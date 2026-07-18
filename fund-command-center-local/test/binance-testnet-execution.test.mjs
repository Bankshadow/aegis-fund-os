import assert from "node:assert/strict";
import test from "node:test";
import { placeTestnetGrid, OrphanedTestnetOrdersError } from "../src/lib/binance-testnet-execution.ts";

process.env.BINANCE_TESTNET_API_KEY = "testnet-key";
process.env.BINANCE_TESTNET_API_SECRET = "testnet-secret";
process.env.BINANCE_TESTNET_BASE_URL = "https://testnet.binance.vision";

const bot = {
  id: "BOT-testnet-1", name: "Testnet grid", environment: "BINANCE_TESTNET",
  pair: "BTCUSDT", state: "APPROVED", runtimeState: "IDLE", makerId: "maker",
  checkerId: "checker", version: 3, createdAt: "2026-07-17T00:00:00Z",
  updatedAt: "2026-07-17T00:00:00Z",
  configuration: { lower: "90", upper: "110", grids: 4, mode: "ARITHMETIC", investment: "100" },
};

const response = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { "content-type": "application/json" },
});

const marketResponse = (url) => {
  if (url.includes("/api/v3/time")) return response({ serverTime: 1_700_000_000_000 });
  if (url.includes("bookTicker")) return response({ bidPrice: "99", askPrice: "101" });
  if (url.includes("exchangeInfo")) return response({ symbols: [{ filters: [
    { filterType: "PRICE_FILTER", tickSize: "0.01" },
    { filterType: "LOT_SIZE", stepSize: "0.001" },
    { filterType: "MIN_NOTIONAL", minNotional: "5" },
  ] }] });
  if (url.includes("/api/v3/account")) return response({ balances: [
    { asset: "BTC", free: "10" }, { asset: "USDT", free: "1000" },
  ] });
  return null;
};

test("places deterministic LIMIT orders only on Binance Spot Testnet", async () => {
  const calls = [];
  let orderId = 100;
  const fetcher = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method ?? "GET" });
    const market = marketResponse(String(url));
    if (market) return market;
    if (init.method === "POST" && String(url).includes("/api/v3/order?"))
      return response({ orderId: ++orderId, clientOrderId: new URL(url).searchParams.get("newClientOrderId"), status: "NEW" });
    throw new Error(`Unexpected request ${init.method ?? "GET"} ${url}`);
  };
  const orders = await placeTestnetGrid(bot, fetcher);
  assert.equal(orders.length, 4);
  assert.equal(new Set(orders.map((order) => order.clientOrderId)).size, 4);
  assert.ok(calls.every((call) => call.url.startsWith("https://testnet.binance.vision/")));
  assert.equal(calls.filter((call) => call.method === "POST").length, 4);
  // Time is synced once for the whole grid, not re-fetched per order (no N+1).
  assert.equal(calls.filter((call) => call.url.includes("/api/v3/time")).length, 1);
});

test("cancels already accepted Testnet orders when a later placement fails", async () => {
  let posts = 0;
  let deletes = 0;
  const fetcher = async (url, init = {}) => {
    const market = marketResponse(String(url));
    if (market) return market;
    if (init.method === "POST") {
      posts += 1;
      if (posts === 2) return response({ code: -2010, msg: "rejected" }, 400);
      return response({ orderId: 200, clientOrderId: new URL(url).searchParams.get("newClientOrderId"), status: "NEW" });
    }
    if (init.method === "DELETE") { deletes += 1; return response({ status: "CANCELED" }); }
    throw new Error(`Unexpected request ${init.method ?? "GET"} ${url}`);
  };
  await assert.rejects(() => placeTestnetGrid(bot, fetcher), /Binance Testnet -2010/);
  assert.equal(deletes, 1);
});

test("surfaces orphaned orders when rollback cannot cancel a filled order", async () => {
  let posts = 0;
  const placedClientIds = [];
  const fetcher = async (url, init = {}) => {
    const market = marketResponse(String(url));
    if (market) return market;
    if (init.method === "POST") {
      posts += 1;
      if (posts === 2) return response({ code: -2010, msg: "rejected" }, 400);
      const clientOrderId = new URL(url).searchParams.get("newClientOrderId");
      placedClientIds.push(clientOrderId);
      return response({ orderId: 300, clientOrderId, status: "NEW" });
    }
    // The already-accepted order filled before rollback: cancel is rejected.
    if (init.method === "DELETE") return response({ code: -2011, msg: "Unknown order sent." }, 400);
    throw new Error(`Unexpected request ${init.method ?? "GET"} ${url}`);
  };
  const error = await placeTestnetGrid(bot, fetcher).then(
    () => { throw new Error("expected placeTestnetGrid to reject"); },
    (caught) => caught,
  );
  assert.ok(error instanceof OrphanedTestnetOrdersError);
  assert.equal(error.orphaned.length, 1);
  assert.equal(error.orphaned[0].clientOrderId, placedClientIds[0]);
  assert.match(error.message, /Reconcile/);
});

test("fails closed when a non-Testnet base URL is configured", async () => {
  process.env.BINANCE_TESTNET_BASE_URL = "https://api.binance.com";
  await assert.rejects(() => placeTestnetGrid(bot, async () => response({})), /locked to Binance Spot Testnet/);
  process.env.BINANCE_TESTNET_BASE_URL = "https://testnet.binance.vision";
});
