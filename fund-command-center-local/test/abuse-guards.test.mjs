import assert from "node:assert/strict";
import test from "node:test";
import {
  DEFAULT_LIMITS,
  assertBotCreationAllowed,
  assertOrderPlacementAllowed,
  resolveGuardLimits,
  windowStart,
} from "../src/lib/abuse-guards.ts";

test("defaults apply when env is absent or invalid", () => {
  assert.deepEqual(resolveGuardLimits(undefined), DEFAULT_LIMITS);
  assert.deepEqual(
    resolveGuardLimits({ AEGIS_MAX_BOTS: "0", AEGIS_MAX_OPEN_ORDERS: "abc", AEGIS_CREATE_WINDOW_MINUTES: "-5" }),
    DEFAULT_LIMITS,
  );
});

test("env overrides are honoured", () => {
  const limits = resolveGuardLimits({
    AEGIS_MAX_BOTS: "3",
    AEGIS_MAX_CREATES_PER_WINDOW: "2",
    AEGIS_CREATE_WINDOW_MINUTES: "30",
    AEGIS_MAX_OPEN_ORDERS: "10",
  });
  assert.deepEqual(limits, { maxBots: 3, maxCreatesPerWindow: 2, windowMinutes: 30, maxOpenOrders: 10 });
});

test("creation is allowed below both caps", () => {
  assert.doesNotThrow(() => assertBotCreationAllowed({ totalBots: 5, recentCreates: 1 }, DEFAULT_LIMITS));
});

test("creation fails closed at the total-bot cap", () => {
  assert.throws(
    () => assertBotCreationAllowed({ totalBots: DEFAULT_LIMITS.maxBots, recentCreates: 0 }, DEFAULT_LIMITS),
    /Bot limit reached/,
  );
});

test("creation fails closed at the rate limit", () => {
  assert.throws(
    () =>
      assertBotCreationAllowed(
        { totalBots: 1, recentCreates: DEFAULT_LIMITS.maxCreatesPerWindow },
        DEFAULT_LIMITS,
      ),
    /Too many bots created recently/,
  );
});

test("placement is allowed when the incoming grid still fits", () => {
  assert.doesNotThrow(() =>
    assertOrderPlacementAllowed({ openOrders: 100, incoming: 20 }, DEFAULT_LIMITS),
  );
});

test("placement fails closed when the grid would cross the open-order cap", () => {
  assert.throws(
    () => assertOrderPlacementAllowed({ openOrders: 115, incoming: 20 }, DEFAULT_LIMITS),
    /Open Testnet order limit reached/,
  );
});

test("windowStart is the configured number of minutes back", () => {
  const now = new Date("2026-07-19T12:00:00.000Z");
  assert.equal(windowStart({ ...DEFAULT_LIMITS, windowMinutes: 10 }, now), "2026-07-19T11:50:00.000Z");
});
