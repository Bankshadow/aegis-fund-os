export type PaperGridLevel = {
  id: string;
  side: "BUY" | "SELL";
  price: number;
  quantity: number;
  status: "SIMULATED_PENDING";
};

export type PaperGridRules = {
  tickSize: number;
  stepSize: number;
  minNotional: number;
};

export type GridSpacingMode = "ARITHMETIC" | "GEOMETRIC";

export type BinanceStyleGridInput = {
  lowerPrice: number;
  upperPrice: number;
  gridCount: number;
  investment: number;
  mode: GridSpacingMode;
  feeRatePct: number;
  triggerPrice?: number;
  takeProfit?: number;
  stopLoss?: number;
  trailingUp?: boolean;
  sellAllOnStop?: boolean;
};

export type BinanceStyleGridSetup = {
  levels: PaperGridLevel[];
  estimatedProfitPerGridPct: { min: number; max: number };
  input: BinanceStyleGridInput;
};

const floorTo = (value: number, increment: number) => {
  const units = Math.floor(value / increment + 1e-9);
  return Number((units * increment).toFixed(12));
};

export function buildBinanceStyleGridSetup(
  midPrice: number,
  input: BinanceStyleGridInput,
  rules: PaperGridRules,
): BinanceStyleGridSetup {
  const { lowerPrice, upperPrice, gridCount, investment, mode, feeRatePct } = input;
  if (!Number.isFinite(midPrice) || midPrice <= 0) throw new Error("Market price must be positive");
  if (!(lowerPrice > 0) || !(upperPrice > lowerPrice)) throw new Error("Price range is invalid");
  if (midPrice < lowerPrice || midPrice > upperPrice) throw new Error("Market price must be inside the grid range");
  if (!Number.isInteger(gridCount) || gridCount < 2 || gridCount > 200)
    throw new Error("Number of grids must be between 2 and 200");
  if (!(investment > 0)) throw new Error("Investment must be positive");
  if (!(feeRatePct >= 0) || feeRatePct > 1) throw new Error("Fee rate must be between 0% and 1%");
  if (!(rules.tickSize > 0) || !(rules.stepSize > 0) || rules.minNotional < 0)
    throw new Error("Invalid Binance symbol rules");
  if (input.triggerPrice !== undefined && !(input.triggerPrice > 0)) throw new Error("Trigger price must be positive");
  if (input.takeProfit !== undefined && input.takeProfit <= upperPrice)
    throw new Error("Take profit must be above the upper price");
  if (input.stopLoss !== undefined && input.stopLoss >= lowerPrice)
    throw new Error("Stop loss must be below the lower price");

  const notionalPerGrid = investment / gridCount;
  if (notionalPerGrid < rules.minNotional) throw new Error("Investment per grid is below Binance minimum");
  const ratio = Math.pow(upperPrice / lowerPrice, 1 / gridCount);
  const rawPrices = Array.from({ length: gridCount + 1 }, (_, index) =>
    mode === "GEOMETRIC"
      ? lowerPrice * Math.pow(ratio, index)
      : lowerPrice + ((upperPrice - lowerPrice) * index) / gridCount,
  );
  const prices = [...new Set(rawPrices.map((price) => floorTo(price, rules.tickSize)))];
  if (prices.length !== rawPrices.length) throw new Error("Price range is too narrow for the Binance tick size");
  const nearestMarketIndex = prices.reduce(
    (best, price, index) => Math.abs(price - midPrice) < Math.abs(prices[best] - midPrice) ? index : best,
    0,
  );
  const levels = prices
    .filter((_, index) => index !== nearestMarketIndex)
    .map((price, index) => ({
      id: `PAPER-GRID-${index + 1}`,
      side: price < midPrice ? "BUY" as const : "SELL" as const,
      price,
      quantity: floorTo(notionalPerGrid / price, rules.stepSize),
      status: "SIMULATED_PENDING" as const,
    }));
  if (levels.some((level) => level.quantity <= 0 || level.price * level.quantity < rules.minNotional))
    throw new Error("Quantized order value is below Binance minimum");
  const grossPcts = prices.slice(0, -1).map((price, index) => (prices[index + 1] / price - 1) * 100);
  const netPcts = grossPcts.map((value) => value - feeRatePct * 2);
  if (netPcts.some((value) => value <= 0)) throw new Error("Grid profit does not cover estimated round-trip fees");
  return {
    levels,
    estimatedProfitPerGridPct: { min: Math.min(...netPcts), max: Math.max(...netPcts) },
    input,
  };
}

export function buildPaperGridLevels(
  midPrice: number,
  capitalUsdt: number,
  levelCount = 3,
  spacingPct = 0.005,
  rules: PaperGridRules = { tickSize: 0.01, stepSize: 0.00000001, minNotional: 0 },
): PaperGridLevel[] {
  if (!Number.isFinite(midPrice) || midPrice <= 0) throw new Error("midPrice must be positive");
  if (!Number.isFinite(capitalUsdt) || capitalUsdt <= 0)
    throw new Error("capitalUsdt must be positive");
  if (!Number.isInteger(levelCount) || levelCount < 1 || levelCount > 20)
    throw new Error("levelCount must be between 1 and 20");
  if (!Number.isFinite(spacingPct) || spacingPct <= 0 || spacingPct > 0.1)
    throw new Error("spacingPct must be between 0 and 0.1");
  if (!(rules.tickSize > 0) || !(rules.stepSize > 0) || rules.minNotional < 0)
    throw new Error("invalid Binance symbol rules");

  const notionalPerLevel = capitalUsdt / (levelCount * 2);
  if (notionalPerLevel < rules.minNotional)
    throw new Error("notional per level is below Binance minimum");
  return Array.from({ length: levelCount }, (_, index) => index + 1).flatMap((distance) => {
    const buyPrice = floorTo(midPrice * (1 - spacingPct * distance), rules.tickSize);
    const sellPrice = floorTo(midPrice * (1 + spacingPct * distance), rules.tickSize);
    return [
      {
        id: `PAPER-BUY-${distance}`,
        side: "BUY" as const,
        price: buyPrice,
        quantity: floorTo(notionalPerLevel / buyPrice, rules.stepSize),
        status: "SIMULATED_PENDING" as const,
      },
      {
        id: `PAPER-SELL-${distance}`,
        side: "SELL" as const,
        price: sellPrice,
        quantity: floorTo(notionalPerLevel / sellPrice, rules.stepSize),
        status: "SIMULATED_PENDING" as const,
      },
    ];
  });
}
