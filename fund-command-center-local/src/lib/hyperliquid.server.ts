import "@tanstack/react-start/server-only";

const HYPERLIQUID_TESTNET_INFO_URL = "https://api.hyperliquid-testnet.xyz/info";
const REQUEST_TIMEOUT_MS = 8_000;
const WALLET_ADDRESS_PATTERN = /^0x[a-fA-F0-9]{40}$/;

type RuntimeEnvironment = Record<string, string | undefined>;

type HyperliquidAssetContext = {
  universe?: unknown[];
};

type HyperliquidClearinghouseState = {
  assetPositions?: unknown[];
};

export type HyperliquidProbeResult = {
  status: "connected" | "needs_address" | "misconfigured" | "unreachable";
  reachable: boolean;
  walletConfigured: boolean;
  baseUrl: string;
  checkedAt: string;
  latencyMs: number | null;
  marketCount: number | null;
  openPositionCount: number | null;
  openOrderCount: number | null;
  message: string;
};

function getRuntimeEnvironment(): RuntimeEnvironment {
  const runtime = globalThis as typeof globalThis & {
    process?: { env?: RuntimeEnvironment };
  };
  return runtime.process?.env ?? {};
}

function getConfiguration() {
  const env = getRuntimeEnvironment();
  return {
    baseUrl: env.HYPERLIQUID_TESTNET_INFO_URL?.trim() || HYPERLIQUID_TESTNET_INFO_URL,
    walletAddress: env.HYPERLIQUID_TESTNET_WALLET_ADDRESS?.trim() || "",
  };
}

async function fetchWithTimeout(body: object) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(HYPERLIQUID_TESTNET_INFO_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

async function fetchInfo<T>(body: object): Promise<T> {
  const response = await fetchWithTimeout(body);
  if (!response.ok) throw new Error(`Hyperliquid Info API returned HTTP ${response.status}`);
  return (await response.json()) as T;
}

export async function probeHyperliquid(): Promise<HyperliquidProbeResult> {
  const checkedAt = new Date().toISOString();
  const { baseUrl, walletAddress } = getConfiguration();
  if (baseUrl !== HYPERLIQUID_TESTNET_INFO_URL) {
    return {
      status: "misconfigured",
      reachable: false,
      walletConfigured: false,
      baseUrl,
      checkedAt,
      latencyMs: null,
      marketCount: null,
      openPositionCount: null,
      openOrderCount: null,
      message: "Only the official Hyperliquid Testnet Info API endpoint is allowed.",
    };
  }

  const startedAt = Date.now();
  try {
    const metadata = await fetchInfo<[HyperliquidAssetContext, unknown[]]>({
      type: "metaAndAssetCtxs",
    });
    const marketCount = metadata[0]?.universe?.length ?? 0;

    if (!walletAddress) {
      return {
        status: "needs_address",
        reachable: true,
        walletConfigured: false,
        baseUrl,
        checkedAt,
        latencyMs: Date.now() - startedAt,
        marketCount,
        openPositionCount: null,
        openOrderCount: null,
        message:
          "Hyperliquid Testnet market data is reachable. Add a public Testnet wallet address for account-level read-only data.",
      };
    }

    if (!WALLET_ADDRESS_PATTERN.test(walletAddress)) {
      return {
        status: "misconfigured",
        reachable: true,
        walletConfigured: false,
        baseUrl,
        checkedAt,
        latencyMs: Date.now() - startedAt,
        marketCount,
        openPositionCount: null,
        openOrderCount: null,
        message: "The Hyperliquid wallet address must be a 42-character 0x address.",
      };
    }

    const [state, orders] = await Promise.all([
      fetchInfo<HyperliquidClearinghouseState>({ type: "clearinghouseState", user: walletAddress }),
      fetchInfo<unknown[]>({ type: "openOrders", user: walletAddress }),
    ]);

    return {
      status: "connected",
      reachable: true,
      walletConfigured: true,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      marketCount,
      openPositionCount: state.assetPositions?.length ?? 0,
      openOrderCount: orders.length,
      message:
        "Connected through Hyperliquid Testnet's public Info API. No wallet signing, orders, transfers, or withdrawals are enabled.",
    };
  } catch {
    return {
      status: "unreachable",
      reachable: false,
      walletConfigured: false,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      marketCount: null,
      openPositionCount: null,
      openOrderCount: null,
      message: "Hyperliquid Testnet Info API did not respond within the connection window.",
    };
  }
}
