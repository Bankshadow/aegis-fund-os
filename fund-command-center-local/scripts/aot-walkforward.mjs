/**
 * AOT grid walk-forward harness — out-of-sample validation.
 *
 * Protocol and pass criteria are declared in docs/AOT_VALIDATION_CRITERIA.md and
 * must not be edited to fit an observed result. This script only measures; it
 * decides nothing and places no order.
 *
 *   node scripts/aot-walkforward.mjs [--out report.json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  analyzeMarketData,
  parseMarketCsv,
  runAotBacktest,
  validateMarketBars,
} from "../src/lib/aot-backtest.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(here, "..", "data", "historical", "AOT.BK_daily_2005-2026.csv");

// ---- protocol constants (docs/AOT_VALIDATION_CRITERIA.md §3) ----------------
const IS_BARS = 504;
const OOS_BARS = 252;
const STEP = 252;
const MODES = ["CONSERVATIVE_OHLC", "WORST_CASE", "OPTIMISTIC_OHLC"];
const PASS_MODES = ["CONSERVATIVE_OHLC", "WORST_CASE"];
const GRID_COUNTS = [8, 10, 12];
const RANGE_SCALES = [0.9, 1.0, 1.1];
const CAPITAL = 1_000_000;

// E27 mechanism: percentile-rank regime filter, fixed a priori (no tuning pass).
// Enable with --regime; without it this reproduces the E26 baseline exactly.
const REGIME_ENABLED = process.argv.includes("--regime");
// E28 mechanism: trailing re-anchor. Enable with --trailing.
const TRAILING_ENABLED = process.argv.includes("--trailing");
const REGIME_FILTER = { lookback: 20, rankWindow: 252, upperRank: 80, lowerRank: 20 };

// Thai retail cost model, percent units (engine divides by 100).
const COSTS = {
  commissionRate: 0.157,
  exchangeFeeRate: 0.005,
  vatRate: 7,
  slippageRate: 0.05,
};

const dateOnly = (timestamp) => timestamp.slice(0, 10);
const mean = (values) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0);
const pct = (part, whole) => (whole ? (part / whole) * 100 : 0);

/** Buy-and-hold max drawdown over a bar window, in percent (C3 needs this). */
function buyAndHoldDrawdown(bars) {
  let peak = bars[0].close;
  let maxDd = 0;
  for (const bar of bars) {
    peak = Math.max(peak, bar.high ?? bar.close);
    const low = bar.low ?? bar.close;
    maxDd = Math.max(maxDd, ((peak - low) / peak) * 100);
  }
  return maxDd;
}

/**
 * Grid geometry derived from IN-SAMPLE bars only. Widening the range with any
 * out-of-sample bar would be lookahead — AOT ran 5 -> 64 THB, so a range fitted
 * on the whole file silently guarantees a good result.
 */
function geometryFromInSample(isBars, gridCount, rangeScale, gridType) {
  const closes = isBars.map((bar) => bar.close).sort((a, b) => a - b);
  const at = (q) => closes[Math.min(closes.length - 1, Math.floor(q * closes.length))];
  const mid = at(0.5);
  const lower = mid - (mid - at(0.05)) * rangeScale;
  const upper = mid + (at(0.95) - mid) * rangeScale;
  return { lowerPrice: Math.max(0.01, lower), upperPrice: upper, gridCount, gridType };
}

function configFor(geometry, window, executionMode, firstClose) {
  // Standard grid posture: half the book in stock so sells above the reference
  // level are possible from bar one; the rest in cash to buy the way down.
  const inventory = Math.floor(CAPITAL / 2 / firstClose / 100) * 100;
  return {
    symbol: "AOT",
    startDate: dateOnly(window[0].timestamp),
    endDate: dateOnly(window[window.length - 1].timestamp),
    initialCapital: CAPITAL,
    initialCash: CAPITAL - inventory * firstClose,
    initialInventory: inventory,
    ...geometry,
    tickSize: 0.25,
    boardLot: 100,
    ...COSTS,
    fillModel: "CONSERVATIVE",
    endTreatment: "MARK_TO_MARKET",
    dividendInclusion: false,
    dividendReinvestment: false,
    cashConstraint: true,
    executionMode,
    regimeFilter: REGIME_ENABLED ? REGIME_FILTER : null,
    trailing: TRAILING_ENABLED ? { mode: "TRAIL_UP" } : null,
  };
}

