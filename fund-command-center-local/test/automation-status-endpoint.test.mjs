import assert from "node:assert/strict";
import test from "node:test";
import { handleAutomationStatusRequest } from "../src/lib/automation-status-endpoint.ts";

const db = {
  prepare() {
    return {
      bind() { return this; },
      async all() { return { success: true, results: [] }; },
      async first() { return null; },
      async run() { return { success: true, meta: { changes: 0 } }; },
    };
  },
  async batch() { return []; },
};

test("automation status is GET-only and token-gated", async () => {
  const env = { AEGIS_AUTOMATION_STATUS_TOKEN: "token", GOVERNANCE_DB: db };
  assert.equal((await handleAutomationStatusRequest(new Request("https://x/api/automation/runtime-status"), env)).status, 401);
  assert.equal((await handleAutomationStatusRequest(new Request("https://x/api/automation/runtime-status", { method: "POST" }), env)).status, 405);
});

test("automation status is read-only and reports safe hold", async () => {
  const res = await handleAutomationStatusRequest(new Request("https://x/api/automation/runtime-status", {
    headers: { "x-aegis-automation-token": "token" },
  }), { AEGIS_AUTOMATION_STATUS_TOKEN: "token", GRID_TESTNET_KILL_SWITCH: "true", GOVERNANCE_DB: db });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.schema, "aegis.automation-status.v1");
  assert.equal(body.mode, "SAFE_HOLD");
  assert.deepEqual(body.bots, { total: 0, running: 0 });
});
