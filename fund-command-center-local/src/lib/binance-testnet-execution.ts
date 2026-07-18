import "@tanstack/react-start/server-only";

import Decimal from "decimal.js-light";
import { buildExactGridPreview, type GridMode } from "./grid-bot-domain.ts";
import { hmacSha256Hex } from "./binance-signing.ts";
import type { BotRecord } from "./grid-bot-repository.ts";

const TESTNET_URL = "https://testnet.binance.vision";
const RECV_WINDOW = "5000";
const MAX_GRID_ORDERS = 40;

type RuntimeEnvironment = Record<string, string | undefined>;
type Fetcher = typeof fetch;

export type TestnetOrderRecord = {
  exchangeOrderId: string;
  clientOrderId: string;
  gridIndex: number;
  side: "BUY" | "SELL";
  price: string;
  quantity: string;
  status: string;
};

/**
 * Raised when a grid placement fails partway and at least one already-accepted
 * order could not be cancelled during rollback. A cancel is rejected when the
 * order is no longer open — typically because it filled — so the exchange now
 * holds positions with no matching ledger record. Callers must reconcile the
 * listed orders rather than treat the start as cleanly rolled back.
 */
export class OrphanedTestnetOrdersError extends Error {
  readonly orphaned: TestnetOrderRecord[];
  readonly cause: unknown;
  constructor(cause: unknown, orphaned: TestnetOrderRecord[]) {
    const reason = cause instanceof Error ? cause.message : String(cause);
    super(
      `Testnet grid rollback incomplete: ${orphaned.length} order(s) could not be cancelled after "${reason}". ` +
        `Reconcile ${orphaned.map((order) => order.clientOrderId).join(", ")}.`,
    );
    this.name = "OrphanedTestnetOrdersError";
    this.orphaned = orphaned;
    this.cause = cause;
  }
}

const runtimeEnvironment = () => {
  const runtime = globalThis as typeof globalThis & { process?: { env?: RuntimeEnvironment } };
  return runtime.process?.env ?? {};
};

const credentials = () => {
  const env = runtimeEnvironment();
  const baseUrl = env.BINANCE_TESTNET_BASE_URL?.trim() || TESTNET_URL;
  if (baseUrl !== TESTNET_URL) throw new Error("Execution is locked to Binance Spot Testnet");
  const apiKey = env.BINANCE_TESTNET_API_KEY?.trim() ?? "";
  const apiSecret = env.BINANCE_TESTNET_API_SECRET?.trim() ?? "";
  if (!apiKey || !apiSecret) throw new Error("Binance Spot Testnet credentials are unavailable");
  return { baseUrl, apiKey, apiSecret };
};

const json = async <T>(response: Response): Promise<T> => {
  const payload = (await response.json()) as T & { code?: number; msg?: string };
  if (!response.ok)
    throw new Error(`Binance Testnet ${payload.code ?? response.status}: ${payload.msg ?? "request rejected"}`);
  return payload;
};

/**
 * Binance requires each signed request to carry a timestamp within `recvWindow`
 * of exchange time. Rather than fetch `/api/v3/time` before every order — which
 * turns a 40-order grid into ~80 round-trips and courts rate limits — sync once
 * and derive later timestamps from the local clock plus this offset.
 */
const timeOffset = async (fetcher: Fetcher, baseUrl: string) => {
  const time = await json<{ serverTime: number }>(await fetcher(`${baseUrl}/api/v3/time`));
  return time.serverTime - Date.now();
};

const signedRequest = async <T>(
  fetcher: Fetcher,
  method: "POST" | "DELETE",
  path: string,
  parameters: Record<string, string>,
  offset?: number,
): Promise<T> => {
  const { baseUrl, apiKey, apiSecret } = credentials();
  const timestamp = offset === undefined ? await timeOffset(fetcher, baseUrl).then((o) => Date.now() + o) : Date.now() + offset;
  const query = new URLSearchParams({ ...parameters, recvWindow: RECV_WINDOW, timestamp: String(timestamp) }).toString();
  const signature = await hmacSha256Hex(apiSecret, query);
  return json<T>(
    await fetcher(`${baseUrl}${path}?${query}&signature=${signature}`, {
      method,
      headers: { "X-MBX-APIKEY": apiKey },
    }),
  );
};

const requiredString = (bot: BotRecord, key: string) => {
  const value = bot.configuration[key];
  if (typeof value !== "string" && typeof value !== "number") throw new Error(`Missing ${key} configuration`);
  return String(value);
};

