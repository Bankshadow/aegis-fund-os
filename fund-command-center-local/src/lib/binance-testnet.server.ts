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
