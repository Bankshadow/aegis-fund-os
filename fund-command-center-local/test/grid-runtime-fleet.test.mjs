import assert from "node:assert/strict";
import test from "node:test";
import {
  dryLoopPolicyFromEnv,
  reconcileBotWithOptionalDryLoop,
} from "../src/lib/grid-runtime-fleet.ts";

const bot = {
  id: "BOT-dry", name: "Dry", environment: "BINANCE_TESTNET", pair: "BTCUSDT", configuration: {},
  state: "APPROVED", runtimeState: "RUNNING", makerId: "maker", version: 1,
  createdAt: "2026-07-23T00:00:00Z", updatedAt: "2026-07-23T00:00:00Z",
};

const orders = [
  { id: "a", executionId: "x", botId: bot.id, symbol: "BTCUSDT", exchangeOrderId: "1", clientOrderId: "buy", gridIndex: 1, side: "BUY", price: "99", quantity: "0.01", status: "NEW", createdAt: "x", updatedAt: "x" },
  { id: "b", executionId: "x", botId: bot.id, symbol: "BTCUSDT", exchangeOrderId: "2", clientOrderId: "sell", gridIndex: 2, side: "SELL", price: "101", quantity: "0.01", status: "NEW", createdAt: "x", updatedAt: "x" },
];

class SafetyRepo {
  constructor() {
    this.runs = [];
    this.finished = [];
  }
  async getRuntimeSafetyControl() { return { placementDisabled: false, consecutiveFailures: 0 }; }
  async acquireRuntimeLease() { return true; }
  async renewRuntimeLease() { return true; }
  async releaseRuntimeLease() { this.released = true; }
  async countOpenTestnetOrders() { return 0; }
  async startRuntimeRun() { this.runs.push("started"); return `RUN-${this.runs.length}`; }
  async finishRuntimeRun(id, status, reason, placements, route, deferred) {
    this.finished.push({ id, status, reason, placements, route, deferred });
  }
  async recordRuntimeSafety() {}
  async listOrders() { return orders; }
  async recordGridSync() { return { changed: true, bot, orders: [] }; }
}

test("dry-loop policy defaults off and caps max rounds", () => {
  const off = dryLoopPolicyFromEnv({});
  assert.equal(off.enabled, false);
  assert.equal(off.maxRounds, 3);
  const on = dryLoopPolicyFromEnv({
    GRID_RECONCILE_DRY_LOOP: "true",
    GRID_RECONCILE_MAX_ROUNDS: "99",
  });
  assert.equal(on.enabled, true);
  assert.equal(on.maxRounds, 5);
});

test("disabled dry-loop performs a single pass and persists route on finish", async () => {
  const repo = new SafetyRepo();
  const outcome = await reconcileBotWithOptionalDryLoop(
    repo,
    bot,
    "operator",
    {
      getStatus: async () => ({
        checkedAt: new Date().toISOString(),
        openOrders: [{ clientOrderId: "sell", status: "NEW" }],
        trades: [{ orderId: "1" }],
      }),
      placeOrder: async () => ({ orderId: "3", status: "NEW" }),
    },
    { maxPlacementsPerRun: 2 },
    { enabled: false, dryRounds: 1, maxRounds: 3 },
  );
  assert.equal(outcome.rounds, 1);
  assert.equal(outcome.stopReason, "single_pass");
  assert.equal(outcome.result.route.severity, "ok");
  assert.equal(repo.finished[0].route.severity, "ok");
  assert.equal(repo.finished[0].deferred, 0);
});

test("enabled dry-loop drains deferred work across capped passes", async () => {
  const repo = new SafetyRepo();
  let calls = 0;
  const outcome = await reconcileBotWithOptionalDryLoop(
    repo,
    bot,
    "operator",
    {
      getStatus: async () => ({
        checkedAt: new Date().toISOString(),
        openOrders: [{ clientOrderId: "sell", status: "NEW" }],
        trades: [{ orderId: "1" }],
      }),
      placeOrder: async () => ({ orderId: `P-${++calls}`, status: "NEW" }),
    },
    { maxPlacementsPerRun: 0 },
    { enabled: true, dryRounds: 1, maxRounds: 2 },
  );
  assert.equal(outcome.rounds, 2);
  assert.equal(outcome.stopReason, "max_rounds");
  assert.equal(outcome.history.every((item) => item.severity === "deferred"), true);
  assert.equal(repo.finished.length, 2);
  assert.equal(repo.finished[0].route.severity, "deferred");
});

test("dry-loop telemetry flags backlog when max_rounds ends deferred", async () => {
  const { summarizeDryLoopTelemetry } = await import("../src/lib/grid-runtime-fleet.ts");
  const telemetry = summarizeDryLoopTelemetry(true, [
    {
      botId: "BOT-a",
      rounds: 3,
      stopReason: "max_rounds",
      history: [
        { severity: "deferred", action: "retry_next", workRemaining: true },
        { severity: "deferred", action: "retry_next", workRemaining: true },
        { severity: "deferred", action: "retry_next", workRemaining: true },
      ],
    },
    {
      botId: "BOT-b",
      rounds: 1,
      stopReason: "dry",
      history: [{ severity: "ok", action: "continue", workRemaining: false }],
    },
  ]);
  assert.equal(telemetry.bots, 2);
  assert.equal(telemetry.totalPasses, 4);
  assert.equal(telemetry.avgPassesPerBot, 2);
  assert.equal(telemetry.maxPasses, 3);
  assert.equal(telemetry.deferredEnds, 1);
  assert.equal(telemetry.drainedEnds, 1);
  assert.equal(telemetry.backlogStillDeferred, true);
  assert.equal(telemetry.stopReasons.max_rounds, 1);
});
