import "@tanstack/react-start/server-only";

import { hmacSha256Hex } from "./binance-signing";

const BYBIT_TESTNET_BASE_URL = "https://api-testnet.bybit.com";
const REQUEST_TIMEOUT_MS = 8_000;
const RECV_WINDOW_MS = 5_000;

type RuntimeEnvironment = Record<string, string | undefined>;

type BybitTimeResponse = { retCode?: number; retMsg?: string; time?: number };
type BybitWalletResponse = {
  retCode?: number;
  retMsg?: string;
  result?: {
    list?: Array<{
      accountType?: string;
      coin?: Array<{ walletBalance?: string; equity?: string }>;
    }>;
  };
};

export type BybitTestnetProbeResult = {
  status: "connected" | "needs_credentials" | "rejected" | "unreachable" | "misconfigured";
  reachable: boolean;
  authenticated: boolean;
  baseUrl: string;
  checkedAt: string;
  latencyMs: number | null;
  serverTime: number | null;
  accountType?: string;
  nonZeroAssetCount?: number;
  message: string;
  errorCode?: number;
};

function getRuntimeEnvironment(): RuntimeEnvironment {
  const runtime = globalThis as typeof globalThis & { process?: { env?: RuntimeEnvironment } };
  return runtime.process?.env ?? {};
}

function getConfiguration() {
  const env = getRuntimeEnvironment();
  return {
    apiKey: env.BYBIT_TESTNET_API_KEY?.trim() ?? "",
    apiSecret: env.BYBIT_TESTNET_API_SECRET?.trim() ?? "",
    baseUrl: env.BYBIT_TESTNET_BASE_URL?.trim() || BYBIT_TESTNET_BASE_URL,
  };
}

async function fetchWithTimeout(url: string, init?: RequestInit) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, cache: "no-store", signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function countNonZeroAssets(wallet: BybitWalletResponse["result"]): number {
  return (wallet?.list?.flatMap((account) => account.coin ?? []) ?? []).filter((coin) => {
    const value = Number(coin.equity ?? coin.walletBalance ?? 0);
    return Number.isFinite(value) && value !== 0;
  }).length;
}

export async function probeBybitTestnet(): Promise<BybitTestnetProbeResult> {
  const checkedAt = new Date().toISOString();
  const { apiKey, apiSecret, baseUrl } = getConfiguration();
  if (baseUrl !== BYBIT_TESTNET_BASE_URL) {
    return {
      status: "misconfigured",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: null,
      serverTime: null,
      message: "Only the official Bybit Testnet endpoint is allowed.",
    };
  }

  const startedAt = Date.now();
  let serverTime: number;
  try {
    const response = await fetchWithTimeout(`${baseUrl}/v5/market/time`);
    const payload = (await response.json()) as BybitTimeResponse;
    if (!response.ok || payload.retCode !== 0 || !Number.isFinite(payload.time))
      throw new Error("Bybit time unavailable");
    serverTime = payload.time as number;
  } catch {
    return {
      status: "unreachable",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      serverTime: null,
      message: "Bybit Testnet did not respond within the connection window.",
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
      message: "Bybit Testnet is reachable. Add both server-side API credentials to authenticate.",
    };
  }

  const query = "accountType=UNIFIED";
  const timestamp = String(serverTime);
  const signature = await hmacSha256Hex(
    apiSecret,
    `${timestamp}${apiKey}${RECV_WINDOW_MS}${query}`,
  );
  try {
    const response = await fetchWithTimeout(`${baseUrl}/v5/account/wallet-balance?${query}`, {
      headers: {
        "X-BAPI-API-KEY": apiKey,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": String(RECV_WINDOW_MS),
      },
    });
    const payload = (await response.json()) as BybitWalletResponse;
    if (!response.ok || payload.retCode !== 0) {
      return {
        status: "rejected",
        reachable: true,
        authenticated: false,
        baseUrl,
        checkedAt,
        latencyMs: Date.now() - startedAt,
        serverTime,
        message: "Bybit Testnet rejected the credentials or signed request.",
        errorCode: payload.retCode,
      };
    }
    const account = payload.result?.list?.[0];
    return {
      status: "connected",
      reachable: true,
      authenticated: true,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      serverTime,
      accountType: account?.accountType ?? "UNIFIED",
      nonZeroAssetCount: countNonZeroAssets(payload.result),
      message:
        "Authenticated through Bybit Testnet in read-only mode. No order, transfer, or withdrawal calls are enabled.",
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
      message: "Bybit Testnet was reachable, but the signed account request did not complete.",
    };
  }
}
