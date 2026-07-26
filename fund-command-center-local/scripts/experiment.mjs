/**
 * Experiment runner — declare criteria as data, run, and get the decomposition for
 * free.
 *
 * Every experiment E26-E29 followed the same ritual by hand: write the criteria,
 * run the harness, read numbers off stdout, check them against the criteria, then
 * hand-write a fold-by-fold comparison against the baseline to work out whether a
 * mean improvement was real. That last step is the one that matters and the one
 * most easily skipped — E29 passed all three of its declared mechanism criteria on
 * the mean, and only a hand-written comparison revealed that most of the movement
 * was the selection step choosing a different geometry, plus folds that had simply
 * stopped trading (where "less drawdown" is a tautology).
 *
 * Doing that check by hand means one day it does not get done and a false positive
 * is reported. So it is automated here, and the criteria live in a file written
 * BEFORE the run — data, not prose, so they cannot be quietly reinterpreted after
 * seeing the result.
 *
 * This only measures. It decides nothing and places no order.
 *
 *   node scripts/experiment.mjs experiments/E29.json [--out report.json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { analyzeMarketData, parseMarketCsv, validateMarketBars } from "../src/lib/aot-backtest.ts";
import { runAotWalkForward } from "../src/lib/aot-walkforward.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(here, "..", "data", "historical", "AOT.BK_daily_2005-2026.csv");

const specPath = process.argv[2];
if (!specPath) {
  console.error("usage: node scripts/experiment.mjs <experiment.json> [--out report.json]");
  process.exit(64);
}
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));

// ---- guard rails on the declaration itself -------------------------------
// Criteria must be declared before the run. A spec without them is not an
// experiment, it is a fishing trip.
if (!spec.id || !spec.declaredAt) {
  console.error("ABORT: spec needs `id` and `declaredAt` (the date the criteria were frozen).");
  process.exit(64);
}
if (!Array.isArray(spec.mechanismCriteria) || !spec.mechanismCriteria.length) {
  console.error("ABORT: spec needs at least one entry in `mechanismCriteria`, declared before running.");
  process.exit(64);
}

const { bars } = parseMarketCsv(fs.readFileSync(DATA, "utf8"));
const quality = analyzeMarketData(bars);
const blocked = validateMarketBars(bars).filter((w) => w.severity === "BLOCKED");
if (quality.duplicates || quality.missingOhlcv || quality.invalidPrices || quality.negativeVolume || blocked.length) {
  console.error("ABORT: data quality report is not clean. No result reported.");
  process.exit(2);
}

const conservative = (result) => result.modeResults.find((r) => r.mode === "CONSERVATIVE_OHLC");
const foldOf = (result, i) => result.folds[i].oos.CONSERVATIVE_OHLC;
const geometryOf = (result, i) => JSON.stringify(result.folds[i].selected);

console.log(`experiment ${spec.id}  (criteria declared ${spec.declaredAt})`);
if (spec.title) console.log(`  ${spec.title}`);

const baseline = runAotWalkForward(bars, spec.baseline ?? {});
const variant = runAotWalkForward(bars, spec.variant ?? {});
const b = conservative(baseline);
const v = conservative(variant);

// ---- declared criteria ---------------------------------------------------
const OPS = {
  ">": (a, x) => a > x,
  ">=": (a, x) => a >= x,
  "<": (a, x) => a < x,
  "<=": (a, x) => a <= x,
};
const mechanism = spec.mechanismCriteria.map((criterion) => {
  const actual = v[criterion.metric];
  if (actual === undefined) throw new Error(`Unknown metric "${criterion.metric}" in ${criterion.id}`);
  const op = OPS[criterion.op];
  if (!op) throw new Error(`Unknown operator "${criterion.op}" in ${criterion.id}`);
  return { ...criterion, actual, passed: op(actual, criterion.value) };
});

// Gate criteria are computed by the harness itself and are never softened here.
const gate = {
  C1: v.C1,
  C2: v.C2,
  C3: v.C3,
  C4: v.C4,
  C5: variant.C5,
  C6: variant.C6,
  C7: variant.C7,
  passed: variant.passed,
};

// ---- decomposition: is the mean movement actually the mechanism? ----------
// Three buckets, because they mean very different things:
//   inert      - the mechanism never bit; the fold reproduces the baseline exactly
//   mechanism  - same geometry chosen, so any change IS the mechanism
//   reselected - the selection step picked a different geometry once the mechanism
//                was active, so the change is a selection artifact, not the mechanism
const folds = baseline.folds.map((_, i) => {
  const bf = foldOf(baseline, i);
  const vf = foldOf(variant, i);
  const sameGeometry = geometryOf(baseline, i) === geometryOf(variant, i);
  const identical = Math.abs(bf.robust - vf.robust) < 1e-9 && Math.abs(bf.alpha - vf.alpha) < 1e-9;
  return {
    index: i + 1,
    oosRange: baseline.folds[i].oosRange,
    bucket: identical ? "inert" : sameGeometry ? "mechanism" : "reselected",
    baseline: { robust: bf.robust, alpha: bf.alpha, cycles: bf.completedCycles },
    variant: { robust: vf.robust, alpha: vf.alpha, cycles: vf.completedCycles },
    robustDelta: vf.robust - bf.robust,
    wentSilent: bf.completedCycles > 0 && vf.completedCycles === 0,
  };
});

const bucket = (name) => folds.filter((f) => f.bucket === name);
const silent = folds.filter((f) => f.wentSilent);
const robustDelta = v.meanRobust - b.meanRobust;
// How much of the mean change is carried by folds that stopped trading? In those,
// a better risk number is a tautology: not being in the market cannot lose money.
const silentContribution = silent.reduce((sum, f) => sum + f.robustDelta, 0) / folds.length;
const mechanismContribution =
  bucket("mechanism").reduce((sum, f) => sum + f.robustDelta, 0) / folds.length;

console.log(`\n=== means (CONSERVATIVE_OHLC) ===`);
for (const metric of ["meanRobust", "meanAlpha", "meanReturn", "meanDrawdown", "engagedPct"]) {
  console.log(`  ${metric.padEnd(14)} baseline ${b[metric].toFixed(2).padStart(8)} -> variant ${v[metric].toFixed(2).padStart(8)}`);
}

console.log(`\n=== declared mechanism criteria ===`);
for (const criterion of mechanism)
  console.log(
    `  ${criterion.passed ? "PASS" : "FAIL"}  ${criterion.id}: ${criterion.metric} ${criterion.op} ${criterion.value}  (actual ${criterion.actual.toFixed(2)})`,
  );

console.log(`\n=== gate ===`);
console.log(`  C1=${gate.C1} C2=${gate.C2} C3=${gate.C3} C4=${gate.C4} C5=${gate.C5} C6=${gate.C6} C7=${gate.C7}`);

console.log(`\n=== decomposition (${folds.length} folds) ===`);
console.log(`  inert (reproduces baseline exactly) : ${bucket("inert").length}`);
console.log(`  mechanism (same geometry chosen)    : ${bucket("mechanism").length}`);
console.log(`  reselected (geometry changed)       : ${bucket("reselected").length}  <- selection artifact, not the mechanism`);
console.log(`  folds that stopped trading entirely : ${silent.length}`);
console.log(`  mean robust delta                   : ${robustDelta >= 0 ? "+" : ""}${robustDelta.toFixed(2)}`);
console.log(`    carried by mechanism folds        : ${mechanismContribution >= 0 ? "+" : ""}${mechanismContribution.toFixed(2)}`);
console.log(`    carried by folds that went silent : ${silentContribution >= 0 ? "+" : ""}${silentContribution.toFixed(2)}`);

// ---- honesty warnings ----------------------------------------------------
// These are the two ways E29 looked like a win on the mean while not being one.
const warnings = [];
if (robustDelta > 0 && bucket("reselected").length > bucket("mechanism").length)
  warnings.push(
    `Most folds that moved changed because the SELECTION step picked a different geometry (${bucket("reselected").length} reselected vs ${bucket("mechanism").length} mechanism). The mean improvement is largely a selection artifact.`,
  );
if (robustDelta > 0 && silentContribution > robustDelta / 2)
  warnings.push(
    `Over half the mean improvement comes from folds that stopped trading entirely (${silent.length} folds). Not being in the market cannot lose money, so this is a tautology rather than an edge.`,
  );
if (v.engagedPct < b.engagedPct - 5)
  warnings.push(`Engagement fell ${b.engagedPct.toFixed(0)}% -> ${v.engagedPct.toFixed(0)}%: the mechanism is partly just trading less.`);

if (warnings.length) {
  console.log(`\n=== READ BEFORE BELIEVING THE MEANS ===`);
  for (const warning of warnings) console.log(`  ! ${warning}`);
}

const allMechanismPassed = mechanism.every((c) => c.passed);
const verdict = gate.passed
  ? "PASS — clears the gate"
  : allMechanismPassed && !warnings.length
    ? "PARTIAL — mechanism criteria met, gate not cleared"
    : allMechanismPassed
      ? "PARTIAL BUT SUSPECT — mechanism criteria met on the mean, decomposition undercuts them (see warnings)"
      : "FAIL — declared mechanism criteria not met";

console.log(`\nVERDICT: ${verdict}`);

const outIndex = process.argv.indexOf("--out");
if (outIndex > -1 && process.argv[outIndex + 1]) {
  fs.writeFileSync(
    process.argv[outIndex + 1],
    JSON.stringify(
      {
        spec,
        generatedAt: new Date().toISOString(),
        means: { baseline: b, variant: v },
        mechanism,
        gate,
        decomposition: {
          inert: bucket("inert").length,
          mechanism: bucket("mechanism").length,
          reselected: bucket("reselected").length,
          wentSilent: silent.length,
          robustDelta,
          mechanismContribution,
          silentContribution,
        },
        folds,
        warnings,
        verdict,
      },
      null,
      2,
    ),
  );
  console.log(`wrote ${process.argv[outIndex + 1]}`);
}

process.exit(gate.passed ? 0 : 1);
