import assert from "node:assert/strict";
import test from "node:test";
import { handleGridCronRequest } from "../src/lib/grid-cron-endpoint.ts";

const post = (headers = {}) =>
  new Request("https://x/api/cron/grid-sync", { method: "POST", headers });

// D1 fake with no bots so reconcileAll returns [] without any exchange call.
const emptyDb = {
  prepare() {
    return {
      bind() {
        return this;
      },
      async all() {
        return { results: [] };
      },
      async first() {
        return null;
      },
      async run() {
        return { success: true };
      },
    };
  },
  async batch() {
    return [];
  },
};

test("rejects a non-POST request", async () => {
  const res = await handleGridCronRequest(new Request("https://x/api/cron/grid-sync"), {
    GRID_CRON_ENABLED: "true",
    GRID_CRON_SECRET: "s",
  });
  assert.equal(res.status, 405);
});

test("is a 200 no-op when GRID_CRON_ENABLED is not 'true'", async () => {
  const res = await handleGridCronRequest(post(), { GRID_CRON_SECRET: "s", GOVERNANCE_DB: emptyDb });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.enabled, false);
  assert.deepEqual(body.results, []);
});

test("rejects a wrong or missing shared secret when enabled", async () => {
  const wrong = await handleGridCronRequest(post({ "x-grid-cron-secret": "nope" }), {
    GRID_CRON_ENABLED: "true",
    GRID_CRON_SECRET: "correct",
    GOVERNANCE_DB: emptyDb,
  });
  assert.equal(wrong.status, 401);
  const missing = await handleGridCronRequest(post(), {
    GRID_CRON_ENABLED: "true",
    GRID_CRON_SECRET: "correct",
    GOVERNANCE_DB: emptyDb,
  });
  assert.equal(missing.status, 401);
});

test("fails closed with 503 when governance storage is unavailable", async () => {
  const res = await handleGridCronRequest(post({ "x-grid-cron-secret": "s" }), {
    GRID_CRON_ENABLED: "true",
    GRID_CRON_SECRET: "s",
  });
  assert.equal(res.status, 503);
});

test("runs the batch reconcile with a valid secret and reports enabled", async () => {
  const res = await handleGridCronRequest(post({ "x-grid-cron-secret": "s" }), {
    GRID_CRON_ENABLED: "true",
    GRID_CRON_SECRET: "s",
    GOVERNANCE_DB: emptyDb,
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.enabled, true);
  assert.deepEqual(body.results, []); // no running bots → no exchange calls
  assert.ok(body.ranAt);
});
