import assert from "node:assert/strict";
import test from "node:test";
import { calculatePaperGrid, simulatePaperFill } from "../src/lib/aot-paper-domain.ts";

const config = {
  name: "AOT Paper",
  lowerPrice: "36.00",
  upperPrice: "44.00",
  referencePrice: "40.00",
  initialCash: "100000",
  initialInventory: "3000",
  levelCount: 8,
  mode: "ARITHMETIC",
  oneWayCostPct: "0.20",
  slippagePct: "0.05",
  maxPositionValue: "300000",
  maxActiveOrders: 20,
};

test("paper grid keeps the reference level and applies AOT tick and board lot", () => {
  const result = calculatePaperGrid(config);
  assert.equal(result.levels.length, 9);
  assert.equal(result.levels.filter((row) => row.side === "REFERENCE").length, 1);
  assert.ok(
    result.levels
      .filter((row) => row.side !== "REFERENCE")
      .every(
        (row) =>
          Number(row.price) / 0.25 === Math.round(Number(row.price) / 0.25) &&
          Number(row.quantity) % 100 === 0,
      ),
  );
  assert.ok(!result.validation.some((item) => item.level === "BLOCKED"));
});

test("paper grid blocks duplicate rounded levels and insufficient inventory", () => {
  const duplicate = calculatePaperGrid({
    ...config,
    lowerPrice: "40.00",
    upperPrice: "40.50",
    referencePrice: "40.25",
    levelCount: 8,
  });
  assert.ok(duplicate.validation.some((item) => item.code === "DUPLICATE_TICK"));
  const noInventory = calculatePaperGrid({ ...config, initialInventory: "0" });
  assert.ok(noInventory.validation.some((item) => item.code === "INSUFFICIENT_INVENTORY"));
});

test("paper fills keep cash and inventory non-negative and support partial fills", () => {
  const order = {
    id: "O1",
    gridIndex: 1,
    side: "BUY",
    limitPrice: "39.00",
    originalQuantity: "200",
    filledQuantity: "0",
    remainingQuantity: "200",
    averageFillPrice: "0",
    status: "OPEN",
    reservedAmount: "7800",
  };
  const account = {
    initialCash: "10000",
    cash: "10000",
    inventory: "0",
    averageCost: "0",
    realizedGridProfit: "0",
    realizedAssetPnl: "0",
    costs: "0",
    slippage: "0",
    currentPrice: "40",
    maxDrawdown: "0",
    completedCycles: 0,
  };
  const result = simulatePaperFill(order, account, "39.00", "100");
  assert.equal(result.order.status, "PARTIALLY_FILLED");
  assert.equal(result.account.inventory, "100");
  assert.ok(Number(result.account.cash) > 0);
});
