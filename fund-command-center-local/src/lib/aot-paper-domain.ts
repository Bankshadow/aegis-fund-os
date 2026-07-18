import Decimal from "decimal.js-light";
import type { GridMode } from "./grid-bot-domain.ts";

export const AOT_PAPER_RULES = {
  symbol: "AOT",
  market: "SET",
  currency: "THB",
  boardLot: "100",
  tickSize: "0.25",
} as const;
export type PaperStrategyStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "RUNNING"
  | "PAUSED"
  | "STOPPED"
  | "COMPLETED"
  | "ERROR";
export type PaperOrderStatus =
  "CREATED" | "OPEN" | "PARTIALLY_FILLED" | "FILLED" | "CANCELLED" | "REJECTED" | "EXPIRED";
export type PaperSide = "BUY" | "SELL";
export type ValidationLevel = "PASS" | "WARNING" | "BLOCKED";

export type PaperGridConfig = {
  name: string;
  lowerPrice: string;
  upperPrice: string;
  referencePrice: string;
  initialCash: string;
  initialInventory: string;
  levelCount: number;
  mode: GridMode;
  oneWayCostPct: string;
  slippagePct: string;
  maxPositionValue: string;
  maxActiveOrders: number;
  stopLossPrice?: string;
  takeProfitPrice?: string;
};
export type PaperGridLevel = {
  index: number;
  side: PaperSide | "REFERENCE";
  price: string;
  quantity: string;
  notional: string;
  pairedPrice?: string;
  grossProfit: string;
  buyCost: string;
  sellCost: string;
  slippage: string;
  netProfit: string;
  returnOnCapital: string;
};
export type PaperValidation = { level: ValidationLevel; code: string; message: string };
export type PaperOrder = {
  id: string;
  gridIndex: number;
  side: PaperSide;
  limitPrice: string;
  originalQuantity: string;
  filledQuantity: string;
  remainingQuantity: string;
  averageFillPrice: string;
  status: PaperOrderStatus;
  reservedAmount: string;
};
export type PaperAccount = {
  initialCash: string;
  cash: string;
  inventory: string;
  averageCost: string;
  realizedGridProfit: string;
  realizedAssetPnl: string;
  costs: string;
  slippage: string;
  currentPrice: string;
  maxDrawdown: string;
  completedCycles: number;
};

const d = (value: string | number | Decimal) => new Decimal(value);
const tick = d(AOT_PAPER_RULES.tickSize);
const lot = d(AOT_PAPER_RULES.boardLot);
const quantize = (value: Decimal) =>
  value.div(tick).toDecimalPlaces(0, Decimal.ROUND_HALF_UP).mul(tick);
const floorLot = (value: Decimal) =>
  value.div(lot).toDecimalPlaces(0, Decimal.ROUND_FLOOR).mul(lot);
const fixed = (value: Decimal) => value.toFixed(2);