export async function buildExecutableGrid(bot: BotRecord, fetcher: Fetcher = fetch, offset?: number) {
  if (bot.environment !== "BINANCE_TESTNET") throw new Error("Only BINANCE_TESTNET bots can transmit Testnet orders");
  if (bot.state !== "APPROVED" || bot.runtimeState !== "IDLE")
    throw new Error("Bot must be approved and IDLE before Testnet execution");
  if (bot.pair !== "BTCUSDT") throw new Error("Only BTCUSDT is enabled for Testnet execution");

  const { baseUrl, apiKey, apiSecret } = credentials();
  const clockOffset = offset ?? (await timeOffset(fetcher, baseUrl));
  const accountQuery = new URLSearchParams({ omitZeroBalances: "true", recvWindow: RECV_WINDOW, timestamp: String(Date.now() + clockOffset) }).toString();
  const accountSignature = await hmacSha256Hex(apiSecret, accountQuery);
  const [ticker, exchangeInfo, account] = await Promise.all([
    json<{ bidPrice: string; askPrice: string }>(await fetcher(`${baseUrl}/api/v3/ticker/bookTicker?symbol=${bot.pair}`)),
    json<{ symbols?: Array<{ filters?: Array<Record<string, string>> }> }>(await fetcher(`${baseUrl}/api/v3/exchangeInfo?symbol=${bot.pair}`)),
    json<{ balances?: Array<{ asset: string; free: string }> }>(await fetcher(`${baseUrl}/api/v3/account?${accountQuery}&signature=${accountSignature}`, { headers: { "X-MBX-APIKEY": apiKey } })),
  ]);
  const filters = exchangeInfo.symbols?.[0]?.filters ?? [];
  const filter = (type: string) => filters.find((item) => item.filterType === type);
  const currentPrice = new Decimal(ticker.bidPrice).add(ticker.askPrice).div(2).toFixed();
  const rows = buildExactGridPreview({
    lowerPrice: requiredString(bot, "lower"),
    upperPrice: requiredString(bot, "upper"),
    currentPrice,
    investment: requiredString(bot, "investment"),
    gridCount: Number(requiredString(bot, "grids")),
    mode: requiredString(bot, "mode") as GridMode,
    feeRatePct: "0.1",
    tickSize: filter("PRICE_FILTER")?.tickSize ?? "0",
    stepSize: filter("LOT_SIZE")?.stepSize ?? "0",
    minNotional: filter("NOTIONAL")?.minNotional ?? filter("MIN_NOTIONAL")?.minNotional ?? "0",
  });
  if (rows.length > MAX_GRID_ORDERS) throw new Error(`Testnet execution is capped at ${MAX_GRID_ORDERS} orders`);
  const balance = (asset: string) => new Decimal(account.balances?.find((item) => item.asset === asset)?.free ?? 0);
  const buyQuote = rows.filter((row) => row.side === "BUY").reduce((sum, row) => sum.add(row.quoteValue), new Decimal(0));
  const sellBase = rows.filter((row) => row.side === "SELL").reduce((sum, row) => sum.add(row.quantity), new Decimal(0));
  if (buyQuote.gt(balance("USDT"))) throw new Error(`Insufficient Testnet USDT: requires ${buyQuote.toFixed(2)}`);
  if (sellBase.gt(balance("BTC"))) throw new Error(`Insufficient Testnet BTC: requires ${sellBase.toFixed()}`);
  return rows;
}

export async function placeTestnetGrid(bot: BotRecord, fetcher: Fetcher = fetch) {
  const { baseUrl } = credentials();
  const offset = await timeOffset(fetcher, baseUrl);
  const rows = await buildExecutableGrid(bot, fetcher, offset);
  const placed: TestnetOrderRecord[] = [];
  try {
    for (const row of rows) {
      const digest = await hmacSha256Hex(bot.id, `${bot.version}:${row.grid}:${row.side}:${row.price}:${row.quantity}`);
      const clientOrderId = `aegis-${digest.slice(0, 24)}`;
      const result = await signedRequest<{ orderId: number; clientOrderId: string; status: string }>(fetcher, "POST", "/api/v3/order", {
        symbol: bot.pair,
        side: row.side,
        type: "LIMIT",
        timeInForce: "GTC",
        quantity: row.quantity,
        price: row.price,
        newClientOrderId: clientOrderId,
        newOrderRespType: "RESULT",
      }, offset);
      placed.push({ exchangeOrderId: String(result.orderId), clientOrderId: result.clientOrderId, gridIndex: row.grid, side: row.side, price: row.price, quantity: row.quantity, status: result.status });
    }
    return placed;
  } catch (error) {
    const outcomes = await Promise.allSettled(
      placed.map((order) => cancelTestnetOrder(bot.pair, order.clientOrderId, fetcher)),
    );
    const orphaned = placed.filter((_, index) => outcomes[index].status === "rejected");
    if (orphaned.length > 0) throw new OrphanedTestnetOrdersError(error, orphaned);
    throw error;
  }
}

export async function cancelTestnetOrder(symbol: string, clientOrderId: string, fetcher: Fetcher = fetch) {
  return signedRequest<{ status: string }>(fetcher, "DELETE", "/api/v3/order", {
    symbol,
    origClientOrderId: clientOrderId,
  });
}
