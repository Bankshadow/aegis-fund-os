import assert from "node:assert/strict";
import test from "node:test";
import {
  applyPaperPriceEvent,
  calculatePaperGrid,
  simulatePaperFill,
} from "../src/lib/aot-paper-domain.ts";

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

test("volume-aware price event partially fills then creates one paired order only after completion", () => {
  const grid = calculatePaperGrid(config);
  const account = {
    initialCash: "100000",
    cash: "100000",
    inventory: "3000",
    averageCost: "40",
    realizedGridProfit: "0",
    realizedAssetPnl: "0",
    costs: "0",
    slippage: "0",
    currentPrice: "40",
    maxDrawdown: "0",
    completedCycles: 0,
  };
  const buy = {
    id: "BUY-1",
    gridIndex: 1,
    side: "BUY",
    limitPrice: "36.00",
    originalQuantity: "600",
    filledQuantity: "0",
    remainingQuantity: "600",
    averageFillPrice: "0",
    status: "OPEN",
    reservedAmount: "21600",
  };
  const partial = applyPaperPriceEvent([buy], account, grid.levels, {
    eventId: "00000000-0000-4000-8000-000000000001",
    price: "36.00",
    availableVolume: "300",
    fillModel: "VOLUME_AWARE",
    oneWayCostPct: "0.20",
    slippagePct: "0.05",
  });
  assert.equal(partial.orders[0].status, "PARTIALLY_FILLED");
  assert.equal(partial.pairedOrders.length, 0);
  const complete = applyPaperPriceEvent(partial.orders, partial.account, grid.levels, {
    eventId: "00000000-0000-4000-8000-000000000002",
    price: "36.00",
    availableVolume: "300",
    fillModel: "VOLUME_AWARE",
    oneWayCostPct: "0.20",
    slippagePct: "0.05",
  });
  assert.equal(complete.orders[0].status, "FILLED");
  assert.equal(complete.pairedOrders.length, 1);
  assert.equal(complete.pairedOrders[0].side, "SELL");
});

test("a completed sell grid cycle books grid profit separately from asset holding P&L", () => {
  const grid = calculatePaperGrid(config);
  const sell = {
    id: "SELL-1",
    gridIndex: 6,
    side: "SELL",
    limitPrice: "41.00",
    originalQuantity: "600",
    filledQuantity: "0",
    remainingQuantity: "600",
    averageFillPrice: "0",
    status: "OPEN",
    reservedAmount: "24600",
  };
  const account = {
    initialCash: "100000",
    cash: "100000",
    inventory: "3000",
    averageCost: "40",
    realizedGridProfit: "0",
    realizedAssetPnl: "0",
    costs: "0",
    slippage: "0",
    currentPrice: "40",
    maxDrawdown: "0",
    completedCycles: 0,
  };
  const result = applyPaperPriceEvent([sell], account, grid.levels, {
    eventId: "00000000-0000-4000-8000-000000000003",
    price: "41.00",
    availableVolume: "1000",
    fillModel: "TOUCH",
    oneWayCostPct: "0.20",
    slippagePct: "0.05",
  });
  assert.equal(result.account.completedCycles, 1);
  assert.ok(Number(result.account.realizedGridProfit) > 0);
  assert.ok(Number(result.account.realizedAssetPnl) > 0);
});
