import Decimal from "decimal.js-light";
import type { BotRecord, TestnetOrderRow } from "./grid-bot-repository.ts";
import { MIXED_COMMISSION_ASSET } from "./grid-fills.ts";

/**
 * Realized grid-cycle P/L from the durable order ledger.
 *
 * A grid harvests profit one round trip at a time: a BUY fills, its paired SELL
 * one grid line up fills, and the spread minus fees is booked. Only *completed*
 * round trips count as realized — a single filled leg waiting for its partner is
 * reported as open, never as profit.
 *
 * Two prices matter and they are deliberately kept apart:
 *  - **Pairing** uses each order's LIMIT price, because that is the grid line
 *    geometry that decides which buy belongs to which sell.
 *  - **Profit** uses the actual average fill price and the real commission the
 *    exchange charged (migration 0005), so the number is measured rather than
 *    modelled. Rows without execution detail fall back to the LIMIT price and a
 *    0.10%/side estimate, and every cycle reports which basis it used.
 *
 * Binance charges commission in the asset received (base on a BUY, quote on a
 * SELL), so a base-asset fee is valued at that leg's own fill price. A fee in
 * some third asset, or mixed assets on one order, cannot be valued here and
 * falls back to the estimate instead of being silently dropped.
 */

export type FeeBasis = "actual" | "estimated";

export type RealizedCycle = {
  buyPrice: string;
  sellPrice: string;
  quantity: string;
  fees: string;
  profit: string;
  feeBasis: FeeBasis;
};

export type RealizedSummary = {
  cycles: RealizedCycle[];
  realizedProfit: string;
  matchedCycles: number;
  openBuyLegs: number;
  openSellLegs: number;
  /** True when every matched cycle priced its fees from real commissions. */
  allFeesActual: boolean;
};

const FEE_RATE = new Decimal("0.001"); // 0.10% per side, matching grid-profit.ts

const config = (bot: BotRecord, key: string) => {
  const item = bot.configuration[key];
  if (typeof item !== "string" && typeof item !== "number") throw new Error(`Missing ${key} configuration`);
  return new Decimal(item);
};

/** Split a symbol into base/quote for fee valuation (execution is BTCUSDT-locked). */
const splitPair = (pair: string) => {
  for (const quote of ["USDT", "USDC", "BUSD", "TUSD"]) {
    if (pair.endsWith(quote)) return { base: pair.slice(0, -quote.length), quote };
  }
  return { base: pair, quote: "" };
};

type Leg = {
  /** Grid line — used only for pairing. */
  limitPrice: Decimal;
  /** What the order actually executed at (falls back to the limit price). */
  execPrice: Decimal;
  quantity: Decimal;
  commission?: Decimal;
  commissionAsset?: string;
  used: boolean;
};

const toLeg = (order: TestnetOrderRow): Leg => {
  const limitPrice = new Decimal(order.price);
  const execPrice =
    order.avgFillPrice && new Decimal(order.avgFillPrice).gt(0) ? new Decimal(order.avgFillPrice) : limitPrice;
  const quantity =
    order.filledQuantity && new Decimal(order.filledQuantity).gt(0)
      ? new Decimal(order.filledQuantity)
      : new Decimal(order.quantity);
  return {
    limitPrice,
    execPrice,
    quantity,
    commission: order.commission ? new Decimal(order.commission) : undefined,
    commissionAsset: order.commissionAsset,
    used: false,
  };
};

/**
 * Value one leg's fee in the quote asset, or return null when the real
 * commission cannot be valued and the caller must fall back to the estimate.
 */
const actualFeeInQuote = (leg: Leg, base: string, quote: string): Decimal | null => {
  if (!leg.commission || !leg.commissionAsset) return null;
  if (leg.commissionAsset === MIXED_COMMISSION_ASSET) return null;
  if (quote && leg.commissionAsset === quote) return leg.commission;
  if (leg.commissionAsset === base) return leg.commission.mul(leg.execPrice);
  return null; // e.g. BNB — needs an approved mark we do not have here
};

export function computeRealizedCycles(bot: BotRecord, orders: TestnetOrderRow[]): RealizedSummary {
  const lower = config(bot, "lower");
  const upper = config(bot, "upper");
  const grids = config(bot, "grids");
  const geometric = String(bot.configuration.mode) === "GEOMETRIC";
  const step = geometric ? upper.div(lower).pow(new Decimal(1).div(grids)) : upper.sub(lower).div(grids);
  const expectedSell = (buy: Decimal) => (geometric ? buy.mul(step) : buy.add(step));
  const { base, quote } = splitPair(bot.pair);

  const filled = orders.filter((order) => order.status === "FILLED");
  const buys = filled
    .filter((order) => order.side === "BUY")
    .map(toLeg)
    .sort((a, b) => a.limitPrice.cmp(b.limitPrice));
  const sells = filled.filter((order) => order.side === "SELL").map(toLeg);

  const cycles: RealizedCycle[] = [];
  let realized = new Decimal(0);
  let allFeesActual = true;

  for (const buy of buys) {
    const target = expectedSell(buy.limitPrice);
    // A partner sell is "one line up" when it lands within half a step of target
    // (tolerates tick quantization); pick the closest unused sell.
    const tolerance = geometric ? target.sub(buy.limitPrice).mul("0.5") : step.mul("0.5");
    let best: Leg | null = null;
    let bestGap: Decimal | null = null;
    for (const sell of sells) {
      if (sell.used) continue;
      const gap = sell.limitPrice.sub(target).abs();
      if (gap.gt(tolerance)) continue;
      if (bestGap === null || gap.lt(bestGap)) {
        best = sell;
        bestGap = gap;
      }
    }
    if (!best) continue;
    best.used = true;
    buy.used = true;

    const quantity = buy.quantity.lt(best.quantity) ? buy.quantity : best.quantity;
    const buyFee = actualFeeInQuote(buy, base, quote);
    const sellFee = actualFeeInQuote(best, base, quote);
    const feeBasis: FeeBasis = buyFee !== null && sellFee !== null ? "actual" : "estimated";
    if (feeBasis === "estimated") allFeesActual = false;
    const fees =
      feeBasis === "actual"
        ? buyFee!.add(sellFee!)
        : buy.execPrice.add(best.execPrice).mul(quantity).mul(FEE_RATE);
    const profit = best.execPrice.sub(buy.execPrice).mul(quantity).sub(fees);

    realized = realized.add(profit);
    cycles.push({
      buyPrice: buy.execPrice.toFixed(),
      sellPrice: best.execPrice.toFixed(),
      quantity: quantity.toFixed(),
      fees: fees.toFixed(4),
      profit: profit.toFixed(4),
      feeBasis,
    });
  }

  return {
    cycles,
    realizedProfit: realized.toFixed(4),
    matchedCycles: cycles.length,
    openBuyLegs: buys.filter((buy) => !buy.used).length,
    openSellLegs: sells.filter((sell) => !sell.used).length,
    allFeesActual: cycles.length === 0 ? true : allFeesActual,
  };
}
