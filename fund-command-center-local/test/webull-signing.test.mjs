import assert from "node:assert/strict";
import test from "node:test";

import { signWebullRequest, webullHmacSha1Base64 } from "../src/lib/webull-signing.ts";

test("matches Webull's published HMAC-SHA1 signing vector", async () => {
  const signature = await webullHmacSha1Base64(
    "0f50a2e853334a9aae1a783bee120c1f",
    "/trade/place_order&a1=webull&a2=123&a3=xxx&host=api.webull.com&q1=yyy&x-app-key=776da210ab4a452795d74e726ebd74b6&x-signature-algorithm=HMAC-SHA1&x-signature-nonce=48ef5afed43d4d91ae514aaeafbc29ba&x-signature-version=1.0&x-timestamp=2022-01-04T03:55:31Z&E296C96787E1A309691CEF3692F5EEDD",
  );
  assert.equal(signature, "kvlS6opdZDhEBo5jq40nHYXaLvM=");
});

test("POST signing is deterministic and includes the exact request body", async () => {
  const input = {
    path: "/openapi/trade/order/place",
    body: '{"account_id":"sandbox","new_orders":[{"client_order_id":"SBX123","combo_type":"NORMAL","instrument_type":"EQUITY","entrust_type":"QTY","market":"US","symbol":"AAPL","side":"BUY","order_type":"LIMIT","time_in_force":"DAY","support_trading_session":"CORE","limit_price":"1.00","quantity":"1"}]}',
    appKey: "key",
    appSecret: "secret",
    host: "api.sandbox.webull.com",
    timestamp: "2026-07-20T00:00:00Z",
    nonce: "nonce",
  };
  assert.equal(await signWebullRequest(input), "3rAiZncc0QinsM9BuRIR8HztS+8=");
});
