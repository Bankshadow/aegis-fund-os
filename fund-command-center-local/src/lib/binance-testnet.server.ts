import "@tanstack/react-start/server-only";

import { hmacSha256Hex } from "./binance-signing";

const BINANCE_SPOT_TESTNET_URL = "https://testnet.binance.vision";
const REQUEST_TIMEOUT_MS = 8_000;
const RECV_WINDOW_MS = 5_000;

type RuntimeEnvironment = Record<string, string | undefined>;

type BinanceAccountResponse = {
  accountType?: string;
  balances?: Array<{ asset?: string; free?: string; locked?: string }>;
  canTrade?: boolean;
  permissions?: string[];
};

type BinanceErrorResponse = {
  code?: number;
  msg?: string;
};

type BinanceOpenOrder = { orderId: number; clientOrderId: string; status: string; origQty: string; executedQty: string };
type BinanceTrade = { orderId: number; id: number; qty: string; quoteQty: string; commission: string; commissionAsset: string; isBuyer: boolean; time: number };

export type BinanceTestnetGridStatus = {
  checkedAt: string;
  openOrders: BinanceOpenOrder[];
  trades: BinanceTrade[];
};

export type BinanceTestnetProbeResult = {
  status: "connected" | "needs_credentials" | "rejected" | "unreachable" | "misconfigured";
  reachable: boolean;
  authenticated: boolean;
  baseUrl: string;
  checkedAt: string;
  latencyMs: number | null;
  serverTime: number | null;
  accountType?: string;
  permissions?: string[];
  nonZeroAssetCount?: number;
  remoteTradePermission?: boolean;
  message: string;
  errorCode?: number;
};

export type BinancePaperGridFeed = {
  status: "connected" | "unavailable";
  symbol: "BTCUSDT";
  checkedAt: string;
  bidPrice: number | null;
  askPrice: number | null;
  midPrice: number | null;
  btcFree: number | null;
  usdtFree: number | null;
  tickSize: number | null;
  stepSize: number | null;
  minNotional: number | null;
  readOnly: true;
  canPlaceOrder: false;
  message: string;
};

function getRuntimeEnvironment(): RuntimeEnvironment {
  const runtime = globalThis as typeof globalThis & {
    process?: { env?: RuntimeEnvironment };
  };
  return runtime.process?.env ?? {};
}

function getCredentials() {
  const env = getRuntimeEnvironment();
  return {
    apiKey: env.BINANCE_TESTNET_API_KEY?.trim() ?? "",
    apiSecret: env.BINANCE_TESTNET_API_SECRET?.trim() ?? "",
    baseUrl: env.BINANCE_TESTNET_BASE_URL?.trim() || BINANCE_SPOT_TESTNET_URL,
  };
}

async function fetchWithTimeout(url: string, init?: RequestInit) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

function nonZeroBalanceCount(balances: BinanceAccountResponse["balances"]): number {
  return (balances ?? []).filter((balance) => {
    const free = Number(balance.free ?? 0);
    const locked = Number(balance.locked ?? 0);
    return Number.isFinite(free) && Number.isFinite(locked) && (free !== 0 || locked !== 0);
  }).length;
}

export async function probeBinanceSpotTestnet(): Promise<BinanceTestnetProbeResult> {
  const checkedAt = new Date().toISOString();
  const { apiKey, apiSecret, baseUrl } = getCredentials();

  if (baseUrl !== BINANCE_SPOT_TESTNET_URL) {
    return {
      status: "misconfigured",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: null,
      serverTime: null,
      message: "Only the official Binance Spot Testnet endpoint is allowed.",
    };
  }

  const startedAt = Date.now();
  let serverTime: number;
  try {
    const timeResponse = await fetchWithTimeout(`${baseUrl}/api/v3/time`);
    if (!timeResponse.ok) throw new Error(`HTTP ${timeResponse.status}`);
    const timePayload = (await timeResponse.json()) as { serverTime?: number };
    if (!Number.isFinite(timePayload.serverTime)) throw new Error("Missing Binance server time");
    serverTime = timePayload.serverTime as number;
  } catch {
    return {
      status: "unreachable",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      serverTime: null,
      message: "Binance Spot Testnet did not respond within the connection window.",
    };
  }

  if (!apiKey || !apiSecret) {
    return {
      status: "needs_credentials",
      reachable: true,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      serverTime,
      message: "Testnet is reachable. Add both server-side API credentials to authenticate.",
    };
  }

  const query = new URLSearchParams({
    omitZeroBalances: "true",
    recvWindow: String(RECV_WINDOW_MS),
    timestamp: String(serverTime),
  }).toString();
  const signature = await hmacSha256Hex(apiSecret, query);

  try {
    const accountResponse = await fetchWithTimeout(
      `${baseUrl}/api/v3/account?${query}&signature=${signature}`,
      { headers: { "X-MBX-APIKEY": apiKey } },
    );
    const payload = (await accountResponse.json()) as BinanceAccountResponse & BinanceErrorResponse;

    if (!accountResponse.ok) {
      return {
        status: "rejected",
        reachable: true,
        authenticated: false,
        baseUrl,
        checkedAt,
        latencyMs: Date.now() - startedAt,
        serverTime,
        message: "Binance Testnet rejected the credentials or signed request.",
        errorCode: payload.code,
      };
    }

    return {
      status: "connected",
      reachable: true,
      authenticated: true,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      serverTime,
      accountType: payload.accountType ?? "SPOT",
      permissions: payload.permissions ?? [],
      nonZeroAssetCount: nonZeroBalanceCount(payload.balances),
      remoteTradePermission: payload.canTrade === true,
      message:
        payload.canTrade === true
          ? "Authenticated. The remote key reports trade permission, but Aegis exposes read-only calls only."
          : "Authenticated with a read-only account probe.",
    };
  } catch {
    return {
      status: "unreachable",
      reachable: true,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      serverTime,
      message: "Testnet was reachable, but the signed account request did not complete.",
    };
  }
}

