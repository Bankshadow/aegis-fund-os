import assert from "node:assert/strict";
import test from "node:test";
import { projectGridCycleProfit } from "../src/lib/grid-profit.ts";

const bot = { configuration: { lower: "90", upper: "110", grids: 4, mode: "ARITHMETIC" } };
test("projects a positive fee-aware profit for both directions of an adjacent grid cycle", () => {
  const buy = projectGridCycleProfit(bot, { gridIndex: 1, side: "BUY", price: "95", quantity: "1", status: "NEW" });
  const sell = projectGridCycleProfit(bot, { gridIndex: 2, side: "SELL", price: "105", quantity: "1", status: "NEW" });
  assert.equal(buy.targetPrice, "100"); assert.equal(sell.targetPrice, "100");
  assert.equal(buy.estimatedCycleProfit, "4.8050"); assert.equal(sell.estimatedCycleProfit, "4.7950");
});
