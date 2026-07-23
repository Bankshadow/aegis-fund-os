import assert from "node:assert/strict";
import test from "node:test";
import { GridRuntimeSafetyError, reconcileTestnetGridSafely, runtimeSafetyPolicyFromEnv } from "../src/lib/grid-runtime-safety.ts";

const bot = {
  id: "BOT-safe", name: "Safe", environment: "BINANCE_TESTNET", pair: "BTCUSDT", configuration: {},
  state: "APPROVED", runtimeState: "RUNNING", makerId: "maker", version: 1,
  createdAt: "2026-07-23T00:00:00Z", updatedAt: "2026-07-23T00:00:00Z",
};

const orders = [
  { id: "a", executionId: "x", botId: bot.id, symbol: "BTCUSDT", exchangeOrderId: "1", clientOrderId: "buy", gridIndex: 1, side: "BUY", price: "99", quantity: "0.01", status: "NEW", createdAt: "x", updatedAt: "x" },
  { id: "b", executionId: "x", botId: bot.id, symbol: "BTCUSDT", exchangeOrderId: "2", clientOrderId: "sell", gridIndex: 2, side: "SELL", price: "101", quantity: "0.01", status: "NEW", createdAt: "x", updatedAt: "x" },
];

class SafetyRepo {
  constructor({ lease = true, disabled = false } = {}) {
    this.lease = lease; this.disabled = disabled; this.runs = []; this.safety = [];
  }
  async getRuntimeSafetyControl() { return { placementDisabled: this.disabled, consecutiveFailures: 0 }; }
  async acquireRuntimeLease() { return this.lease; }
  async renewRuntimeLease() { this.renewed = (this.renewed ?? 0) + 1; return true; }
  async releaseRuntimeLease() { this.released = true; }
  async countOpenTestnetOrders() { return 0; }
  async startRuntimeRun() { this.runs.push("started"); return "RUN-1"; }
  async finishRuntimeRun(id, status, reason, placements, route, deferred) {
    this.runs.push({ id, status, reason, placements, route, deferred });
  }
  async recordRuntimeSafety(id, actor, item) { this.safety.push(item); }
  async listOrders() { return orders; }
  async recordGridSync(id, actor, sync) { this.sync = sync; return { changed: true, bot, orders: [] }; }
}

const filledDeps = {
  getStatus: async () => ({ checkedAt: new Date().toISOString(), openOrders: [{ clientOrderId: "sell", status: "NEW" }], trades: [{ orderId: "1" }] }),
  placeOrder: async () => ({ orderId: "3", status: "NEW" }),
};

test("global kill switch blocks before a lease, durable run, or exchange call", async () => {
  const repo = new SafetyRepo();
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", filledDeps, { killSwitch: true }), GridRuntimeSafetyError);
  assert.equal(repo.runs.length, 0);
  assert.equal(repo.released, undefined);
});

test("an active lease blocks a concurrent reconciler before exchange placement", async () => {
  const repo = new SafetyRepo({ lease: false });
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", filledDeps), /active lease/);
  assert.equal(repo.runs.length, 0);
});

test("successful run is durable, releases its lease, and clears the failure counter", async () => {
  const repo = new SafetyRepo();
  const result = await reconcileTestnetGridSafely(repo, bot, "operator", filledDeps, { maxPlacementsPerRun: 2 });
  assert.equal(result.summary.placed, 1);
  assert.equal(repo.runs.at(-1).status, "SUCCEEDED");
  assert.equal(repo.runs.at(-1).route.severity, "ok");
  assert.equal(repo.safety.at(-1).failed, false);
  assert.equal(repo.released, true);
  assert.equal(repo.renewed, 1);
});

// The budget throttles a run; it does not fail one. Rejecting the whole run
// deadlocked a bot whose backlog exceeded the cap: the backlog never drained, so
// every later run failed identically until the circuit breaker halted a healthy
// bot. Observed live on BOT-cafaa7ec (15 replenishments vs a cap of 8).
test("an exhausted placement budget defers work instead of failing the run", async () => {
  const repo = new SafetyRepo();
  let placed = 0;
  const result = await reconcileTestnetGridSafely(repo, bot, "operator", {
    ...filledDeps, placeOrder: async () => { placed += 1; return { orderId: "3", status: "NEW" }; },
  }, { maxPlacementsPerRun: 0 });
  assert.equal(placed, 0);
  assert.equal(result.summary.placed, 0);
  assert.equal(result.summary.deferred, 1);
  assert.equal(repo.runs.at(-1).status, "SUCCEEDED");
  assert.equal(repo.safety.at(-1).failed, false);
  assert.equal(repo.released, true);
});

