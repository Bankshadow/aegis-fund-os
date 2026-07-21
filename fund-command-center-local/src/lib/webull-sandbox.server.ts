import "@tanstack/react-start/server-only";

import { signWebullGetRequest, signWebullRequest } from "./webull-signing.ts";

const WEBULL_SANDBOX_HOST = "api.sandbox.webull.com";
const REQUEST_TIMEOUT_MS = 8_000;

type RuntimeEnvironment = Record<string, string | undefined>;
type WebullAccount = { account_id?: string; account_type?: string };
export type WebullSandboxOrderInput = {
  accountId: string;
  symbol: string;
  side: "BUY" | "SELL";
  limitPrice: string;
  quantity: string;
};
export type WebullSandboxOrderResult = {
  status:
    "placed" | "disabled" | "needs_credentials" | "rejected" | "misconfigured" | "unreachable";
  orderId: string | null;
  clientOrderId: string | null;
  message: string;
};

export type WebullSandboxProbeResult = {
  status: "connected" | "needs_credentials" | "rejected" | "unreachable" | "misconfigured";
  reachable: boolean;
  authenticated: boolean;
  baseUrl: string;
  checkedAt: string;
  latencyMs: number | null;
  accountCount: number | null;
  accountTypes: string[];
  message: string;
};

function getRuntimeEnvironment(): RuntimeEnvironment {
  const runtime = globalThis as typeof globalThis & { process?: { env?: RuntimeEnvironment } };
  return runtime.process?.env ?? {};
}

function getConfiguration() {
  const env = getRuntimeEnvironment();
  return {
    appKey: env.WEBULL_SANDBOX_APP_KEY?.trim() ?? "",
    appSecret: env.WEBULL_SANDBOX_APP_SECRET?.trim() ?? "",
    accessToken: env.WEBULL_SANDBOX_ACCESS_TOKEN?.trim() ?? "",
    baseUrl: env.WEBULL_SANDBOX_BASE_URL?.trim() || `https://${WEBULL_SANDBOX_HOST}`,
    orderTestEnabled: env.WEBULL_SANDBOX_ORDER_TEST_ENABLED?.trim() === "true",
    allowedSymbols: (env.WEBULL_SANDBOX_ALLOWED_SYMBOLS?.trim() || "AAPL")
      .split(",")
      .map((symbol) => symbol.trim().toUpperCase())
      .filter(Boolean),
  };
}

async function fetchWithTimeout(url: string, init: RequestInit) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, cache: "no-store", signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Intentionally limited to one signed GET against Webull's sandbox account-list
 * endpoint. There are no POST, order, cancellation, transfer, or withdrawal paths.
 */
export async function probeWebullSandbox(): Promise<WebullSandboxProbeResult> {
  const checkedAt = new Date().toISOString();
  const { appKey, appSecret, accessToken, baseUrl } = getConfiguration();
  if (baseUrl !== `https://${WEBULL_SANDBOX_HOST}`) {
    return {
      status: "misconfigured",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: null,
      accountCount: null,
      accountTypes: [],
      message: "Only the official Webull sandbox endpoint is allowed.",
    };
  }
  if (!appKey || !appSecret) {
    return {
      status: "needs_credentials",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: null,
      accountCount: null,
      accountTypes: [],
      message:
        "Add Webull sandbox App Key and App Secret to enable the signed read-only account check.",
    };
  }

  const startedAt = Date.now();
  const path = "/openapi/account/list";
  const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const nonce = crypto.randomUUID().replaceAll("-", "");
  try {
    const signature = await signWebullGetRequest({
      path,
      appKey,
      appSecret,
      host: WEBULL_SANDBOX_HOST,
      timestamp,
      nonce,
    });
    const response = await fetchWithTimeout(`${baseUrl}${path}`, {
      headers: {
        "x-app-key": appKey,
        "x-timestamp": timestamp,
        "x-signature": signature,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-version": "1.0",
        "x-signature-nonce": nonce,
        "x-version": "v2",
        ...(accessToken ? { "x-access-token": accessToken } : {}),
      },
    });
    if (!response.ok) {
      return {
        status: "rejected",
        reachable: true,
        authenticated: false,
        baseUrl,
        checkedAt,
        latencyMs: Date.now() - startedAt,
        accountCount: null,
        accountTypes: [],
        message: "Webull sandbox rejected the credentials, signature, or optional access token.",
      };
    }
    const accounts = (await response.json()) as WebullAccount[];
    return {
      status: "connected",
      reachable: true,
      authenticated: true,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      accountCount: accounts.length,
      accountTypes: [
        ...new Set(
          accounts
            .map((account) => account.account_type)
            .filter((type): type is string => Boolean(type)),
        ),
      ],
      message:
        "Webull sandbox account metadata was read successfully. This adapter exposes no order, cancellation, transfer, or withdrawal capability.",
    };
  } catch {
    return {
      status: "unreachable",
      reachable: false,
      authenticated: false,
      baseUrl,
      checkedAt,
      latencyMs: Date.now() - startedAt,
      accountCount: null,
      accountTypes: [],
      message: "Webull sandbox did not respond within the connection window.",
    };
  }
}

