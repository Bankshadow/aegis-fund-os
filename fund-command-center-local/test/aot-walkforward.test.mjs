import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { parseMarketCsv } from "../src/lib/aot-backtest.ts";
import { runAotWalkForward } from "../src/lib/aot-walkforward.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(here, "..", "data", "historical", "AOT.BK_daily_2005-2026.csv");
const { bars } = parseMarketCsv(fs.readFileSync(DATA, "utf8"));

const conservative = (result) => result.modeResults.find((r) => r.mode === "CONSERVATIVE_OHLC");
const round2 = (value) => Math.round(value * 100) / 100;

// These are the committed E26/E28/E29 headline numbers (VALIDATION_LOG §E26-E29).
// The in-app Walk-Forward Lab renders exactly this function's output, so pinning
// them here guarantees the education view can never drift from the research it
// teaches. If a change moves these, the research record must move with it.
test("E26 baseline reproduces the committed walk-forward numbers", () => {
  const r = conservative(runAotWalkForward(bars, {}));
  assert.equal(r.folds, 18);
  assert.equal(round2(r.meanRobust), -17.97);
  assert.equal(round2(r.meanAlpha), -10.79);
  assert.equal(r.C1, false);
});

test("E28 trailing reproduces the committed walk-forward numbers", () => {
  const r = conservative(runAotWalkForward(bars, { trailing: true }));
  assert.equal(round2(r.meanRobust), -19.91);
  assert.equal(round2(r.meanDrawdown), 16.84);
  assert.equal(round2(r.engagedPct), 100);
});

test("E29 exposure cap reproduces the committed walk-forward numbers", () => {
  const r = conservative(runAotWalkForward(bars, { exposureCap: true }));
  assert.equal(round2(r.meanRobust), -12.17);
  assert.equal(round2(r.meanDrawdown), 13.52);
  assert.equal(round2(r.meanAlpha), -8.28);
});

test("cost override is opt-in and pins the honest lesson: no edge even at zero cost", () => {
  const net = conservative(runAotWalkForward(bars, {}));
  // Default must be unchanged by the new option (protects the pinned numbers above).
  assert.equal(round2(net.meanRobust), -17.97);
  const gross = conservative(runAotWalkForward(bars, { costs: { commissionRate: 0, slippageRate: 0, vatRate: 0, exchangeFeeRate: 0 } }));
  // The teaching claim, verified rather than assumed: even with ZERO transaction
  // cost the grid still loses badly to buy-and-hold — costs are not why it fails,
  // the mechanism has no edge. (gross alpha ≈ -11 on this fixture.)
  assert.ok(gross.meanAlpha < -5, `gross alpha ${gross.meanAlpha} should still be well below 0`);
  // Heavier cost does make it strictly worse than the Thai-retail default.
  const heavy = conservative(runAotWalkForward(bars, { costs: { commissionRate: 0.5, slippageRate: 0.3 } }));
  assert.ok(heavy.meanRobust < net.meanRobust, `heavy robust ${heavy.meanRobust} should be worse than net ${net.meanRobust}`);
});

test("diagnostics are additive only: same numbers, same protocol run count", () => {
  const base = runAotWalkForward(bars, {});
  const diag = runAotWalkForward(bars, { diagnostics: true });
  assert.equal(round2(conservative(diag).meanRobust), round2(conservative(base).meanRobust));
  // Diagnostic runs select nothing, so they must NOT inflate the multiple-testing
  // count the research reports (docs/AOT_VALIDATION_CRITERIA.md).
  assert.equal(diag.runCount, base.runCount);
  assert.equal(base.folds[0].candidates, undefined);
  assert.equal(diag.folds[0].candidates.length, 6);
  // The selected candidate's diagnostic OOS must equal its real measured OOS.
  for (const fold of diag.folds) {
    const picked = fold.candidates.find((c) => c.selected);
    assert.ok(Math.abs(picked.oosRobust - fold.oos.CONSERVATIVE_OHLC.robust) < 1e-9);
  }
});

test("in-sample selection is no better than random at picking the OOS winner", () => {
  // The teaching claim, verified: on this fixture the in-sample winner is the
  // out-of-sample winner about as often as chance (1 in 6), and even the
  // hindsight-best geometry is still deeply negative — geometry is not the problem.
  const diag = runAotWalkForward(bars, { diagnostics: true });
  const picks = diag.folds.map((fold) => {
    const sorted = [...fold.candidates].sort((a, b) => b.oosRobust - a.oosRobust);
    return sorted.findIndex((c) => c.selected) + 1;
  });
  const meanRank = picks.reduce((a, b) => a + b, 0) / picks.length;
  assert.ok(meanRank > 2.8, `mean OOS rank ${meanRank} should be near the random 3.5, not near 1`);
  const hindsight =
    diag.folds.reduce((sum, fold) => sum + Math.max(...fold.candidates.map((c) => c.oosRobust)), 0) / diag.folds.length;
  assert.ok(hindsight < 0, `hindsight-best robust ${hindsight} is still negative — geometry cannot rescue this`);
});

test("exposure cap is inert without re-anchor accumulation on the folds where it never binds", () => {
  // 6/18 folds are bit-identical between E28 and E29 (cap never bit). Assert the
  // invariant holds so the education view's 'cap vs no-cap' story is truthful.
  const e28 = runAotWalkForward(bars, { trailing: true });
  const e29 = runAotWalkForward(bars, { exposureCap: true });
  const identical = e28.folds.filter((fold, i) => {
    const a = fold.oos.CONSERVATIVE_OHLC;
    const b = e29.folds[i].oos.CONSERVATIVE_OHLC;
    return Math.abs(a.robust - b.robust) < 1e-6 && Math.abs(a.alpha - b.alpha) < 1e-6;
  });
  assert.equal(identical.length, 6);
});