let runCount = 0;
/**
 * `window` is the range actually simulated; `supplied` may prepend warm-up bars
 * so the regime detector is ranked from history rather than starting blind.
 * Warm-up is past data only — startDate still gates what is traded.
 */
function measure(geometry, window, executionMode, supplied = window) {
  runCount += 1;
  const config = configFor(geometry, window, executionMode, window[0].close);
  const run = runAotBacktest(config, supplied);
  const m = run.metrics;
  return {
    runId: run.id,
    configHash: run.metadata?.configHash ?? null,
    totalReturn: m.totalReturn,
    maxDrawdown: m.maxDrawdown,
    robust: m.totalReturn - 2 * m.maxDrawdown,
    alpha: m.alpha,
    buyAndHoldReturn: m.buyAndHoldReturn,
    completedCycles: m.completedCycles,
    fills: m.fills,
    engaged: m.completedCycles >= 1,
    isReconciled: m.isReconciled,
    ambiguousBars: m.ambiguousBars,
    reAnchors: m.reAnchors,
    regimeSuspendedBars: m.regimeSuspendedBars,
    regimeBarCounts: m.regimeBarCounts,
    totalFees: m.totalFees,
    forcedLiquidation: m.forcedLiquidation,
    endingInventory: m.endingInventory,
    maxCapitalDeployed: m.maxCapitalDeployed,
  };
}

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

// ---- walk-forward ----------------------------------------------------------
const folds = [];
// Enough past bars for the detector to be ranked before the window opens.
const WARMUP = REGIME_FILTER.rankWindow + REGIME_FILTER.lookback + 30;
const withWarmup = (from, to) => bars.slice(Math.max(0, from - WARMUP), to);

for (let start = 0; start + IS_BARS + OOS_BARS <= bars.length; start += STEP) {
  const isWindow = bars.slice(start, start + IS_BARS);
  const oosWindow = bars.slice(start + IS_BARS, start + IS_BARS + OOS_BARS);
  const isSupplied = withWarmup(start, start + IS_BARS);
  const oosSupplied = withWarmup(start + IS_BARS, start + IS_BARS + OOS_BARS);

  // Selection step: pick geometry on IS only, by IS robust score.
  let selected = null;
  for (const gridType of ["ARITHMETIC", "GEOMETRIC"]) {
    for (const gridCount of GRID_COUNTS) {
      const geometry = geometryFromInSample(isWindow, gridCount, 1.0, gridType);
      const result = measure(geometry, isWindow, "CONSERVATIVE_OHLC", isSupplied);
      if (!selected || result.robust > selected.result.robust) selected = { geometry, result };
    }
  }

  const oos = {};
  for (const mode of MODES) oos[mode] = measure(selected.geometry, oosWindow, mode, oosSupplied);

  // C7 sensitivity: perturb the selected geometry, evaluate on OOS.
  const perturbations = [];
  for (const gridCount of [selected.geometry.gridCount - 2, selected.geometry.gridCount, selected.geometry.gridCount + 2]) {
    if (gridCount < 4) continue;
    for (const scale of RANGE_SCALES) {
      const geometry = geometryFromInSample(isWindow, gridCount, scale, selected.geometry.gridType);
      perturbations.push({ gridCount, scale, ...measure(geometry, oosWindow, "CONSERVATIVE_OHLC", oosSupplied) });
    }
  }

  folds.push({
    index: folds.length + 1,
    isRange: [dateOnly(isWindow[0].timestamp), dateOnly(isWindow.at(-1).timestamp)],
    oosRange: [dateOnly(oosWindow[0].timestamp), dateOnly(oosWindow.at(-1).timestamp)],
    selected: selected.geometry,
    isRobust: selected.result.robust,
    oos,
    buyAndHoldDrawdown: buyAndHoldDrawdown(oosWindow),
    perturbations,
  });
  const c = oos.CONSERVATIVE_OHLC;
  console.log(
    `fold ${String(folds.length).padStart(2)} OOS ${folds.at(-1).oosRange.join("..")}  ` +
      `ret=${c.totalReturn.toFixed(2)}%  dd=${c.maxDrawdown.toFixed(2)}%  ` +
      `robust=${c.robust.toFixed(4)}  alpha=${c.alpha.toFixed(2)}  cycles=${c.completedCycles}`,
  );
}

