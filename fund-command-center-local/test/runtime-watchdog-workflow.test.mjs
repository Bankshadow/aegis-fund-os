import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("native watchdog is read-only and fails closed until secrets exist", async () => {
  const source = await readFile(new URL("../../.github/workflows/runtime-watchdog.yml", import.meta.url), "utf8");
  assert.match(source, /AEGIS_AUTOMATION_STATUS_TOKEN/);
  assert.match(source, /\/api\/automation\/runtime-status/);
  assert.match(source, /issues: write/);
  assert.match(source, /skipped until AEGIS_AUTOMATION_STATUS_URL/);
  assert.doesNotMatch(source, /cron\/grid-sync/);
  assert.doesNotMatch(source, /BINANCE_TESTNET_API/);
  assert.doesNotMatch(source, /placeOrder|cancelTestnetOrder/);
});
