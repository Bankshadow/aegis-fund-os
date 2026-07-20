import Decimal from "decimal.js-light";

/**
 * Aggregate exchange trades into one execution record per order.
 *
 * A single LIMIT order can fill across several trades, so the true execution is
 * the sum: filled quantity = Σ qty, average fill price = Σ quoteQty / Σ qty, and
 * commission = Σ commission. Binance charges commission in the asset received —
 * base for a BUY, quote for a SELL — so the asset is carried alongside the
 * amount instead of being assumed.
 *
 * If one order's trades charged commission in more than one asset we cannot
 * represent it in a single amount, so the asset is reported as `MIXED` with an
 * empty amount; downstream P/L treats that as unvalued and falls back to the
 * estimate rather than silently under-counting fees.
 */

export const MIXED_COMMISSION_ASSET = "MIXED";

export type ExchangeTrade = {
  orderId: number | string;
  qty: string;
  quoteQty: string;
  commission: string;
  commissionAsset: string;
};

export type OrderFill = {
  exchangeOrderId: string;
  filledQuantity: string;
  avgFillPrice: string;
  commission: string;
  commissionAsset: string;
};

export function aggregateFillsByOrder(trades: readonly ExchangeTrade[]): Map<string, OrderFill> {
  type Accumulator = {
    qty: Decimal;
    quote: Decimal;
    commissionByAsset: Map<string, Decimal>;
  };
  const byOrder = new Map<string, Accumulator>();

  for (const trade of trades) {
    const key = String(trade.orderId);
    const acc =
      byOrder.get(key) ?? { qty: new Decimal(0), quote: new Decimal(0), commissionByAsset: new Map() };
    acc.qty = acc.qty.add(trade.qty || 0);
    acc.quote = acc.quote.add(trade.quoteQty || 0);
    const asset = trade.commissionAsset || "";
    if (asset) {
      acc.commissionByAsset.set(
        asset,
        (acc.commissionByAsset.get(asset) ?? new Decimal(0)).add(trade.commission || 0),
      );
    }
    byOrder.set(key, acc);
  }

  const fills = new Map<string, OrderFill>();
  for (const [exchangeOrderId, acc] of byOrder) {
    const assets = [...acc.commissionByAsset.keys()];
    const mixed = assets.length > 1;
    fills.set(exchangeOrderId, {
      exchangeOrderId,
      filledQuantity: acc.qty.toFixed(),
      // Guard against a zero-quantity trade set producing a division by zero.
      avgFillPrice: acc.qty.isZero() ? "0" : acc.quote.div(acc.qty).toFixed(),
      commission: mixed ? "" : (acc.commissionByAsset.get(assets[0]) ?? new Decimal(0)).toFixed(),
      commissionAsset: mixed ? MIXED_COMMISSION_ASSET : (assets[0] ?? ""),
    });
  }
  return fills;
}