function clientOrderId() {
  return `SBX${crypto.randomUUID().replaceAll("-", "").slice(0, 29)}`;
}

/** Places one deliberately tiny, LIMIT-only test order in Webull Sandbox. */
export async function placeWebullSandboxTestOrder(
  input: WebullSandboxOrderInput,
): Promise<WebullSandboxOrderResult> {
  const { appKey, appSecret, accessToken, baseUrl, orderTestEnabled, allowedSymbols } =
    getConfiguration();
  if (baseUrl !== `https://${WEBULL_SANDBOX_HOST}`)
    return {
      status: "misconfigured",
      orderId: null,
      clientOrderId: null,
      message: "Only the official Webull sandbox endpoint is allowed.",
    };
  if (!orderTestEnabled)
    return {
      status: "disabled",
      orderId: null,
      clientOrderId: null,
      message:
        "Sandbox order testing is disabled. Set WEBULL_SANDBOX_ORDER_TEST_ENABLED=true server-side to enable it.",
    };
  if (!appKey || !appSecret || !accessToken)
    return {
      status: "needs_credentials",
      orderId: null,
      clientOrderId: null,
      message: "Sandbox order testing requires App Key, App Secret and Access Token.",
    };
  const symbol = input.symbol.trim().toUpperCase();
  const accountId = input.accountId.trim();
  const price = Number(input.limitPrice);
  const quantity = Number(input.quantity);
  if (!accountId || !/^[A-Z][A-Z0-9.-]{0,9}$/.test(symbol) || !allowedSymbols.includes(symbol))
    return {
      status: "rejected",
      orderId: null,
      clientOrderId: null,
      message: `Symbol/account rejected. Allowed sandbox symbols: ${allowedSymbols.join(", ")}.`,
    };
  if (
    !Number.isFinite(price) ||
    price <= 0 ||
    !Number.isFinite(quantity) ||
    quantity <= 0 ||
    quantity > 1 ||
    price * quantity > 25
  )
    return {
      status: "rejected",
      orderId: null,
      clientOrderId: null,
      message: "Sandbox test is capped at 1 share and USD 25 notional.",
    };

  const path = "/openapi/trade/order/place";
  const orderId = clientOrderId();
  const body = JSON.stringify({
    account_id: accountId,
    new_orders: [
      {
        client_order_id: orderId,
        combo_type: "NORMAL",
        instrument_type: "EQUITY",
        entrust_type: "QTY",
        market: "US",
        symbol,
        side: input.side,
        order_type: "LIMIT",
        time_in_force: "DAY",
        support_trading_session: "CORE",
        limit_price: price.toFixed(2),
        quantity: quantity.toString(),
      },
    ],
  });
  const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const nonce = crypto.randomUUID().replaceAll("-", "");
  try {
    const signature = await signWebullRequest({
      path,
      body,
      appKey,
      appSecret,
      host: WEBULL_SANDBOX_HOST,
      timestamp,
      nonce,
    });
    const response = await fetchWithTimeout(`${baseUrl}${path}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json",
        "x-app-key": appKey,
        "x-timestamp": timestamp,
        "x-signature": signature,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-version": "1.0",
        "x-signature-nonce": nonce,
        "x-access-token": accessToken,
        "x-version": "v2",
      },
      body,
    });
    const payload = (await response.json().catch(() => ({}))) as {
      order_id?: string;
      client_order_id?: string;
      message?: string;
    };
    if (!response.ok)
      return {
        status: "rejected",
        orderId: null,
        clientOrderId: orderId,
        message: payload.message || "Webull sandbox rejected the test order.",
      };
    return {
      status: "placed",
      orderId: payload.order_id ?? null,
      clientOrderId: payload.client_order_id ?? orderId,
      message:
        "Sandbox LIMIT test order accepted. Cancel it from Webull Sandbox after verification.",
    };
  } catch {
    return {
      status: "unreachable",
      orderId: null,
      clientOrderId: orderId,
      message: "Webull sandbox did not respond to the test order request.",
    };
  }
}
