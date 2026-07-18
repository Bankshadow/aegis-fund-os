import assert from "node:assert/strict";
import test from "node:test";

import { buildBinanceStyleGridSetup, buildPaperGridLevels } from "../src/lib/binance-paper-grid.ts";

test("builds deterministic symmetric paper-only grid levels", () => {
  const levels = buildPaperGridLevels(100_000, 12_000, 3, 0.005);
  assert.equal(levels.length, 6);
  assert.deepEqual(levels.map((level) => level.side), ["BUY", "SELL", "BUY", "SELL", "BUY", "SELL"]);
  assert.equal(levels[0].price, 99_500);
  assert.equal(levels[1].price, 100_500);
  assert.ok(levels.every((level) => level.status === "SIMULATED_PENDING"));
  assert.ok(levels.every((level) => !("exchangeOrderId" in level)));
});

test("fails closed on invalid paper-grid risk inputs", () => {
  assert.throws(() => buildPaperGridLevels(0, 12_000), /midPrice/);
  assert.throws(() => buildPaperGridLevels(100_000, -1), /capitalUsdt/);
  assert.throws(() => buildPaperGridLevels(100_000, 12_000, 21), /levelCount/);
  assert.throws(
    () => buildPaperGridLevels(100_000, 20, 3, 0.005, { tickSize: 0.01, stepSize: 0.00001, minNotional: 5 }),
    /below Binance minimum/,
  );
});

test("quantizes a setup to Binance tick and lot rules", () => {
  const levels = buildPaperGridLevels(
    64_179.135, 12_000, 3, 0.005,
    { tickSize: 0.01, stepSize: 0.00001, minNotional: 5 },
  );
  assert.equal(Number((levels[0].price / 0.01).toFixed(8)) % 1, 0);
  assert.equal(Number((levels[0].quantity / 0.00001).toFixed(8)) % 1, 0);
});

test("builds a Binance-style arithmetic grid with fee-aware preview", () => {
  const setup = buildBinanceStyleGridSetup(100, {
    lowerPrice: 90, upperPrice: 110, gridCount: 10, investment: 1_000,
    mode: "ARITHMETIC", feeRatePct: 0.1, takeProfit: 120, stopLoss: 80,
    trailingUp: true, sellAllOnStop: false,
  }, { tickSize: 0.01, stepSize: 0.00001, minNotional: 5 });
  assert.equal(setup.levels.length, 10);
  assert.ok(setup.levels.some((level) => level.side === "BUY"));
  assert.ok(setup.levels.some((level) => level.side === "SELL"));
  assert.ok(setup.estimatedProfitPerGridPct.min > 0);
  assert.ok(setup.levels.every((level) => !("exchangeOrderId" in level)));
});

test("fails closed on unsafe Binance-style advanced parameters", () => {
  const base = { lowerPrice: 90, upperPrice: 110, gridCount: 10, investment: 1_000, mode: "GEOMETRIC", feeRatePct: 0.1 };
  const rules = { tickSize: 0.01, stepSize: 0.00001, minNotional: 5 };
  assert.throws(() => buildBinanceStyleGridSetup(120, base, rules), /inside the grid range/);
  assert.throws(() => buildBinanceStyleGridSetup(100, { ...base, takeProfit: 105 }, rules), /above the upper/);
  assert.throws(() => buildBinanceStyleGridSetup(100, { ...base, stopLoss: 95 }, rules), /below the lower/);
});
