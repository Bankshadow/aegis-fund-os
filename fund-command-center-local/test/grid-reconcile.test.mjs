import assert from "node:assert/strict";
import test from "node:test";
import {
  reconcileOneTestnetGrid,
  reconcileAllRunningTestnetGrids,
} from "../src/lib/grid-reconcile.ts";
import { replenishmentClientOrderId } from "../src/lib/grid-runtime.ts";

const botRecord = (over = {}) => ({
  id: over.id ?? "BOT-1",
  name: "Grid",
  environment: over.environment ?? "BINANCE_TESTNET",
  pair: over.pair ?? "BTCUSDT",
  configuration: {},
  state: "APPROVED",
  runtimeState: over.runtimeState ?? "RUNNING",
  makerId: "m",
  version: 5,
  createdAt: "2026-07-19T00:00:00Z",
  updatedAt: "2026-07-19T00:00:00Z",
});

const orderRow = (over) => ({
  id: over.clientOrderId,
  executionId: "EXE-1",
  botId: over.botId ?? "BOT-1",
  symbol: "BTCUSDT",
  exchangeOrderId: over.exchangeOrderId,
  clientOrderId: over.clientOrderId,
  gridIndex: over.gridIndex ?? 1,
  side: over.side,
  price: over.price,
  quantity: over.quantity ?? "0.010",
  status: over.status ?? "NEW",
  createdAt: "2026-07-19T00:00:00Z",
  updatedAt: "2026-07-19T00:00:00Z",
});

// Minimal repo fake: canned bots/orders, captures recordGridSync calls.
class FakeRepo {
  constructor({ bots = [], ordersByBot = {} }) {
    this.bots = bots;
    this.ordersByBot = ordersByBot;
    this.syncCalls = [];
  }
  async listBots() {
    return this.bots;
  }
  async listOrders(botId) {
    return this.ordersByBot[botId] ?? [];
  }
  async recordGridSync(botId, actorId, sync) {
    this.syncCalls.push({ botId, actorId, sync });
    const changed =
      sync.filled.length + sync.placements.length + sync.statusUpdates.length + sync.reconciliationRequired.length > 0;
    return { bot: {}, orders: [], changed };
  }
}

const depsThatPlace = (placed = []) => ({
  getStatus: async () => ({
    // b-high (BUY @99) filled: not open, has a matching trade.
    openOrders: [{ clientOrderId: "b-low", status: "NEW" }, { clientOrderId: "s-high", status: "NEW" }],
    trades: [{ orderId: "12" }],
  }),
  placeOrder: async (symbol, order) => {
    placed.push(order);
    return { orderId: 999, status: "NEW" };
  },
});

const ledgerForFill = () => [
  orderRow({ clientOrderId: "b-low", exchangeOrderId: "11", side: "BUY", price: "98" }),
  orderRow({ clientOrderId: "b-high", exchangeOrderId: "12", side: "BUY", price: "99" }),
  orderRow({ clientOrderId: "s-high", exchangeOrderId: "14", side: "SELL", price: "101" }),
];

test("reconcileOne places the replenishment for a fill and records the sync", async () => {
  const repo = new FakeRepo({ bots: [botRecord()], ordersByBot: { "BOT-1": ledgerForFill() } });
  const placed = [];
  const result = await reconcileOneTestnetGrid(repo, botRecord(), "checker@x", depsThatPlace(placed));
  assert.equal(result.summary.filled, 1);
  assert.equal(result.summary.placed, 1);
  assert.equal(placed.length, 1);
  assert.equal(placed[0].side, "SELL");
  // paired sell one line up from the filled buy @99 → 101
  assert.equal(placed[0].price, "101");
  assert.equal(placed[0].clientOrderId, await replenishmentClientOrderId("BOT-1", "b-high", "SELL", "101"));
  assert.equal(repo.syncCalls.length, 1);
});

test("reconcileOne refuses a non-RUNNING bot", async () => {
  const repo = new FakeRepo({});
  await assert.rejects(
    () => reconcileOneTestnetGrid(repo, botRecord({ runtimeState: "PAUSED" }), "x", depsThatPlace()),
    /Only a RUNNING bot/,
  );
});

test("reconcileAll only touches RUNNING testnet BTCUSDT bots and isolates failures", async () => {
  const bots = [
    botRecord({ id: "BOT-run", runtimeState: "RUNNING" }),
    botRecord({ id: "BOT-idle", runtimeState: "IDLE" }),
    botRecord({ id: "BOT-paper", environment: "PAPER" }),
    botRecord({ id: "BOT-eth", pair: "ETHUSDT" }),
  ];
  const repo = new FakeRepo({ bots, ordersByBot: { "BOT-run": ledgerForFill() } });
  const results = await reconcileAllRunningTestnetGrids(repo, "system:grid-cron", depsThatPlace());
  assert.equal(results.length, 1); // only BOT-run qualifies
  assert.equal(results[0].botId, "BOT-run");
  assert.equal(repo.syncCalls[0].actorId, "system:grid-cron");
});

test("reconcileAll reports a failing bot without aborting the batch", async () => {
  const bots = [botRecord({ id: "BOT-a" }), botRecord({ id: "BOT-b" })];
  const repo = new FakeRepo({ bots, ordersByBot: { "BOT-a": ledgerForFill(), "BOT-b": ledgerForFill() } });
  let calls = 0;
  const deps = {
    getStatus: async () => ({ openOrders: [], trades: [{ orderId: "12" }] }),
    placeOrder: async () => {
      calls += 1;
      if (calls === 1) throw new Error("exchange rejected");
      return { orderId: 1, status: "NEW" };
    },
  };
  const results = await reconcileAllRunningTestnetGrids(repo, "system:grid-cron", deps);
  assert.equal(results.length, 2);
  assert.equal(results.filter((r) => "error" in r).length, 1);
  assert.equal(results.filter((r) => "summary" in r).length, 1);
});