test("a deferred replenishment leaves its source fill un-terminal for the next run", async () => {
  const repo = new SafetyRepo();
  await reconcileTestnetGridSafely(repo, bot, "operator", filledDeps, { maxPlacementsPerRun: 0 });
  // Committing the fill without its paired order would strand the grid: the next
  // run would see a terminal row and never replenish it.
  assert.equal(repo.sync.filled.length, 0);
});

// Schema drift is a deployment problem, not a bot malfunction. It must fail closed
// (no lease means no placement) but say what to do, and must not be recorded as a
// consecutive failure — otherwise a pending migration halts the whole fleet.
test("missing safety tables fail closed with an actionable message and no failure count", async () => {
  const repo = new SafetyRepo();
  repo.getRuntimeSafetyControl = async () => {
    throw new Error("D1_ERROR: no such table: grid_runtime_controls: SQLITE_ERROR");
  };
  await assert.rejects(
    () => reconcileTestnetGridSafely(repo, bot, "operator", filledDeps),
    (error) => error instanceof GridRuntimeSafetyError && /migrations apply/.test(error.message),
  );
  assert.equal(repo.runs.length, 0);
  assert.equal(repo.safety.length, 0);
});

test("a failure to open the run record releases the lease it already holds", async () => {
  const repo = new SafetyRepo();
  repo.startRuntimeRun = async () => {
    throw new Error("D1_ERROR: no such table: grid_runtime_runs: SQLITE_ERROR");
  };
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", filledDeps), /migrations apply/);
  // Without the release a leaked lease would block this bot until expiry.
  assert.equal(repo.released, true);
});

test("invalid environment values resolve to conservative numeric defaults", () => {
  const policy = runtimeSafetyPolicyFromEnv({ GRID_TESTNET_KILL_SWITCH: "anything", GRID_MAX_REPLENISHMENTS_PER_RUN: "no" });
  assert.equal(policy.killSwitch, false);
  assert.equal(Number.isNaN(policy.maxPlacementsPerRun), true);
});

test("stale exchange evidence fails closed before a placement", async () => {
  const repo = new SafetyRepo();
  let placed = 0;
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", {
    getStatus: async () => ({ checkedAt: "2000-01-01T00:00:00.000Z", openOrders: [], trades: [] }),
    placeOrder: async () => { placed += 1; return { orderId: "3", status: "NEW" }; },
  }), /stale or invalid/);
  assert.equal(placed, 0);
  assert.equal(repo.runs.at(-1).status, "FAILED");
});

test("open-order cap is rechecked immediately before placement", async () => {
  const repo = new SafetyRepo();
  repo.countOpenTestnetOrders = async () => 1;
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", filledDeps, { maxOpenOrders: 1 }), /Open-order safety cap/);
  assert.equal(repo.runs.at(-1).status, "FAILED");
});

test("future-dated exchange evidence also fails closed", async () => {
  const repo = new SafetyRepo();
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", {
    getStatus: async () => ({ checkedAt: new Date(Date.now() + 60_000).toISOString(), openOrders: [], trades: [] }),
    placeOrder: async () => ({ orderId: "3", status: "NEW" }),
  }), /stale or invalid/);
  assert.equal(repo.runs.at(-1).status, "FAILED");
});

test("lease renewal failure blocks placement and records a failed run", async () => {
  const repo = new SafetyRepo();
  repo.renewRuntimeLease = async () => false;
  let placed = 0;
  await assert.rejects(() => reconcileTestnetGridSafely(repo, bot, "operator", {
    ...filledDeps, placeOrder: async () => { placed += 1; return { orderId: "3", status: "NEW" }; },
  }), /lease expired/);
  assert.equal(placed, 0);
  assert.equal(repo.runs.at(-1).status, "FAILED");
});
