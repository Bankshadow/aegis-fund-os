import assert from "node:assert/strict";
import test from "node:test";

import { parseMarketCsv, runAotBacktest, validateMarketBars } from "../src/lib/aot-backtest.ts";

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

test("conservative model records ambiguous bars instead of inventing intraday order", () => {
  const run = runAotBacktest(config, [
    { timestamp: "2024-01-01", open: 40, high: 42, low: 38, close: 40 },
    ...bars.slice(1),
  ]);
  assert.ok(run.metrics.ambiguousBars >= 1);
  assert.ok(run.warnings.some((warning) => warning.code === "AMBIGUOUS_BARS"));
});

test("invalid OHLC fails closed before simulation", () => {
  assert.throws(
    () =>
      runAotBacktest(config, [{ timestamp: "2024-01-01", open: 10, high: 5, low: 9, close: 10 }]),
    /Invalid OHLC/,
  );
});
