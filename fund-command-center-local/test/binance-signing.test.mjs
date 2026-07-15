import assert from "node:assert/strict";
import test from "node:test";

import { hmacSha256Hex } from "../src/lib/binance-signing.ts";

test("matches the official Binance HMAC SHA-256 signing vector", async () => {
  const secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j";
  const payload =
    "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1&recvWindow=5000&timestamp=1499827319559";

  const signature = await hmacSha256Hex(secret, payload);

  assert.equal(signature, "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71");
});
