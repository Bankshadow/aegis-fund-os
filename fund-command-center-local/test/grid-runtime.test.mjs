import assert from "node:assert/strict";
import test from "node:test";
import {
  planGridReconciliation,
  replenishmentClientOrderId,
} from "../src/lib/grid-runtime.ts";

const BOT_ID = "BOT-grid-1";

// A small 4-line ladder around a mid price: two BUYs below, two SELLs above.
const order = (over = {}) => ({
  id: over.clientOrderId ?? "row",
  executionId: "EXE-1",
  botId: BOT_ID,
  symbol: "BTCUSDT",
  exchangeOrderId: over.exchangeOrderId ?? "1",
  clientOrderId: over.clientOrderId ?? "c1",
  gridIndex: over.gridIndex ?? 1,
  side: over.side ?? "BUY",
  price: over.price ?? "100",
  quantity: over.quantity ?? "0.010",
  status: over.status ?? "NEW",
  createdAt: "2026-07-18T00:00:00Z",
  updatedAt: "2026-07-18T00:00:00Z",
});

const ledger = () => [
  order({ clientOrderId: "b-low", exchangeOrderId: "11", side: "BUY", price: "98", gridIndex: 1 }),
  order({ clientOrderId: "b-high", exchangeOrderId: "12", side: "BUY", price: "99", gridIndex: 2 }),
  order({ clientOrderId: "s-low", exchangeOrderId: "13", side: "SELL", price: "101", gridIndex: 3 }),
  order({ clientOrderId: "s-high", exchangeOrderId: "14", side: "SELL", price: "102", gridIndex: 4 }),
];

const openAll = (orders) => orders.map((o) => ({ clientOrderId: o.clientOrderId, status: "NEW" }));

test("no change when every order is still open on the exchange", async () => {
  const orders = ledger();
  const plan = await planGridReconciliation(BOT_ID, orders, openAll(orders), []);
  assert.equal(plan.filled.length, 0);
  assert.equal(plan.replenishments.length, 0);
  assert.equal(plan.statusUpdates.length, 0);
  assert.equal(plan.reconciliationRequired.length, 0);
});

test("a filled BUY places a SELL one grid line up with the same quantity", async () => {
  const orders = ledger();
  // b-high (BUY @99) filled: gone from open orders, present in trades.
  const open = openAll(orders).filter((o) => o.clientOrderId !== "b-high");
  const plan = await planGridReconciliation(BOT_ID, orders, open, [{ exchangeOrderId: "12" }]);
  assert.deepEqual(plan.filled.map((f) => f.clientOrderId), ["b-high"]);
  assert.equal(plan.replenishments.length, 1);
  const r = plan.replenishments[0];
  assert.equal(r.side, "SELL");
  assert.equal(r.price, "101"); // next ladder line above 99
  assert.equal(r.quantity, "0.010");
  assert.equal(r.sourceClientOrderId, "b-high");
  assert.equal(r.clientOrderId, await replenishmentClientOrderId(BOT_ID, "b-high", "SELL", "101"));
});

test("a filled SELL places a BUY one grid line down", async () => {
  const orders = ledger();
  const open = openAll(orders).filter((o) => o.clientOrderId !== "s-low");
  const plan = await planGridReconciliation(BOT_ID, orders, open, [{ exchangeOrderId: "13" }]);
  assert.equal(plan.replenishments.length, 1);
  const r = plan.replenishments[0];
  assert.equal(r.side, "BUY");
  assert.equal(r.price, "99"); // next ladder line below 101
});

test("a filled BUY at the top grid line has no line above and places nothing", async () => {
  // A BUY sitting at the highest ladder price harvests upward but there is no
  // line above it, so the grid ends on that side and nothing is placed.
  const orders = [
    order({ clientOrderId: "b-low", exchangeOrderId: "11", side: "BUY", price: "98", gridIndex: 1 }),
    order({ clientOrderId: "b-top", exchangeOrderId: "12", side: "BUY", price: "102", gridIndex: 2 }),
  ];
  const open = openAll(orders).filter((o) => o.clientOrderId !== "b-top");
  const plan = await planGridReconciliation(BOT_ID, orders, open, [{ exchangeOrderId: "12" }]);
  assert.deepEqual(plan.filled.map((f) => f.clientOrderId), ["b-top"]);
  assert.equal(plan.replenishments.length, 0); // boundary — harvest ends this side
});

test("an order missing from the exchange with no fill is flagged for reconciliation", async () => {
  const orders = ledger();
  // b-low vanished with no matching trade: externally cancelled / unknown.
  const open = openAll(orders).filter((o) => o.clientOrderId !== "b-low");
  const plan = await planGridReconciliation(BOT_ID, orders, open, []);
  assert.deepEqual(plan.reconciliationRequired.map((o) => o.clientOrderId), ["b-low"]);
  assert.equal(plan.replenishments.length, 0);
  assert.equal(plan.filled.length, 0);
});

test("replenishment is idempotent when the paired order already exists", async () => {
  const orders = ledger();
  // The SELL @101 that a filled b-high would create already exists in the ledger
  // (deterministic id), so a replayed sync must not place a second one.
  const dupId = await replenishmentClientOrderId(BOT_ID, "b-high", "SELL", "101");
  orders.push(order({ clientOrderId: dupId, exchangeOrderId: "99", side: "SELL", price: "101", status: "NEW", gridIndex: 3 }));
  const open = openAll(orders).filter((o) => o.clientOrderId !== "b-high");
  const plan = await planGridReconciliation(BOT_ID, orders, open, [{ exchangeOrderId: "12" }]);
  assert.deepEqual(plan.filled.map((f) => f.clientOrderId), ["b-high"]);
  assert.equal(plan.replenishments.length, 0);
});

test("a partial fill updates status but does not replenish", async () => {
  const orders = ledger();
  const open = openAll(orders).map((o) =>
    o.clientOrderId === "b-high" ? { ...o, status: "PARTIALLY_FILLED" } : o,
  );
  const plan = await planGridReconciliation(BOT_ID, orders, open, []);
  assert.deepEqual(plan.statusUpdates, [{ clientOrderId: "b-high", status: "PARTIALLY_FILLED" }]);
  assert.equal(plan.replenishments.length, 0);
  assert.equal(plan.filled.length, 0);
});

test("already-terminal ledger rows are never reprocessed", async () => {
  const orders = ledger().map((o) => (o.clientOrderId === "b-low" ? { ...o, status: "FILLED" } : o));
  // b-low is FILLED and absent from open orders; it must not re-trigger anything.
  const open = openAll(orders).filter((o) => o.clientOrderId !== "b-low");
  const plan = await planGridReconciliation(BOT_ID, orders, open, [{ exchangeOrderId: "11" }]);
  assert.equal(plan.filled.length, 0);
  assert.equal(plan.replenishments.length, 0);
});
