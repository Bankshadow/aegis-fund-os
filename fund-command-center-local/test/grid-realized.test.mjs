import assert from "node:assert/strict";
import test from "node:test";
import { computeRealizedCycles } from "../src/lib/grid-realized.ts";

// Arithmetic grid: lower 90, upper 110, 4 grids → step 5. Lines: 90,95,100,105,110.
const bot = {
  id: "BOT-1",
  environment: "BINANCE_TESTNET",
  pair: "BTCUSDT",
  configuration: { lower: "90", upper: "110", grids: 4, mode: "ARITHMETIC" },
};

const order = (side, price, status, quantity = "0.010") => ({
  id: `${side}-${price}`,
  executionId: "EXE-1",
  botId: "BOT-1",
  symbol: "BTCUSDT",
  exchangeOrderId: `x-${price}`,
  clientOrderId: `c-${side}-${price}`,
  gridIndex: 1,
  side,
  price,
  quantity,
  status,
  createdAt: "2026-07-19T00:00:00Z",
  updatedAt: "2026-07-19T00:00:00Z",
});

test("a completed buy→sell round trip books realized profit minus fees", () => {
  // BUY @95 filled, its paired SELL @100 (one line up) filled → one cycle.
  const summary = computeRealizedCycles(bot, [order("BUY", "95", "FILLED"), order("SELL", "100", "FILLED")]);
  assert.equal(summary.matchedCycles, 1);
  // profit = (100-95)*0.01 - (95+100)*0.01*0.001 = 0.05 - 0.00195 = 0.04805 → 0.0481
  assert.equal(summary.realizedProfit, "0.0481");
  assert.equal(summary.cycles[0].buyPrice, "95");
  assert.equal(summary.cycles[0].sellPrice, "100");
  assert.equal(summary.openBuyLegs, 0);
  assert.equal(summary.openSellLegs, 0);
});

test("a single filled leg is reported open, never as profit", () => {
  const summary = computeRealizedCycles(bot, [order("BUY", "95", "FILLED")]);
  assert.equal(summary.matchedCycles, 0);
  assert.equal(summary.realizedProfit, "0.0000");
  assert.equal(summary.openBuyLegs, 1);
});

test("open (NEW) orders are excluded from realized P/L", () => {
  const summary = computeRealizedCycles(bot, [order("BUY", "95", "NEW"), order("SELL", "100", "NEW")]);
  assert.equal(summary.matchedCycles, 0);
  assert.equal(summary.realizedProfit, "0.0000");
  assert.equal(summary.openBuyLegs, 0); // NEW is not a filled leg either
});

test("a sell not one line above any buy does not pair", () => {
  // SELL @110 is two lines above BUY @95; outside the half-step tolerance.
  const summary = computeRealizedCycles(bot, [order("BUY", "95", "FILLED"), order("SELL", "110", "FILLED")]);
  assert.equal(summary.matchedCycles, 0);
  assert.equal(summary.openBuyLegs, 1);
  assert.equal(summary.openSellLegs, 1);
});

test("multiple cycles accumulate and each sell is used once", () => {
  const summary = computeRealizedCycles(bot, [
    order("BUY", "90", "FILLED"),
    order("BUY", "95", "FILLED"),
    order("SELL", "95", "FILLED"), // pairs with buy 90 (90+5)
    order("SELL", "100", "FILLED"), // pairs with buy 95 (95+5)
  ]);
  assert.equal(summary.matchedCycles, 2);
  assert.equal(summary.openBuyLegs, 0);
  assert.equal(summary.openSellLegs, 0);
});

test("geometric grid pairs a buy with buy×ratio", () => {
  const geo = { ...bot, configuration: { lower: "100", upper: "200", grids: 4, mode: "GEOMETRIC" } };
  // ratio = (200/100)^(1/4) ≈ 1.18921. buy 100 → expected sell ≈ 118.92.
  const summary = computeRealizedCycles(geo, [order("BUY", "100", "FILLED"), order("SELL", "118.92", "FILLED")]);
  assert.equal(summary.matchedCycles, 1);
});
