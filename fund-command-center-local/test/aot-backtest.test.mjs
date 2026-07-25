import assert from "node:assert/strict";
import test from "node:test";

import {
  computeRegimeStates,
  parseMarketCsv,
  runAotBacktest,
  validateMarketBars,
} from "../src/lib/aot-backtest.ts";

const config = {
  symbol: "AOT",
  startDate: "2024-01-01",
  endDate: "2024-01-04",
  initialCapital: 100000,
  initialCash: 100000,
  initialInventory: 3000,
  lowerPrice: 36,
  upperPrice: 44,
  gridCount: 8,
  gridType: "ARITHMETIC",
  tickSize: 0.25,
  boardLot: 100,
  commissionRate: 0.2,
  exchangeFeeRate: 0,
  vatRate: 7,
  slippageRate: 0.05,
  fillModel: "CONSERVATIVE",
  endTreatment: "MARK_TO_MARKET",
  dividendInclusion: true,
  dividendReinvestment: false,
  cashConstraint: true,
};

const bars = [
  { timestamp: "2024-01-01T00:00:00Z", open: 40, high: 40, low: 38, close: 38 },
  { timestamp: "2024-01-02T00:00:00Z", open: 38, high: 39, low: 38, close: 39 },
  { timestamp: "2024-01-03T00:00:00Z", open: 39, high: 41, low: 39, close: 40 },
  { timestamp: "2024-01-04T00:00:00Z", open: 40, high: 40, low: 40, close: 40 },
];

test("CSV parser validates OHLC and preserves source timestamps", () => {
  const parsed = parseMarketCsv("timestamp,open,high,low,close\n2024-01-01,40,41,39,40");
  assert.equal(parsed.bars[0].close, 40);
  assert.equal(parsed.warnings.length, 0);
  assert.ok(
    validateMarketBars([
      { timestamp: "2024-01-02", open: 1, high: 1, low: 1, close: 1 },
      { timestamp: "2024-01-01", open: 1, high: 1, low: 1, close: 1 },
    ]).some((warning) => warning.code === "UNSORTED_OR_DUPLICATE"),
  );
});

test("conservative backtest fills buy then paired sell and reports costs", () => {
  const run = runAotBacktest(config, bars);
  assert.ok(run.metrics.buyFills > 0);
  assert.ok(run.metrics.sellFills > 0);
  assert.ok(run.metrics.completedCycles > 0);
  assert.ok(run.metrics.totalFees > 0);
  assert.equal(run.metrics.ambiguousBars, 0);
  assert.equal(run.equityCurve.length, bars.length);
  assert.equal(
    run.warnings.some((warning) => warning.code === "NO_DATA"),
    false,
  );
});

test("backtest reconciles P/L and reports transparent duration and trade quality", () => {
  const run = runAotBacktest(config, bars);
  assert.equal(run.metrics.startEquity, 214000);
  assert.equal(run.metrics.isReconciled, true);
  assert.ok(Math.abs(run.metrics.reconciliationDifference) <= 0.01);
  assert.equal(
    run.warnings.some((warning) => warning.code === "RECONCILIATION_FAILED"),
    false,
  );
  assert.equal(run.metrics.durationDays, 3);
  assert.ok(run.metrics.totalReturn <= 100);
  assert.ok(run.equityCurve.every((point) => point.drawdown >= 0));
  assert.ok(
    run.metrics.winRate === null || (run.metrics.winRate >= 0 && run.metrics.winRate <= 100),
  );
  assert.ok(run.events.length > 0);
  assert.deepEqual(
    run.events.slice(0, 4).map((event) => event.type),
    ["ORDER_SUBMITTED", "ORDER_QUEUED", "ORDER_SUBMITTED", "ORDER_QUEUED"],
  );
  assert.ok(run.events.some((event) => event.type === "PORTFOLIO_VALUATION"));
});

test("conservative model records ambiguous bars instead of inventing intraday order", () => {
  const run = runAotBacktest(config, [
    { timestamp: "2024-01-01", open: 40, high: 42, low: 38, close: 40 },
    ...bars.slice(1),
  ]);
  assert.ok(run.metrics.ambiguousBars >= 1);
  assert.ok(run.warnings.some((warning) => warning.code === "AMBIGUOUS_BARS"));
});

// Wide-swing bars so several grid levels of both sides are touched per bar,
// which is exactly where an execution assumption has to be stated.
const swingBars = [
  { timestamp: "2024-01-01T00:00:00Z", open: 40, high: 43, low: 37, close: 40 },
  { timestamp: "2024-01-02T00:00:00Z", open: 40, high: 43.5, low: 36.5, close: 41 },
  { timestamp: "2024-01-03T00:00:00Z", open: 41, high: 43, low: 37, close: 39 },
  { timestamp: "2024-01-04T00:00:00Z", open: 39, high: 42, low: 38, close: 40 },
];

const runUnder = (executionMode, marketBars = swingBars, overrides = {}) =>
  runAotBacktest({ ...config, executionMode, ...overrides }, marketBars);

