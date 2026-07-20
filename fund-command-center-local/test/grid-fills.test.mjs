import assert from "node:assert/strict";
import test from "node:test";
import { aggregateFillsByOrder, MIXED_COMMISSION_ASSET } from "../src/lib/grid-fills.ts";

const trade = (over) => ({
  orderId: over.orderId ?? 1,
  qty: over.qty ?? "0.010",
  quoteQty: over.quoteQty ?? "640",
  commission: over.commission ?? "0.00001",
  commissionAsset: over.commissionAsset ?? "BTC",
});

test("a single trade becomes one execution record", () => {
  const fills = aggregateFillsByOrder([
    trade({ orderId: 12, qty: "0.010", quoteQty: "640", commission: "0.00001", commissionAsset: "BTC" }),
  ]);
  const fill = fills.get("12");
  assert.equal(fill.filledQuantity, "0.01");
  assert.equal(fill.avgFillPrice, "64000"); // 640 / 0.010
  assert.equal(fill.commission, "0.00001");
  assert.equal(fill.commissionAsset, "BTC");
});

test("partial fills across trades sum into a quantity-weighted average price", () => {
  const fills = aggregateFillsByOrder([
    trade({ orderId: 7, qty: "0.010", quoteQty: "600", commission: "0.00001", commissionAsset: "BTC" }),
    trade({ orderId: 7, qty: "0.030", quoteQty: "2100", commission: "0.00003", commissionAsset: "BTC" }),
  ]);
  const fill = fills.get("7");
  assert.equal(fill.filledQuantity, "0.04");
  // (600 + 2100) / (0.010 + 0.030) = 2700 / 0.04 = 67500
  assert.equal(fill.avgFillPrice, "67500");
  assert.equal(fill.commission, "0.00004");
});

test("trades are grouped per order", () => {
  const fills = aggregateFillsByOrder([
    trade({ orderId: 1, qty: "0.010", quoteQty: "640" }),
    trade({ orderId: 2, qty: "0.020", quoteQty: "1300" }),
  ]);
  assert.equal(fills.size, 2);
  assert.equal(fills.get("1").filledQuantity, "0.01");
  assert.equal(fills.get("2").filledQuantity, "0.02");
});

test("a sell books commission in the quote asset", () => {
  const fills = aggregateFillsByOrder([
    trade({ orderId: 9, qty: "0.010", quoteQty: "650", commission: "0.65", commissionAsset: "USDT" }),
  ]);
  assert.equal(fills.get("9").commissionAsset, "USDT");
  assert.equal(fills.get("9").commission, "0.65");
});

test("mixed commission assets are flagged rather than summed", () => {
  const fills = aggregateFillsByOrder([
    trade({ orderId: 5, commission: "0.00001", commissionAsset: "BTC" }),
    trade({ orderId: 5, commission: "0.10", commissionAsset: "BNB" }),
  ]);
  const fill = fills.get("5");
  assert.equal(fill.commissionAsset, MIXED_COMMISSION_ASSET);
  assert.equal(fill.commission, ""); // unvalued → downstream falls back to estimate
});

test("a zero-quantity trade set does not divide by zero", () => {
  const fills = aggregateFillsByOrder([trade({ orderId: 3, qty: "0", quoteQty: "0" })]);
  assert.equal(fills.get("3").avgFillPrice, "0");
});
