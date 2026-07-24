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
