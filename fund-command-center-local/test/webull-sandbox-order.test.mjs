import assert from "node:assert/strict";
import test from "node:test";

import { placeWebullSandboxTestOrder } from "../src/lib/webull-sandbox.server.ts";

test("Webull sandbox order transport is disabled unless explicitly enabled server-side", async () => {
  delete process.env.WEBULL_SANDBOX_ORDER_TEST_ENABLED;
  const result = await placeWebullSandboxTestOrder({
    accountId: "sandbox",
    symbol: "AAPL",
    side: "BUY",
    limitPrice: "1.00",
    quantity: "1",
  });
  assert.equal(result.status, "disabled");
});

test("Webull sandbox order caps quantity and notional before network transport", async () => {
  process.env.WEBULL_SANDBOX_ORDER_TEST_ENABLED = "true";
  process.env.WEBULL_SANDBOX_APP_KEY = "key";
  process.env.WEBULL_SANDBOX_APP_SECRET = "secret";
  process.env.WEBULL_SANDBOX_ACCESS_TOKEN = "token";
  const result = await placeWebullSandboxTestOrder({
    accountId: "sandbox",
    symbol: "AAPL",
    side: "BUY",
    limitPrice: "100.00",
    quantity: "1",
  });
  assert.equal(result.status, "rejected");
  assert.match(result.message, /capped/);
  delete process.env.WEBULL_SANDBOX_ORDER_TEST_ENABLED;
  delete process.env.WEBULL_SANDBOX_APP_KEY;
  delete process.env.WEBULL_SANDBOX_APP_SECRET;
  delete process.env.WEBULL_SANDBOX_ACCESS_TOKEN;
});
