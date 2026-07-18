import Decimal from "decimal.js-light";

export type BotEnvironment = "DEMO" | "PAPER" | "BINANCE_TESTNET";
export type BotState =
  | "DRAFT"
  | "IDLE"
  | "PENDING_APPROVAL"
  | "WAITING_FOR_TRIGGER"
  | "RUNNING"
  | "PAUSED"
  | "STOPPED"
  | "RECOVERY_REQUIRED";
export type GridMode = "ARITHMETIC" | "GEOMETRIC";
export type GridOrderStatus = "OPEN" | "PARTIALLY_FILLED" | "FILLED" | "RECONCILIATION_REQUIRED";
export type GridOrder = {
  id: string;
  grid: number;
  side: "BUY" | "SELL";
  price: string;
  quantity: string;
  quoteValue: string;
  fee: string;
  status: GridOrderStatus;
  createdAt: string;
};
export type GridCycle = {
  id: string;
  buyPrice: string;
  sellPrice: string;
  quantity: string;
  fee: string;
  profit: string;
  completedAt: string;
};
export type GridBot = {
  id: string;
  name: string;
  pair: string;
  strategy: string;
  strategyId: string;
  strategyVersion: string;
  environment: BotEnvironment;
  state: BotState;
  lowerPrice: string;
  upperPrice: string;
  currentPrice: string;
  investment: string;
  gridCount: number;
  mode: GridMode;
  gridProfit: string;
  unrealizedPnl: string;
  matchedCycles: number;
  openOrders: number;
  runtime: string;
  lastEvent: string;
  risk: "PASS" | "PASS_WITH_WARNING" | "MANUAL_REVIEW_REQUIRED";
  createdBy: string;
  approvedBy: string | null;
  orders: GridOrder[];
  cycles: GridCycle[];
};

export type GridPreviewInput = {
  lowerPrice: string;
  upperPrice: string;
  currentPrice: string;
  investment: string;
  gridCount: number;
  mode: GridMode;
  feeRatePct: string;
  tickSize: string;
  stepSize: string;
  minNotional: string;
};
export type GridPreviewRow = {
  grid: number;
  side: "BUY" | "SELL";
  price: string;
  quantity: string;
  quoteValue: string;
  estimatedFee: string;
  estimatedNetProfit: string;
  initialState: "PREVIEW";
};

const floorIncrement = (value: Decimal, increment: Decimal) =>
  value.div(increment).toDecimalPlaces(0, Decimal.ROUND_FLOOR).mul(increment);
export function buildExactGridPreview(input: GridPreviewInput): GridPreviewRow[] {
  const lower = new Decimal(input.lowerPrice),
    upper = new Decimal(input.upperPrice),
    current = new Decimal(input.currentPrice);
  const investment = new Decimal(input.investment),
    tick = new Decimal(input.tickSize),
    step = new Decimal(input.stepSize);
  const minNotional = new Decimal(input.minNotional),
    feeRate = new Decimal(input.feeRatePct).div(100);
  if (!lower.gt(0) || !upper.gt(lower) || !current.gte(lower) || !current.lte(upper))
    throw new Error("Current price must be inside the configured range");
  if (!Number.isInteger(input.gridCount) || input.gridCount < 2 || input.gridCount > 200)
    throw new Error("Grid count must be between 2 and 200");
  const perGrid = investment.div(input.gridCount);
  if (perGrid.lt(minNotional)) throw new Error("Investment per grid is below minimum notional");
  const ratio = upper.div(lower).pow(new Decimal(1).div(input.gridCount));
  const prices = Array.from({ length: input.gridCount + 1 }, (_, i) =>
    floorIncrement(
      input.mode === "GEOMETRIC"
        ? lower.mul(ratio.pow(i))
        : lower.add(upper.sub(lower).mul(i).div(input.gridCount)),
      tick,
    ),
  );
  const nearest = prices.reduce(
    (best, p, i) => (p.sub(current).abs().lt(prices[best].sub(current).abs()) ? i : best),
    0,
  );
  return prices
    .filter((_, i) => i !== nearest)
    .map((price, index) => {
      const quantity = floorIncrement(perGrid.div(price), step),
        quote = price.mul(quantity),
        fee = quote.mul(feeRate);
      if (quote.lt(minNotional)) throw new Error("Quantized order is below minimum notional");
      const adjacent = prices[Math.min(index + 1, prices.length - 1)];
      const net = adjacent.sub(price).abs().mul(quantity).sub(fee.mul(2));
      return {
        grid: index + 1,
        side: price.lt(current) ? "BUY" : "SELL",
        price: price.toFixed(),
        quantity: quantity.toFixed(),
        quoteValue: quote.toFixed(2),
        estimatedFee: fee.toFixed(4),
        estimatedNetProfit: net.toFixed(4),
        initialState: "PREVIEW",
      };
    });
}

