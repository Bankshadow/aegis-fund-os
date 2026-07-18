import assert from "node:assert/strict";
import test from "node:test";
import { GridBotRepository } from "../src/lib/grid-bot-repository.ts";

const botRow = (over = {}) => ({
  id: "BOT-1",
  name: "Testnet grid",
  environment: "BINANCE_TESTNET",
  pair: "BTCUSDT",
  configuration_json: "{}",
  state: "APPROVED",
  runtime_state: over.runtime_state ?? "RUNNING",
  maker_id: "maker@x",
  checker_id: "checker@x",
  version: over.version ?? 5,
  created_at: "2026-07-18T00:00:00Z",
  updated_at: "2026-07-18T00:00:00Z",
});

// Minimal D1 fake: routes queries by SQL substring and captures batches.
class FakeD1 {
  constructor({ bot, orders, execution }) {
    this.bot = bot;
    this.orders = orders ?? [];
    this.execution = execution; // {id} or undefined
    this.batches = [];
  }
  prepare(sql) {
    const db = this;
    return {
      _sql: sql,
      _binds: [],
      bind(...values) {
        this._binds = values;
        return this;
      },
      async first() {
        if (sql.includes("FROM grid_bots WHERE id")) return db.bot;
        if (sql.includes("FROM grid_bot_executions")) return db.execution ?? null;
        return null;
      },
      async all() {
        if (sql.includes("FROM grid_bot_audit")) return { results: [] };
        if (sql.includes("FROM grid_bot_orders")) return { results: db.orders };
        return { results: [] };
      },
      async run() {
        return { success: true };
      },
    };
  }
  async batch(statements) {
    this.batches.push(statements);
    return statements.map(() => ({ success: true }));
  }
}

test("recordGridSync persists a fill, a placement, a version bump and one audit event", async () => {
  const db = new FakeD1({ bot: botRow(), execution: { id: "EXE-1" } });
  const repo = new GridBotRepository(db);
  const result = await repo.recordGridSync("BOT-1", "checker@x", {
    statusUpdates: [],
    filled: [{ clientOrderId: "b-high" }],
    reconciliationRequired: [],
    placements: [
      {
        clientOrderId: "aegis-r-abc",
        exchangeOrderId: "555",
        side: "SELL",
        price: "101",
        quantity: "0.010",
        gridIndex: 2,
        status: "NEW",
      },
    ],
  });
  assert.equal(result.changed, true);
  assert.equal(result.bot.version, 6);
  assert.equal(db.batches.length, 1);
  const sqls = db.batches[0].map((s) => s._sql);
  assert.ok(sqls.some((s) => s.includes("SET status='FILLED'")));
  assert.ok(sqls.some((s) => s.includes("INSERT INTO grid_bot_orders")));
  assert.ok(sqls.some((s) => s.includes("UPDATE grid_bots SET version")));
  assert.equal(sqls.filter((s) => s.includes("INSERT INTO grid_bot_audit")).length, 1);
});

test("recordGridSync writes nothing when the poll found no change", async () => {
  const db = new FakeD1({ bot: botRow(), execution: { id: "EXE-1" } });
  const repo = new GridBotRepository(db);
  const result = await repo.recordGridSync("BOT-1", "checker@x", {
    statusUpdates: [],
    filled: [],
    reconciliationRequired: [],
    placements: [],
  });
  assert.equal(result.changed, false);
  assert.equal(db.batches.length, 0);
});

test("recordGridSync refuses to reconcile a bot that is not RUNNING", async () => {
  const db = new FakeD1({ bot: botRow({ runtime_state: "PAUSED" }), execution: { id: "EXE-1" } });
  const repo = new GridBotRepository(db);
  await assert.rejects(
    () =>
      repo.recordGridSync("BOT-1", "checker@x", {
        statusUpdates: [],
        filled: [{ clientOrderId: "x" }],
        reconciliationRequired: [],
        placements: [],
      }),
    /Only a RUNNING bot can reconcile/,
  );
});

test("recordGridSync fails closed when there is no active execution", async () => {
  const db = new FakeD1({ bot: botRow(), execution: undefined });
  const repo = new GridBotRepository(db);
  await assert.rejects(
    () =>
      repo.recordGridSync("BOT-1", "checker@x", {
        statusUpdates: [],
        filled: [{ clientOrderId: "x" }],
        reconciliationRequired: [],
        placements: [],
      }),
    /No active Testnet execution/,
  );
});
