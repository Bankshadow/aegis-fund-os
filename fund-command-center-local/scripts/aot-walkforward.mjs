/**
 * AOT grid walk-forward harness — out-of-sample validation.
 *
 * Protocol and pass criteria are declared in docs/AOT_VALIDATION_CRITERIA.md and
 * must not be edited to fit an observed result. This script only measures; it
 * decides nothing and places no order.
 *
 * The walk-forward itself lives in src/lib/aot-walkforward.ts so the in-app
 * Walk-Forward Lab shows the SAME numbers as this research. This file is now a thin
 * CLI wrapper: read the CSV, run the shared function, print, optionally write JSON.
 *
 *   node scripts/aot-walkforward.mjs [--regime] [--trailing] [--exposure-cap] [--out report.json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { analyzeMarketData, parseMarketCsv, validateMarketBars } from "../src/lib/aot-backtest.ts";
import { runAotWalkForward } from "../src/lib/aot-walkforward.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(here, "..", "data", "historical", "AOT.BK_daily_2005-2026.csv");

const options = {
  regime: process.argv.includes("--regime"),
  trailing: process.argv.includes("--trailing"),
  exposureCap: process.argv.includes("--exposure-cap"),
};

const dateOnly = (timestamp) => timestamp.slice(0, 10);

// ---- data ------------------------------------------------------------------
const { bars, warnings: parseWarnings } = parseMarketCsv(fs.readFileSync(DATA, "utf8"));
const quality = analyzeMarketData(bars);
const qualityClean =
  !quality.duplicates && !quality.missingOhlcv && !quality.invalidPrices && !quality.negativeVolume;

console.log(`bars=${bars.length}  ${dateOnly(bars[0].timestamp)} -> ${dateOnly(bars.at(-1).timestamp)}`);
console.log(`data quality: ${JSON.stringify(quality)}  parseWarnings=${parseWarnings.length}`);
// analyzeMarketData does not check OHLC ordering, so validate the whole file up
// front: a bad bar found mid-walk would otherwise abort after partial results.
const blocked = validateMarketBars(bars).filter((warning) => warning.severity === "BLOCKED");
if (!qualityClean || blocked.length) {
  console.error("ABORT: data quality report is not clean (criteria §2). No result reported.");
  for (const warning of blocked) console.error(`  ${warning.code}: ${warning.message}`);
  process.exit(2);
}

// ---- walk-forward (shared with the in-app Walk-Forward Lab) -----------------
const result = runAotWalkForward(bars, options);
const { folds, modeResults, C5, C6, C7, passed, flatSurfacePct, optimismGap, runCount, protocol } = result;

for (const fold of folds) {
  const c = fold.oos.CONSERVATIVE_OHLC;
  console.log(
    `fold ${String(fold.index).padStart(2)} OOS ${fold.oosRange.join("..")}  ` +
      `ret=${c.totalReturn.toFixed(2)}%  dd=${c.maxDrawdown.toFixed(2)}%  ` +
      `robust=${c.robust.toFixed(4)}  alpha=${c.alpha.toFixed(2)}  cycles=${c.completedCycles}`,
  );
}

console.log("\n=== criteria ===");
for (const r of modeResults) {
  console.log(
    `[${r.mode}] folds=${r.folds} meanRobust=${r.meanRobust.toFixed(4)} ` +
      `meanAlpha=${r.meanAlpha.toFixed(2)} meanRet=${r.meanReturn.toFixed(2)} ` +
      `meanB&H=${r.meanBuyAndHold.toFixed(2)} dd=${r.meanDrawdown.toFixed(2)} ` +
      `bhDd=${r.meanBuyAndHoldDrawdown.toFixed(2)} engaged=${r.engagedPct.toFixed(0)}% ` +
      `beatB&H=${r.beatsBuyHoldPct.toFixed(0)}%`,
  );
  console.log(`   C1=${r.C1} C2=${r.C2} C3=${r.C3} C4=${r.C4} C6=${r.C6}`);
}
const allPerturbations = folds.flatMap((fold) => fold.perturbations);
console.log(`C5 (both modes pass C1-C4) = ${C5}`);
console.log(`C6 (reconciled + ambiguous<=5%) = ${C6}`);
console.log(`C7 (flat surface ${flatSurfacePct.toFixed(1)}% >= 60%) = ${C7}`);
console.log(`\nVERDICT: ${passed ? "PASS" : "FAIL"}`);
console.log(`total backtest runs (multiple-testing count) = ${runCount}`);
console.log(`Bonferroni-adjusted alpha for 0.05 over ${allPerturbations.length} OOS configs = ${(0.05 / allPerturbations.length).toExponential(2)}`);
console.log(`optimism gap (OPTIMISTIC - CONSERVATIVE mean return) = ${optimismGap.toFixed(2)} pct pts`);

const outIndex = process.argv.indexOf("--out");
if (outIndex > -1 && process.argv[outIndex + 1]) {
  fs.writeFileSync(
    process.argv[outIndex + 1],
    JSON.stringify(
      { generatedAt: new Date().toISOString(), protocol, quality, folds, modeResults, C5, C6, C7, passed, runCount, flatSurfacePct, optimismGap },
      null,
      2,
    ),
  );
  console.log(`wrote ${process.argv[outIndex + 1]}`);
}

process.exit(passed ? 0 : 1);