export async function getBinancePaperGridFeed(): Promise<BinancePaperGridFeed> {
  const checkedAt = new Date().toISOString();
  const { apiKey, apiSecret, baseUrl } = getCredentials();
  const unavailable = (message: string): BinancePaperGridFeed => ({
    status: "unavailable", symbol: "BTCUSDT", checkedAt,
    bidPrice: null, askPrice: null, midPrice: null, btcFree: null, usdtFree: null,
    tickSize: null, stepSize: null, minNotional: null,
    readOnly: true, canPlaceOrder: false, message,
  });
  if (baseUrl !== BINANCE_SPOT_TESTNET_URL || !apiKey || !apiSecret)
    return unavailable("Binance Spot Testnet credentials are unavailable.");

  try {
    const timePayload = (await (await fetchWithTimeout(`${baseUrl}/api/v3/time`)).json()) as {
      serverTime?: number;
    };
    if (!Number.isFinite(timePayload.serverTime)) return unavailable("Binance server time unavailable.");
    const query = new URLSearchParams({
      omitZeroBalances: "true", recvWindow: String(RECV_WINDOW_MS),
      timestamp: String(timePayload.serverTime),
    }).toString();
    const signature = await hmacSha256Hex(apiSecret, query);
    const [tickerResponse, accountResponse, exchangeInfoResponse] = await Promise.all([
      fetchWithTimeout(`${baseUrl}/api/v3/ticker/bookTicker?symbol=BTCUSDT`),
      fetchWithTimeout(`${baseUrl}/api/v3/account?${query}&signature=${signature}`, {
        headers: { "X-MBX-APIKEY": apiKey },
      }),
      fetchWithTimeout(`${baseUrl}/api/v3/exchangeInfo?symbol=BTCUSDT`),
    ]);
    if (!tickerResponse.ok || !accountResponse.ok || !exchangeInfoResponse.ok)
      return unavailable("Testnet market, account, or symbol rules feed rejected.");
    const ticker = (await tickerResponse.json()) as { bidPrice?: string; askPrice?: string };
    const account = (await accountResponse.json()) as BinanceAccountResponse;
    const exchangeInfo = (await exchangeInfoResponse.json()) as {
      symbols?: Array<{ filters?: Array<Record<string, string>> }>;
    };
    const bidPrice = Number(ticker.bidPrice);
    const askPrice = Number(ticker.askPrice);
    if (!(bidPrice > 0) || !(askPrice > bidPrice)) return unavailable("Invalid BTCUSDT book ticker.");
    const balance = (asset: string) =>
      Number(account.balances?.find((item) => item.asset === asset)?.free ?? 0);
    const filters = exchangeInfo.symbols?.[0]?.filters ?? [];
    const filter = (type: string) => filters.find((item) => item.filterType === type);
    const tickSize = Number(filter("PRICE_FILTER")?.tickSize);
    const stepSize = Number(filter("LOT_SIZE")?.stepSize);
    const minNotional = Number(
      filter("NOTIONAL")?.minNotional ?? filter("MIN_NOTIONAL")?.minNotional,
    );
    if (!(tickSize > 0) || !(stepSize > 0) || !(minNotional >= 0))
      return unavailable("Invalid Binance BTCUSDT symbol rules.");
    return {
      status: "connected", symbol: "BTCUSDT", checkedAt,
      bidPrice, askPrice, midPrice: (bidPrice + askPrice) / 2,
      btcFree: balance("BTC"), usdtFree: balance("USDT"),
      tickSize, stepSize, minNotional,
      readOnly: true, canPlaceOrder: false,
      message: "Real Binance Spot Testnet feed connected to local paper-grid simulation.",
    };
  } catch {
    return unavailable("Binance Spot Testnet paper-grid feed did not complete.");
  }
}

/** Read-only exchange evidence for an already-created Testnet grid bot. */
export async function getBinanceTestnetGridStatus(symbol: "BTCUSDT"): Promise<BinanceTestnetGridStatus> {
  const { apiKey, apiSecret, baseUrl } = getCredentials();
  if (baseUrl !== BINANCE_SPOT_TESTNET_URL) throw new Error("Only the official Binance Spot Testnet endpoint is allowed.");
  if (!apiKey || !apiSecret) throw new Error("Binance Spot Testnet credentials are unavailable.");
  const timeResponse = await fetchWithTimeout(`${baseUrl}/api/v3/time`);
  if (!timeResponse.ok) throw new Error("Binance Testnet server time is unavailable.");
  const { serverTime } = (await timeResponse.json()) as { serverTime?: number };
  if (!Number.isFinite(serverTime)) throw new Error("Binance Testnet server time is invalid.");
  const query = new URLSearchParams({ symbol, recvWindow: String(RECV_WINDOW_MS), timestamp: String(serverTime) }).toString();
  const signature = await hmacSha256Hex(apiSecret, query);
  const headers = { "X-MBX-APIKEY": apiKey };
  const [openResponse, tradesResponse] = await Promise.all([
    fetchWithTimeout(`${baseUrl}/api/v3/openOrders?${query}&signature=${signature}`, { headers }),
    fetchWithTimeout(`${baseUrl}/api/v3/myTrades?${query}&signature=${signature}`, { headers }),
  ]);
  if (!openResponse.ok || !tradesResponse.ok) throw new Error("Binance Testnet order-status request was rejected.");
  return { checkedAt: new Date().toISOString(), openOrders: await openResponse.json() as BinanceOpenOrder[], trades: await tradesResponse.json() as BinanceTrade[] };
}