// ---- criteria evaluation (docs/AOT_VALIDATION_CRITERIA.md §4) --------------
function evaluateMode(mode) {
  const rows = folds.map((fold) => fold.oos[mode]);
  const engaged = rows.filter((row) => row.engaged);
  const beatsBuyHold = rows.filter((row) => row.alpha > 0);
  const meanDd = mean(rows.map((row) => row.maxDrawdown));
  const meanBhDd = mean(folds.map((fold) => fold.buyAndHoldDrawdown));
  return {
    mode,
    folds: rows.length,
    meanRobust: mean(rows.map((row) => row.robust)),
    meanAlpha: mean(rows.map((row) => row.alpha)),
    meanReturn: mean(rows.map((row) => row.totalReturn)),
    meanBuyAndHold: mean(rows.map((row) => row.buyAndHoldReturn)),
    meanDrawdown: meanDd,
    meanBuyAndHoldDrawdown: meanBhDd,
    engagedPct: pct(engaged.length, rows.length),
    beatsBuyHoldPct: pct(beatsBuyHold.length, rows.length),
    reconciledAll: rows.every((row) => row.isReconciled),
    maxAmbiguousPct: Math.max(...folds.map((fold, i) => pct(rows[i].ambiguousBars, OOS_BARS))),
    forcedLiquidations: rows.filter((row) => row.forcedLiquidation).length,
    totalFees: rows.reduce((sum, row) => sum + row.totalFees, 0),
    C1: mean(rows.map((row) => row.robust)) > 0,
    C2: mean(rows.map((row) => row.alpha)) > 0 && pct(beatsBuyHold.length, rows.length) > 50,
    C3: meanDd <= meanBhDd,
    C4: pct(engaged.length, rows.length) >= 50,
    C6:
      rows.every((row) => row.isReconciled) &&
      folds.every((fold, i) => pct(rows[i].ambiguousBars, OOS_BARS) <= 5),
  };
}

const modeResults = PASS_MODES.map(evaluateMode);
const allPerturbations = folds.flatMap((fold) => fold.perturbations);
const flatSurfacePct = pct(allPerturbations.filter((row) => row.robust > 0).length, allPerturbations.length);
const C5 = modeResults.every((r) => r.C1 && r.C2 && r.C3 && r.C4);
const C7 = flatSurfacePct >= 60;
const C6 = modeResults.every((r) => r.C6);
const passed = C5 && C6 && C7;

const optimismGap =
  mean(folds.map((fold) => fold.oos.OPTIMISTIC_OHLC.totalReturn)) -
  mean(folds.map((fold) => fold.oos.CONSERVATIVE_OHLC.totalReturn));

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
      { generatedAt: new Date().toISOString(), protocol: { IS_BARS, OOS_BARS, STEP, COSTS, CAPITAL }, quality, folds, modeResults, C5, C6, C7, passed, runCount, flatSurfacePct, optimismGap },
      null,
      2,
    ),
  );
  console.log(`wrote ${process.argv[outIndex + 1]}`);
}

process.exit(passed ? 0 : 1);