const order = (
  id: string,
  grid: number,
  side: "BUY" | "SELL",
  price: string,
  status: GridOrderStatus = "OPEN",
): GridOrder => ({
  id,
  grid,
  side,
  price,
  quantity: "0.01000",
  quoteValue: new Decimal(price).mul("0.01").toFixed(2),
  fee: "0.0642",
  status,
  createdAt: "2026-07-16 19:10 ICT",
});
export const GRID_BOTS: GridBot[] = [
  {
    id: "BOT-T-104",
    name: "BTC Testnet Range",
    pair: "BTCUSDT",
    strategy: "Dual Grid 75/25",
    strategyId: "STR-DG-75-25",
    strategyVersion: "v1.4",
    environment: "BINANCE_TESTNET",
    state: "RUNNING",
    lowerPrice: "57800",
    upperPrice: "70600",
    currentPrice: "64242",
    investment: "12000",
    gridCount: 20,
    mode: "ARITHMETIC",
    gridProfit: "184.20",
    unrealizedPnl: "-42.80",
    matchedCycles: 18,
    openOrders: 4,
    runtime: "2d 4h",
    lastEvent: "Price update · 2s ago",
    risk: "PASS",
    createdBy: "Somchai P.",
    approvedBy: "Preecha S.",
    orders: [
      order("T-8821", 9, "BUY", "62960"),
      order("T-8822", 10, "BUY", "63600", "PARTIALLY_FILLED"),
      order("T-8823", 12, "SELL", "64884"),
      order("T-8824", 13, "SELL", "65527"),
    ],
    cycles: [
      {
        id: "CYC-044",
        buyPrice: "62960",
        sellPrice: "63600",
        quantity: "0.01",
        fee: "0.1266",
        profit: "6.2734",
        completedAt: "2026-07-16 18:42 ICT",
      },
    ],
  },
  {
    id: "BOT-P-105",
    name: "ETH Regime Grid",
    pair: "ETHUSDT",
    strategy: "Percentile Router",
    strategyId: "STR-PCT-02",
    strategyVersion: "v2.1",
    environment: "PAPER",
    state: "WAITING_FOR_TRIGGER",
    lowerPrice: "1750",
    upperPrice: "2150",
    currentPrice: "1924.67",
    investment: "8000",
    gridCount: 24,
    mode: "GEOMETRIC",
    gridProfit: "0",
    unrealizedPnl: "0",
    matchedCycles: 0,
    openOrders: 0,
    runtime: "—",
    lastEvent: "Awaiting trigger",
    risk: "PASS_WITH_WARNING",
    createdBy: "Anong K.",
    approvedBy: "Niran C.",
    orders: [],
    cycles: [],
  },
  {
    id: "BOT-D-106",
    name: "BTC Recovery Drill",
    pair: "BTCUSDT",
    strategy: "Dual Grid 75/25",
    strategyId: "STR-DG-75-25",
    strategyVersion: "v1.4",
    environment: "DEMO",
    state: "RECOVERY_REQUIRED",
    lowerPrice: "60000",
    upperPrice: "68000",
    currentPrice: "64242",
    investment: "5000",
    gridCount: 12,
    mode: "ARITHMETIC",
    gridProfit: "31.20",
    unrealizedPnl: "-88.00",
    matchedCycles: 4,
    openOrders: 1,
    runtime: "6h 12m",
    lastEvent: "Unknown exchange order",
    risk: "MANUAL_REVIEW_REQUIRED",
    createdBy: "Developer",
    approvedBy: null,
    orders: [order("D-9001", 7, "SELL", "64667", "RECONCILIATION_REQUIRED")],
    cycles: [],
  },
];
export const findGridBot = (id: string) => GRID_BOTS.find((bot) => bot.id === id);
export const totalPnl = (bot: GridBot) =>
  new Decimal(bot.gridProfit).add(bot.unrealizedPnl).toFixed(2);
export const roi = (bot: GridBot) =>
  new Decimal(totalPnl(bot)).div(bot.investment).mul(100).toFixed(2);