const meanPrice = (run, side) => {
  const fills = run.fills.filter((fill) => fill.side === side);
  return fills.length ? fills.reduce((sum, fill) => sum + fill.fillPrice, 0) / fills.length : null;
};

// NOTE ON WHAT IS AND IS NOT BOUNDED.
// OPTIMISTIC and WORST_CASE trade the same touched levels under opposite
// assumptions, so their execution quality genuinely brackets the truth.
// CONSERVATIVE is NOT a member of that bracket: it declines to guess and books
// no fill at all on an ambiguous bar, so its equity can land above or below
// both. Asserting optimistic >= conservative >= worst would be asserting a
// relationship the design does not provide.
// Nor is the bracket a bound on PORTFOLIO outcome across bars: the modes leave
// different orders open, so later bars diverge and even the cycle count can run
// the other way. What is bounded is the quality of each fill.
test("optimistic and worst case bracket execution quality", () => {
  const optimistic = runUnder("OPTIMISTIC_OHLC");
  const worst = runUnder("WORST_CASE");
  assert.ok(meanPrice(optimistic, "BUY") !== null && meanPrice(worst, "BUY") !== null);
  assert.ok(
    meanPrice(worst, "BUY") >= meanPrice(optimistic, "BUY"),
    `worst-case buys ${meanPrice(worst, "BUY")} must not be cheaper than optimistic ${meanPrice(optimistic, "BUY")}`,
  );
});

test("worst case ranks fills by adversity on both sides, not by grid index", () => {
  // The old comparator sorted both sides by grid index, so WORST_CASE took the
  // worst buys but the *best* sells — which is how it outscored CONSERVATIVE on
  // real AOT folds (E26). A sell is adverse when it accepts a lower price.
  const worst = runUnder("WORST_CASE");
  const optimistic = runUnder("OPTIMISTIC_OHLC");
  assert.ok(meanPrice(worst, "SELL") !== null && meanPrice(optimistic, "SELL") !== null);
  assert.ok(
    meanPrice(worst, "SELL") <= meanPrice(optimistic, "SELL"),
    `worst-case sells ${meanPrice(worst, "SELL")} must not beat optimistic ${meanPrice(optimistic, "SELL")}`,
  );
});

test("an ambiguous bar: worst case adds exposure, conservative books nothing", () => {
  const ambiguous = [{ timestamp: "2024-01-01", open: 40, high: 42, low: 38, close: 40 }];
  const single = { startDate: "2024-01-01", endDate: "2024-01-01" };
  const worst = runUnder("WORST_CASE", ambiguous, single);
  assert.ok(worst.metrics.buyFills > 0, "the exposure-increasing leg must fill");
  assert.equal(worst.metrics.sellFills, 0, "the offsetting leg must not fill on the worst path");
  assert.equal(worst.metrics.completedCycles, 0, "an unresolved bar must never be credited a cycle");

  const conservative = runUnder("CONSERVATIVE_OHLC", ambiguous, single);
  assert.equal(conservative.metrics.fills, 0);
  assert.ok(conservative.metrics.ambiguousBars >= 1);

  const optimistic = runUnder("OPTIMISTIC_OHLC", ambiguous, single);
  assert.ok(optimistic.metrics.sellFills > 0, "the optimistic path resolves the bar in its favour");
  // On a single unresolved bar the portfolio outcome IS ordered, because the
  // paths have not yet diverged into different open-order sets.
  assert.ok(
    optimistic.metrics.gridProfit >= worst.metrics.gridProfit,
    `optimistic grid profit ${optimistic.metrics.gridProfit} must not be below worst case ${worst.metrics.gridProfit}`,
  );
});

// --- regime filter (E27 mechanism) ------------------------------------------
const REGIME = { lookback: 5, rankWindow: 40, upperRank: 80, lowerRank: 20 };

// A flat oscillating phase that lets the grid trade, then a rising leg. The
// baseline matters: percentile rank measures momentum against its own recent
// history, so a trend is only "high rank" relative to a calmer stretch.
const rampBars = Array.from({ length: 80 }, (_, index) => {
  const close = index < 40 ? (index % 2 === 0 ? 39.5 : 40.5) : 40 + (index - 39) * 0.15;
  return {
    timestamp: `2024-${String(Math.floor(index / 28) + 1).padStart(2, "0")}-${String((index % 28) + 1).padStart(2, "0")}`,
    open: close,
    high: close + 0.5,
    low: close - 0.5,
    close,
  };
});

test("regime state never depends on a future bar", () => {
  const truncated = computeRegimeStates(rampBars.slice(0, 60), REGIME);
  const full = computeRegimeStates(rampBars, REGIME);
  // Rewriting the tail must not change any earlier state; if it did, the
  // detector would be reading the future and every result built on it is void.
  assert.deepEqual(full.slice(0, 60), truncated);
  const mutated = computeRegimeStates(
    [...rampBars.slice(0, 60), ...rampBars.slice(60).map((bar) => ({ ...bar, close: 999 }))],
    REGIME,
  );
  assert.deepEqual(mutated.slice(0, 60), truncated);
});

