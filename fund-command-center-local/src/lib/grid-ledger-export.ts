/**
 * Bridge D1 grid fills -> the Python fund-ops ledger.
 *
 * Grid execution lives in D1 (TypeScript) while NAV, XIRR and strategy
 * attribution live in `dynamic_grid` (Python). Without this export the two
 * never meet, so a real fill can never reach the track record. See
 * `docs/FIRST_REAL_TRACK_RECORD.md` § P2 for the locked design decisions.
 *
 * This module is pure: it takes rows and returns a versioned document. It reads
 * nothing, writes nothing, and flows in one direction only — D1 to Python,
 * never back.
 */
import type { TestnetOrderRow } from "./grid-bot-repository.ts";

export const GRID_LEDGER_EXPORT_VERSION = 1;

/** Assets the ledger can value without an operator-approved FX mark. */
export type ReportingCurrency = string;

export type GridLedgerFill = {
  /**
   * Idempotency key handed to the ledger. The clientOrderId is already
   * deterministic per grid level and execution (see `grid-runtime.ts`), so
   * re-exporting the same window can never double-count a fill.
   */
  externalId: string;
  exchangeOrderId: string;
  /** Attribution key: one grid bot is one strategy in the ledger. */
  strategyId: string;
  platform: string;
  accountId: string;
  portfolioId: string;
  instrument: string;
  side: "buy" | "sell";
  quantity: string;
  price: string;
  fee: string;
  feeAsset: string;
  occurredAt: string;
  sourceRef: string;
};

export type GridLedgerRejection = {
  orderId: string;
  clientOrderId: string;
  botId: string;
  reason:
    | "MISSING_FILL_DETAIL"
    | "UNVALUABLE_COMMISSION_ASSET"
    | "INVALID_NUMERIC"
    | "MISSING_SYMBOL_MAPPING";
  detail: string;
};

export type GridLedgerExport = {
  version: number;
  generatedAt: string;
  platform: string;
  accountId: string;
  portfolioId: string;
  reportingCurrency: ReportingCurrency;
  fills: GridLedgerFill[];
  /**
   * Rows that could not be represented faithfully. They are reported, never
   * silently dropped and never exported with an estimate: a track record built
   * on guessed fees is exactly what this project exists to avoid.
   */
  rejected: GridLedgerRejection[];
  sourceRowCount: number;
};

export type GridLedgerExportOptions = {
  platform: string;
  accountId: string;
  portfolioId: string;
  reportingCurrency: ReportingCurrency;
  /** Maps an exchange symbol to its base/quote assets, e.g. BTCUSDT. */
  symbolAssets: Record<string, { base: string; quote: string }>;
  generatedAt: string;
};

const isFinitePositive = (value: string | undefined): value is string =>
  value !== undefined && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) > 0;

const isFiniteNonNegative = (value: string | undefined): value is string =>
  value !== undefined && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0;

/**
 * Convert filled D1 orders into ledger-ready fills.
 *
 * Fails closed on three things rather than inventing a number:
 *  - a FILLED row with no execution detail (migration 0005 not applied yet);
 *  - a commission charged in an asset the ledger cannot value without an
 *    operator-approved mark — including the `MIXED` sentinel;
 *  - any non-numeric or non-positive quantity/price.
 */
export function buildGridLedgerExport(
  orders: TestnetOrderRow[],
  options: GridLedgerExportOptions,
): GridLedgerExport {
  const fills: GridLedgerFill[] = [];
  const rejected: GridLedgerRejection[] = [];
  const filled = orders.filter((order) => order.status === "FILLED");

  for (const order of filled) {
    const reject = (reason: GridLedgerRejection["reason"], detail: string) =>
      rejected.push({
        orderId: order.id,
        clientOrderId: order.clientOrderId,
        botId: order.botId,
        reason,
        detail,
      });

    const assets = options.symbolAssets[order.symbol];
    if (!assets) {
      reject("MISSING_SYMBOL_MAPPING", `no base/quote mapping for ${order.symbol}`);
      continue;
    }

    // Execution detail is what makes the fee real. Without it the only
    // available numbers are the LIMIT price and a flat fee estimate, which must
    // not enter the ledger.
    if (order.filledQuantity === undefined || order.avgFillPrice === undefined) {
      reject(
        "MISSING_FILL_DETAIL",
        "order is FILLED but has no filled_quantity/avg_fill_price; apply migration 0005 and re-reconcile",
      );
      continue;
    }
    if (!isFinitePositive(order.filledQuantity) || !isFinitePositive(order.avgFillPrice)) {
      reject(
        "INVALID_NUMERIC",
        `filledQuantity=${order.filledQuantity} avgFillPrice=${order.avgFillPrice}`,
      );
      continue;
    }

    const commission = order.commission ?? "0";
    const commissionAsset = order.commissionAsset ?? options.reportingCurrency;
    if (!isFiniteNonNegative(commission)) {
      reject("INVALID_NUMERIC", `commission=${order.commission}`);
      continue;
    }
    // The quote asset is the reporting currency here; a fee paid in the base
    // asset or in BNB needs an approved mark, and `MIXED` cannot be valued at
    // all because the original per-asset amounts were already collapsed.
    if (Number(commission) > 0 && commissionAsset !== options.reportingCurrency) {
      reject(
        "UNVALUABLE_COMMISSION_ASSET",
        `commission charged in ${commissionAsset}, reporting currency is ${options.reportingCurrency}; needs an operator-approved mark`,
      );
      continue;
    }

    fills.push({
      externalId: order.clientOrderId,
      exchangeOrderId: order.exchangeOrderId,
      strategyId: order.botId,
      platform: options.platform,
      accountId: options.accountId,
      portfolioId: options.portfolioId,
      instrument: order.symbol,
      side: order.side === "BUY" ? "buy" : "sell",
      quantity: order.filledQuantity,
      price: order.avgFillPrice,
      fee: commission,
      feeAsset: commissionAsset,
      occurredAt: order.updatedAt,
      sourceRef: `d1:grid_bot_orders:${order.id}`,
    });
  }

  return {
    version: GRID_LEDGER_EXPORT_VERSION,
    generatedAt: options.generatedAt,
    platform: options.platform,
    accountId: options.accountId,
    portfolioId: options.portfolioId,
    reportingCurrency: options.reportingCurrency,
    fills: fills.sort((a, b) => a.occurredAt.localeCompare(b.occurredAt) || a.externalId.localeCompare(b.externalId)),
    rejected,
    sourceRowCount: filled.length,
  };
}
