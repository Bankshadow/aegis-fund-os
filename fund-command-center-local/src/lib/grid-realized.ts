import Decimal from "decimal.js-light";
import type { BotRecord, TestnetOrderRow } from "./grid-bot-repository.ts";

/**
 * Realized grid-cycle P/L from the durable order ledger.
 *
 * A grid harvests profit one round trip at a time: a BUY fills, its paired SELL
 * one grid line up fills, and the spread minus fees is booked. This pairs
 * `FILLED` buys with `FILLED` sells that sit one grid line apart (arithmetic:
 * `buy + step`; geometric: `buy × ratio`) so only *completed* round trips count
 * as realized — a single filled leg waiting for its partner is reported as open,
 * never as profit. Fees use the same 0.10% per-side estimate as the projection.
 */

export type RealizedCycle = {
  buyPrice: string;
  sellPrice: string;
  quantity: string;
  fees: string;
  profit: string;
};

export type RealizedSummary = {
  cycles: RealizedCycle[];
  realizedProfit: string;
  matchedCycles: number;
  openBuyLegs: number;
  openSellLegs: number;
};

const FEE_RATE = new Decimal("0.001"); // 0.10% per side, matching grid-profit.ts

const config = (bot: BotRecord, key: string) => {
  const item = bot.configuration[key];
  if (typeof item !== "string" && typeof item !== "number") throw new Error(`Missing ${key} configuration`);
  return new Decimal(item);
};

export function computeRealizedCycles(bot: BotRecord, orders: TestnetOrderRow[]): RealizedSummary {
  const lower = config(bot, "lower");
  const upper = config(bot, "upper");
  const grids = config(bot, "grids");
  const geometric = String(bot.configuration.mode) === "GEOMETRIC";
  const step = geometric ? upper.div(lower).pow(new Decimal(1).div(grids)) : upper.sub(lower).div(grids);
  // Expected sell price one grid line above a given buy price.
  const expectedSell = (buy: Decimal) => (geometric ? buy.mul(step) : buy.add(step));

  const filled = orders.filter((order) => order.status === "FILLED");
  const buys = filled
    .filter((order) => order.side === "BUY")
    .map((order) => ({ price: new Decimal(order.price), quantity: new Decimal(order.quantity), used: false }))
    .sort((a, b) => a.price.cmp(b.price));
  const sells = filled
    .filter((order) => order.side === "SELL")
    .map((order) => ({ price: new Decimal(order.price), quantity: new Decimal(order.quantity), used: false }));

  const cycles: RealizedCycle[] = [];
  let realized = new Decimal(0);

  for (const buy of buys) {
    const target = expectedSell(buy.price);
    // A partner sell is "one line up" when it lands within half a step of target
    // (tolerates tick quantization); pick the closest unused sell.
    const tolerance = geometric ? target.sub(buy.price).mul("0.5") : step.mul("0.5");
    let best: (typeof sells)[number] | null = null;
    let bestGap: Decimal | null = null;
    for (const sell of sells) {
      if (sell.used) continue;
      const gap = sell.price.sub(target).abs();
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
    const fees = buy.price.add(best.price).mul(quantity).mul(FEE_RATE);
    const profit = best.price.sub(buy.price).mul(quantity).sub(fees);
    realized = realized.add(profit);
    cycles.push({
      buyPrice: buy.price.toFixed(),
      sellPrice: best.price.toFixed(),
      quantity: quantity.toFixed(),
      fees: fees.toFixed(4),
      profit: profit.toFixed(4),
    });
  }

  return {
    cycles,
    realizedProfit: realized.toFixed(4),
    matchedCycles: cycles.length,
    openBuyLegs: buys.filter((buy) => !buy.used).length,
    openSellLegs: sells.filter((sell) => !sell.used).length,
  };
}