export function calculatePaperGrid(config: PaperGridConfig): {
  levels: PaperGridLevel[];
  validation: PaperValidation[];
  requiredCash: string;
  requiredInventory: string;
  maxPositionValue: string;
} {
  const validation: PaperValidation[] = [];
  const lower = d(config.lowerPrice),
    upper = d(config.upperPrice),
    reference = d(config.referencePrice),
    capital = d(config.initialCash),
    inventory = d(config.initialInventory);
  if (!lower.gt(0) || !upper.gt(lower) || !reference.gt(lower) || !reference.lt(upper))
    validation.push({
      level: "BLOCKED",
      code: "RANGE",
      message: "Lower < reference < upper is required.",
    });
  if (!Number.isInteger(config.levelCount) || config.levelCount < 3)
    validation.push({
      level: "BLOCKED",
      code: "LEVELS",
      message: "At least three price intervals are required.",
    });
  if (!capital.gt(0))
    validation.push({
      level: "BLOCKED",
      code: "CASH",
      message: "Initial paper cash must be positive.",
    });
  if (!d(config.oneWayCostPct).gte(0) || !d(config.slippagePct).gte(0))
    validation.push({
      level: "BLOCKED",
      code: "COST",
      message: "Costs and slippage cannot be negative.",
    });
  if (validation.some((item) => item.level === "BLOCKED"))
    return {
      levels: [],
      validation,
      requiredCash: "0.00",
      requiredInventory: "0",
      maxPositionValue: "0.00",
    };
  const ratio = upper.div(lower).pow(d(1).div(config.levelCount));
  const prices = Array.from({ length: config.levelCount + 1 }, (_, index) =>
    quantize(
      config.mode === "GEOMETRIC"
        ? lower.mul(ratio.pow(index))
        : lower.add(upper.sub(lower).mul(index).div(config.levelCount)),
    ),
  );
  if (new Set(prices.map(String)).size !== prices.length)
    validation.push({
      level: "BLOCKED",
      code: "DUPLICATE_TICK",
      message: "Two grid levels collapse to the same tick price.",
    });
  const referenceIndex = prices.reduce(
    (best, price, index) =>
      price.sub(reference).abs().lt(prices[best].sub(reference).abs()) ? index : best,
    0,
  );
  const perOrderCash = capital.div(Math.max(1, referenceIndex));
  const costRate = d(config.oneWayCostPct).div(100),
    slipRate = d(config.slippagePct).div(100);
  const levels = prices.map((price, index): PaperGridLevel => {
    if (index === referenceIndex)
      return {
        index: index + 1,
        side: "REFERENCE",
        price: fixed(price),
        quantity: "0",
        notional: "0.00",
        grossProfit: "0.00",
        buyCost: "0.00",
        sellCost: "0.00",
        slippage: "0.00",
        netProfit: "0.00",
        returnOnCapital: "0.00",
      };
    const side: PaperSide = index < referenceIndex ? "BUY" : "SELL";
    const paired = prices[index + (side === "BUY" ? 1 : -1)];
    const quantity = floorLot(perOrderCash.div(price));
    const notional = price.mul(quantity),
      exitNotional = paired.mul(quantity);
    const buyNotional = side === "BUY" ? notional : exitNotional;
    const sellNotional = side === "SELL" ? notional : exitNotional;
    const buyCost = buyNotional.mul(costRate),
      sellCost = sellNotional.mul(costRate),
      slippage = buyNotional.add(sellNotional).mul(slipRate);
    const gross = paired.sub(price).abs().mul(quantity),
      net = gross.sub(buyCost).sub(sellCost).sub(slippage);
    return {
      index: index + 1,
      side,
      price: fixed(price),
      quantity: quantity.toFixed(0),
      notional: fixed(notional),
      pairedPrice: fixed(paired),
      grossProfit: fixed(gross),
      buyCost: fixed(buyCost),
      sellCost: fixed(sellCost),
      slippage: fixed(slippage),
      netProfit: fixed(net),
      returnOnCapital: notional.eq(0) ? "0.00" : fixed(net.div(notional).mul(100)),
    };
  });
  const buys = levels.filter((row) => row.side === "BUY"),
    sells = levels.filter((row) => row.side === "SELL");
  const requiredCash = buys.reduce((sum, row) => sum.add(row.notional), d(0));
  const requiredInventory = sells.reduce((sum, row) => sum.add(row.quantity), d(0));
  const maxPosition = requiredCash.add(inventory.mul(reference));
  if (requiredCash.gt(capital))
    validation.push({
      level: "BLOCKED",
      code: "INSUFFICIENT_CASH",
      message: "Paper cash cannot reserve all buy orders.",
    });
  if (requiredInventory.gt(inventory))
    validation.push({
      level: "BLOCKED",
      code: "INSUFFICIENT_INVENTORY",
      message: "Paper inventory cannot reserve all sell orders.",
    });
  if (maxPosition.gt(d(config.maxPositionValue)))
    validation.push({
      level: "BLOCKED",
      code: "MAX_POSITION",
      message: "Maximum position value would be exceeded.",
    });
  if (buys.length + sells.length > config.maxActiveOrders)
    validation.push({
      level: "BLOCKED",
      code: "MAX_ORDERS",
      message: "Maximum active order count would be exceeded.",
    });
  if (
    levels.some(
      (row) => row.side !== "REFERENCE" && (!d(row.quantity).gte(lot) || !d(row.netProfit).gt(0)),
    )
  )
    validation.push({
      level: "BLOCKED",
      code: "NET_PROFIT",
      message: "Every order must have one board lot and positive estimated net grid profit.",
    });
  if (prices.length > 1 && prices[1].sub(prices[0]).div(reference).lt("0.005"))
    validation.push({
      level: "WARNING",
      code: "NARROW_GRID",
      message: "Grid spacing is narrow relative to simulated costs.",
    });
  if (!validation.length)
    validation.push({
      level: "PASS",
      code: "READY",
      message: "Paper capital, inventory, tick and lot validations passed.",
    });
  return {
    levels,
    validation,
    requiredCash: fixed(requiredCash),
    requiredInventory: requiredInventory.toFixed(0),
    maxPositionValue: fixed(maxPosition),
  };
}

export function simulatePaperFill(
  order: PaperOrder,
  account: PaperAccount,
  price: string,
  quantity: string,
): { order: PaperOrder; account: PaperAccount } {
  const fillQty = d(quantity),
    remaining = d(order.remainingQuantity),
    fillPrice = d(price);
  if (!fillQty.gt(0) || fillQty.gt(remaining))
    throw new Error("Fill quantity exceeds remaining paper order quantity");
  const notional = fillQty.mul(fillPrice),
    cost = notional.mul("0.002");
  const nextFilled = d(order.filledQuantity).add(fillQty),
    nextRemaining = remaining.sub(fillQty);
  let cash = d(account.cash),
    inventory = d(account.inventory),
    averageCost = d(account.averageCost),
    realizedAssetPnl = d(account.realizedAssetPnl);
  if (order.side === "BUY") {
    if (cash.lt(notional.add(cost))) throw new Error("Insufficient paper cash");
    cash = cash.sub(notional).sub(cost);
    averageCost = inventory.add(fillQty).eq(0)
      ? d(0)
      : inventory.mul(averageCost).add(notional).div(inventory.add(fillQty));
    inventory = inventory.add(fillQty);
  } else {
    if (inventory.lt(fillQty)) throw new Error("Insufficient paper inventory");
    cash = cash.add(notional).sub(cost);
    realizedAssetPnl = realizedAssetPnl.add(fillPrice.sub(averageCost).mul(fillQty));
    inventory = inventory.sub(fillQty);
  }
  const nextOrder = {
    ...order,
    filledQuantity: nextFilled.toFixed(0),
    remainingQuantity: nextRemaining.toFixed(0),
    averageFillPrice: fillPrice.toFixed(2),
    status: (nextRemaining.eq(0) ? "FILLED" : "PARTIALLY_FILLED") as PaperOrderStatus,
  };
  return {
    order: nextOrder,
    account: {
      ...account,
      cash: fixed(cash),
      inventory: inventory.toFixed(0),
      averageCost: fixed(averageCost),
      realizedAssetPnl: fixed(realizedAssetPnl),
      costs: fixed(d(account.costs).add(cost)),
      currentPrice: fixed(fillPrice),
    },
  };
}