test("no regime filter leaves every bar in RANGE and the run unchanged", () => {
  const plain = runAotBacktest(config, bars);
  assert.equal(plain.metrics.regimeSuspendedBars, 0);
  assert.equal(plain.metrics.regimeBarCounts.TREND_UP, 0);
  assert.equal(plain.metrics.regimeBarCounts.TREND_DOWN, 0);
  assert.equal(plain.metrics.regimeBarCounts.RANGE, bars.length);
  const nulled = runAotBacktest({ ...config, regimeFilter: null }, bars);
  assert.equal(nulled.metrics.finalPortfolioValue, plain.metrics.finalPortfolioValue);
});

test("a rising trend is detected and suspends the sell side", () => {
  const window = { startDate: rampBars[0].timestamp, endDate: rampBars.at(-1).timestamp };
  const filtered = runAotBacktest({ ...config, ...window, regimeFilter: REGIME }, rampBars);
  assert.ok(filtered.metrics.regimeBarCounts.TREND_UP > 0, "the ramp must be detected as a trend");
  assert.ok(filtered.metrics.regimeSuspendedBars > 0);
  assert.equal(
    filtered.events.some(
      (event) => event.type === "STRATEGY_DECISION" && event.payload.suspendedSide === "SELL",
    ),
    true,
    "the audit stream must record why a bar was skipped",
  );
});

test("E27 limitation: suspending a limit order delays the fill, it does not avoid it", () => {
  // This is the mechanism-level negative result recorded as E27, pinned as a
  // test so nobody re-proposes the same filter expecting a different outcome.
  // A suspended SELL is held, not cancelled, so when the regime relaxes it
  // still executes at its original limit price — the rally was not captured,
  // only postponed. Preserving upside on a fixed-level grid needs the levels
  // themselves to move (trailing/re-anchoring), which this filter does not do.
  const window = { startDate: rampBars[0].timestamp, endDate: rampBars.at(-1).timestamp };
  const unfiltered = runAotBacktest({ ...config, ...window }, rampBars);
  const filtered = runAotBacktest({ ...config, ...window, regimeFilter: REGIME }, rampBars);
  assert.equal(
    filtered.metrics.sellFills,
    unfiltered.metrics.sellFills,
    "the same sells still happen — suspension only moved them later",
  );
  assert.equal(filtered.metrics.endingInventory, unfiltered.metrics.endingInventory);
});

// --- trailing re-anchor (E28 mechanism) -------------------------------------
const breakoutWindow = { startDate: rampBars[0].timestamp, endDate: rampBars.at(-1).timestamp };

test("no trailing config leaves the ladder where it started", () => {
  const plain = runAotBacktest({ ...config, ...breakoutWindow }, rampBars);
  assert.equal(plain.metrics.reAnchors, 0);
  const nulled = runAotBacktest({ ...config, ...breakoutWindow, trailing: null }, rampBars);
  assert.equal(nulled.metrics.finalPortfolioValue, plain.metrics.finalPortfolioValue);
});

test("trailing lifts the whole ladder once price closes above it", () => {
  const trailed = runAotBacktest(
    { ...config, ...breakoutWindow, trailing: { mode: "TRAIL_UP" } },
    rampBars,
  );
  assert.ok(trailed.metrics.reAnchors > 0, "the ramp closes above 44 and must trigger a lift");
  // Width and spacing are preserved; only the location moves.
  const cancelled = trailed.orders.filter((order) => order.status === "CANCELLED");
  assert.ok(cancelled.length > 0, "stale levels must be cancelled, not held (the E27 lesson)");
  assert.ok(
    trailed.orders.some((order) => order.limitPrice > config.upperPrice),
    "the lifted ladder must quote above the original range",
  );
  assert.equal(
    trailed.events.some((event) => event.type === "ORDER_CANCELLED"),
    true,
    "the audit stream must show the cancellation",
  );
});

test("trailing keeps the grid trading instead of standing sold out", () => {
  const fixed = runAotBacktest({ ...config, ...breakoutWindow }, rampBars);
  const trailed = runAotBacktest(
    { ...config, ...breakoutWindow, trailing: { mode: "TRAIL_UP" } },
    rampBars,
  );
  // This is the entire point of E28: after the breakout the fixed grid has
  // nothing left to do, while the trailed one still has live levels.
  assert.ok(
    trailed.metrics.orders > fixed.metrics.orders,
    `trailed placed ${trailed.metrics.orders} orders vs fixed ${fixed.metrics.orders}`,
  );
});

test("trailing never moves the ladder down", () => {
  const falling = rampBars.map((bar, index) => {
    const close = index < 40 ? bar.close : 40 - (index - 39) * 0.15;
    return { ...bar, open: close, high: close + 0.5, low: close - 0.5, close };
  });
  const trailed = runAotBacktest(
    { ...config, ...breakoutWindow, trailing: { mode: "TRAIL_UP" } },
    falling,
  );
  assert.equal(trailed.metrics.reAnchors, 0, "a falling market must not drag the grid down");
});

test("invalid OHLC fails closed before simulation", () => {
  assert.throws(
    () =>
      runAotBacktest(config, [{ timestamp: "2024-01-01", open: 10, high: 5, low: 9, close: 10 }]),
    /Invalid OHLC/,
  );
});
