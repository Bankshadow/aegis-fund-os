import Decimal from "decimal.js-light";
import type { GridMode, GridPreviewRow } from "./grid-bot-domain.ts";

export const AOT_PAPER_MARKET = {
  symbol: "AOT",
  currency: "THB",
  boardLot: "100",
  tickSize: "0.25",
} as const;

export type AotPaperGridInput = {
  lowerPrice: string;
  upperPrice: string;
  referencePrice: string;
  investment: string;
  gridCount: number;
  mode: GridMode;
  assumedOneWayCostPct: string;
};

const isTickAligned = (value: string) => new Decimal(value).mod(AOT_PAPER_MARKET.tickSize).eq(0);
const floorIncrement = (value: Decimal, increment: Decimal) =>
  value.div(increment).toDecimalPlaces(0, Decimal.ROUND_FLOOR).mul(increment);

/**
 * Local-only AOT grid preview. This has no broker, order, credential, or
 * transport dependency; it merely applies SET-style board-lot and tick rules
 * to an illustrative, operator-entered reference price.
 */
export function buildAotPaperGrid(input: AotPaperGridInput): GridPreviewRow[] {
  for (const [label, value] of [
    ["Lower price", input.lowerPrice],
    ["Upper price", input.upperPrice],
    ["Reference price", input.referencePrice],
  ] as const) {
    if (!isTickAligned(value)) throw new Error(`${label} must use the ฿${AOT_PAPER_MARKET.tickSize} paper tick`);
  }

  const lower = new Decimal(input.lowerPrice);
  const upper = new Decimal(input.upperPrice);
  const current = new Decimal(input.referencePrice);
  const capital = new Decimal(input.investment);
  const costRate = new Decimal(input.assumedOneWayCostPct).div(100);
  const tick = new Decimal(AOT_PAPER_MARKET.tickSize);
  const lot = new Decimal(AOT_PAPER_MARKET.boardLot);
  if (!lower.gt(0) || !upper.gt(lower) || !current.gte(lower) || !current.lte(upper))
    throw new Error("Reference price must be inside the configured range");
  if (!Number.isInteger(input.gridCount) || input.gridCount < 2 || input.gridCount > 200)
    throw new Error("Grid count must be between 2 and 200");

  const perGrid = capital.div(input.gridCount);
  const minimumBoardLotValue = upper.mul(lot);
  if (perGrid.lt(minimumBoardLotValue))
    throw new Error("Investment per grid is below minimum notional for one AOT board lot");
  const ratio = upper.div(lower).pow(new Decimal(1).div(input.gridCount));
  const prices = Array.from({ length: input.gridCount + 1 }, (_, index) =>
    floorIncrement(
      input.mode === "GEOMETRIC"
        ? lower.mul(ratio.pow(index))
        : lower.add(upper.sub(lower).mul(index).div(input.gridCount)),
      tick,
    ),
  );
  const nearest = prices.reduce(
    (best, price, index) => (price.sub(current).abs().lt(prices[best].sub(current).abs()) ? index : best),
    0,
  );

  return prices.flatMap((price, index) => {
    if (index === nearest) return [];
    const side = price.lt(current) ? "BUY" : "SELL";
    const pairedPrice = side === "BUY" ? prices[index + 1] : prices[index - 1];
    const quantity = floorIncrement(perGrid.div(price), lot);
    const quote = price.mul(quantity);
    if (quantity.lt(lot) || quote.lt(minimumBoardLotValue))
      throw new Error("Quantized order is below minimum notional for one AOT board lot");
    const fee = quote.mul(costRate);
    const pairedFee = pairedPrice.mul(quantity).mul(costRate);
    const net = pairedPrice.sub(price).abs().mul(quantity).sub(fee).sub(pairedFee);
    return [{
      grid: index + 1,
      side,
      price: price.toFixed(2),
      quantity: quantity.toFixed(0),
      quoteValue: quote.toFixed(2),
      estimatedFee: fee.toFixed(2),
      estimatedNetProfit: net.toFixed(2),
      initialState: "PREVIEW" as const,
    }];
  });
}
