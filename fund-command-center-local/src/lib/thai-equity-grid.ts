import Decimal from "decimal.js-light";
import { buildExactGridPreview, type GridMode, type GridPreviewRow } from "./grid-bot-domain.ts";

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

  const minimumBoardLotValue = new Decimal(input.upperPrice).mul(AOT_PAPER_MARKET.boardLot).toFixed(2);
  return buildExactGridPreview({
    lowerPrice: input.lowerPrice,
    upperPrice: input.upperPrice,
    currentPrice: input.referencePrice,
    investment: input.investment,
    gridCount: input.gridCount,
    mode: input.mode,
    feeRatePct: input.assumedOneWayCostPct,
    tickSize: AOT_PAPER_MARKET.tickSize,
    stepSize: AOT_PAPER_MARKET.boardLot,
    minNotional: minimumBoardLotValue,
  });
}
