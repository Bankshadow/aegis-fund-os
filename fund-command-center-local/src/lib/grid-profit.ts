import Decimal from "decimal.js-light";
import type { BotRecord, TestnetOrderRow } from "./grid-bot-repository";

export type GridProfitProjection = { gridIndex: number; side: "BUY" | "SELL"; entryPrice: string; targetPrice: string; quantity: string; estimatedFees: string; estimatedCycleProfit: string; orderStatus: string };

const value = (config: BotRecord["configuration"], key: string) => {
  const item = config[key];
  if (typeof item !== "string" && typeof item !== "number") throw new Error(`Missing ${key} configuration`);
  return new Decimal(item);
};

/** Fee-aware projection only; exchange acknowledgements are not realized P/L. */
export const projectGridCycleProfit = (bot: BotRecord, order: TestnetOrderRow): GridProfitProjection => {
  const lower = value(bot.configuration, "lower");
  const upper = value(bot.configuration, "upper");
  const grids = value(bot.configuration, "grids");
  const mode = String(bot.configuration.mode);
  const entry = new Decimal(order.price);
  const quantity = new Decimal(order.quantity);
  const step = mode === "GEOMETRIC" ? upper.div(lower).pow(new Decimal(1).div(grids)) : upper.sub(lower).div(grids);
  const target = order.side === "BUY" ? (mode === "GEOMETRIC" ? entry.mul(step) : entry.add(step)) : (mode === "GEOMETRIC" ? entry.div(step) : entry.sub(step));
  const fees = entry.add(target).mul(quantity).mul("0.001");
  return { gridIndex: order.gridIndex, side: order.side, entryPrice: entry.toFixed(), targetPrice: target.toFixed(), quantity: quantity.toFixed(), estimatedFees: fees.toFixed(4), estimatedCycleProfit: target.sub(entry).abs().mul(quantity).sub(fees).toFixed(4), orderStatus: order.status };
};

export const projectedGridProfitTotal = (items: GridProfitProjection[]) => items.reduce((total, item) => total.add(item.estimatedCycleProfit), new Decimal(0)).toFixed(4);
