import Decimal from "decimal.js-light";

export type BacktestTimeframe = "1d" | "1h" | "15m";
export type FillModel = "CONSERVATIVE" | "OHLC_PATH";
export type EndTreatment = "MARK_TO_MARKET" | "FORCE_CLOSE" | "KEEP_OPEN";
export type GridType = "ARITHMETIC" | "GEOMETRIC";
export type MarketBar = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adjustedClose?: number;
  volume?: number;
};
export type CorporateAction = {
  date: string;
  type: "DIVIDEND" | "SPLIT";
  value: number;
  description?: string;
};
export type BacktestConfig = {
  symbol: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  initialCash?: number;
  initialInventory?: number;
  lowerPrice: number;
  upperPrice: number;
  gridCount: number;
  gridType: GridType;
  tickSize: number;
  boardLot: number;
  commissionRate: number;
  exchangeFeeRate: number;
  vatRate: number;
  slippageRate: number;
  fillModel: FillModel;
  endTreatment: EndTreatment;
  dividendInclusion: boolean;
  dividendReinvestment: boolean;
  cashConstraint: boolean;
  maxInventory?: number;
};
export type BacktestOrder = {
  id: string;
  gridIndex: number;
  side: "BUY" | "SELL";
  limitPrice: number;
  quantity: number;
  status: "OPEN" | "FILLED" | "REJECTED" | "FORCE_CLOSED";
  createdAt: string;
  filledAt?: string;
};
export type BacktestFill = {
  id: string;
  orderId: string;
  timestamp: string;
  side: "BUY" | "SELL";
  quantity: number;
  limitPrice: number;
  fillPrice: number;
  gross: number;
  commission: number;
  exchangeFee: number;
  vat: number;
  slippage: number;
};
export type GridCycle = {
  id: string;
  buyFillId: string;
  sellFillId: string;
  quantity: number;
  grossProfit: number;
  netProfit: number;
  holdingBars: number;
};
export type EquityPoint = {
  timestamp: string;
  equity: number;
  cash: number;
  inventoryValue: number;
  drawdown: number;
};
export type BacktestWarning = {
  code: string;
  severity: "WARNING" | "BLOCKED";
  message: string;
  count?: number;
};
export type BacktestMetrics = {
  startEquity: number;
  finalPortfolioValue: number;
  netPnl: number;
  realizedPnl: number;
  unrealizedPnl: number;
  gridProfit: number;
  totalFees: number;
  totalSlippage: number;
  maxDrawdown: number;
  cagr: number | null;
  buyAndHoldReturn: number | null;
  alpha: number | null;
  orders: number;
  fills: number;
  buyFills: number;
  sellFills: number;
  completedCycles: number;
  openLots: number;
  endingInventory: number;
  ambiguousBars: number;
  annual: Array<{
    year: string;
    startEquity: number;
    endEquity: number;
    netPnl: number;
    return: number;
    maxDrawdown: number;
    completedCycles: number;
    fills: number;
    fees: number;
    endingInventory: number;
    buyAndHoldReturn: number | null;
    alpha: number | null;
  }>;
  monthly: Array<{ year: string; month: string; return: number; netPnl: number; cycles: number }>;
};
export type BacktestRun = {
  id: string;
  createdAt: string;
  engineVersion: string;
  config: BacktestConfig;
  gridLevels: number[];
  metrics: BacktestMetrics;
  equityCurve: EquityPoint[];
  orders: BacktestOrder[];
  fills: BacktestFill[];
  cycles: GridCycle[];
  warnings: BacktestWarning[];
};

const d = (value: number | string) => new Decimal(value);
const n = (value: Decimal) => Number(value.toFixed(10));
const roundTick = (value: Decimal, tick: Decimal) =>
  value.div(tick).toDecimalPlaces(0, Decimal.ROUND_HALF_UP).mul(tick);
const floorLot = (value: Decimal, lot: Decimal) =>
  value.div(lot).toDecimalPlaces(0, Decimal.ROUND_FLOOR).mul(lot);
const dateOnly = (value: string) => value.slice(0, 10);

export function validateMarketBars(
  bars: MarketBar[],
  startDate?: string,
  endDate?: string,
): BacktestWarning[] {
  const warnings: BacktestWarning[] = [];
  if (!bars.length)
    return [{ code: "NO_DATA", severity: "BLOCKED", message: "Historical data is required." }];
  let previous = "";
  for (const bar of bars) {
    if (!bar.timestamp || !Number.isFinite(Date.parse(bar.timestamp)))
      warnings.push({
        code: "INVALID_DATE",
        severity: "BLOCKED",
        message: "Every bar needs a valid timestamp.",
      });
    if (!(
      bar.open > 0 &&
      bar.high >= Math.max(bar.open, bar.close) &&
      bar.low <= Math.min(bar.open, bar.close) &&
      bar.low > 0
    ))
      warnings.push({
        code: "INVALID_OHLC",
        severity: "BLOCKED",
        message: `Invalid OHLC at ${bar.timestamp}.`,
      });
    if (previous && bar.timestamp <= previous)
      warnings.push({
        code: "UNSORTED_OR_DUPLICATE",
        severity: "BLOCKED",
        message: "Bars must be strictly chronological with no duplicates.",
      });
    previous = bar.timestamp;
  }
  if (startDate && dateOnly(bars[0].timestamp) > startDate)
    warnings.push({
      code: "INSUFFICIENT_COVERAGE",
      severity: "BLOCKED",
      message: "Historical data starts after the selected start date.",
    });
  if (endDate && dateOnly(bars[bars.length - 1].timestamp) < endDate)
    warnings.push({
      code: "INSUFFICIENT_COVERAGE",
      severity: "BLOCKED",
      message: "Historical data ends before the selected end date.",
    });
  return [...new Map(warnings.map((warning) => [warning.code, warning])).values()];
}

export function parseMarketCsv(csv: string): { bars: MarketBar[]; warnings: BacktestWarning[] } {
  const lines = csv
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2)
    return {
      bars: [],
      warnings: [
        {
          code: "CSV_EMPTY",
          severity: "BLOCKED",
          message: "CSV must contain a header and at least one bar.",
        },
      ],
    };
  const headers = lines[0].split(",").map((header) => header.trim().toLowerCase());
  const index = (names: string[]) =>
    names.map((name) => headers.indexOf(name)).find((value) => value >= 0) ?? -1;
  const timestamp = index(["timestamp", "date", "time"]),
    open = index(["open"]),
    high = index(["high"]),
    low = index(["low"]),
    close = index(["close"]),
    adjusted = index(["adjustedclose", "adjusted_close"]),
    volume = index(["volume"]);
  if ([timestamp, open, high, low, close].some((value) => value < 0))
    return {
      bars: [],
      warnings: [
        {
          code: "CSV_SCHEMA",
          severity: "BLOCKED",
          message: "CSV needs timestamp/date, open, high, low and close columns.",
        },
      ],
    };
  const bars = lines.slice(1).map((line) => {
    const values = line.split(",").map((value) => value.trim());
    return {
      timestamp: values[timestamp],
      open: Number(values[open]),
      high: Number(values[high]),
      low: Number(values[low]),
      close: Number(values[close]),
      ...(adjusted >= 0 ? { adjustedClose: Number(values[adjusted]) } : {}),
      ...(volume >= 0 ? { volume: Number(values[volume]) } : {}),
    };
  });
  return { bars, warnings: validateMarketBars(bars) };
}

function levelsOf(config: BacktestConfig): number[] {
  const lower = d(config.lowerPrice),
    upper = d(config.upperPrice),
    tick = d(config.tickSize);
  if (
    !lower.gt(0) ||
    !upper.gt(lower) ||
    !Number.isInteger(config.gridCount) ||
    config.gridCount < 2 ||
    config.gridCount > 500
  )
    throw new Error("Invalid grid range or grid count");
  const ratio = upper.div(lower).pow(d(1).div(config.gridCount));
  return Array.from({ length: config.gridCount + 1 }, (_, index) =>
    n(
      roundTick(
        config.gridType === "GEOMETRIC"
          ? lower.mul(ratio.pow(index))
          : lower.add(upper.sub(lower).mul(index).div(config.gridCount)),
        tick,
      ),
    ),
  );
}

function costFor(gross: Decimal, config: BacktestConfig) {
  const commission = gross.mul(d(config.commissionRate).div(100));
  const exchangeFee = gross.mul(d(config.exchangeFeeRate).div(100));
  const vat = commission.add(exchangeFee).mul(d(config.vatRate).div(100));
  return { commission, exchangeFee, vat, total: commission.add(exchangeFee).add(vat) };
}

export function runAotBacktest(
  config: BacktestConfig,
  inputBars: MarketBar[],
  actions: CorporateAction[] = [],
): BacktestRun {
  const validation = validateMarketBars(inputBars, config.startDate, config.endDate);
  if (validation.some((warning) => warning.severity === "BLOCKED"))
    throw new Error(validation.map((warning) => warning.message).join(" "));
  const bars = inputBars.filter(
    (bar) =>
      dateOnly(bar.timestamp) >= config.startDate && dateOnly(bar.timestamp) <= config.endDate,
  );
  if (!bars.length) throw new Error("No historical bars in selected range.");
  const levels = levelsOf(config),
    lot = d(config.boardLot),
    tick = d(config.tickSize);
  let cash = d(config.initialCash ?? config.initialCapital),
    inventory = d(config.initialInventory ?? 0),
    averageCost = inventory.gt(0) ? d(bars[0].close) : d(0),
    realized = d(0),
    gridProfit = d(0),
    fees = d(0),
    slippageTotal = d(0),
    peak = d(config.initialCapital),
    ambiguousBars = 0;
  const orders: BacktestOrder[] = [],
    fills: BacktestFill[] = [],
    cycles: GridCycle[] = [],
    equityCurve: EquityPoint[] = [],
    openBuys = new Map<number, Array<{ fill: BacktestFill; costBasis: Decimal; bar: number }>>();
  const active = new Map<number, BacktestOrder>();
  const firstClose = d(bars[0].close);
  const reference = levels.reduce(
    (best, value, index) =>
      d(value).sub(firstClose).abs().lt(d(levels[best]).sub(firstClose).abs()) ? index : best,
    0,
  );
  const quantityFor = (price: Decimal) =>
    floorLot(d(config.initialCapital).div(config.gridCount).div(price), lot);
  const addOrder = (index: number, side: "BUY" | "SELL", timestamp: string) => {
    if (index < 0 || index >= levels.length || active.has(index)) return;
    const quantity = quantityFor(d(levels[index]));
    if (!quantity.gte(lot)) return;
    const order: BacktestOrder = {
      id: `ORD-${orders.length + 1}`,
      gridIndex: index,
      side,
      limitPrice: levels[index],
      quantity: n(quantity),
      status: "OPEN",
      createdAt: timestamp,
    };
    orders.push(order);
    active.set(index, order);
  };
  for (let index = 0; index < levels.length; index += 1)
    if (index !== reference) addOrder(index, index < reference ? "BUY" : "SELL", bars[0].timestamp);
  const fillAt = (order: BacktestOrder, bar: MarketBar, barIndex: number, price: Decimal) => {
    const quantity = d(order.quantity);
    if (
      order.side === "BUY" &&
      config.maxInventory !== undefined &&
      inventory.add(quantity).gt(config.maxInventory)
    )
      return false;
    const signedPrice =
      order.side === "BUY"
        ? price.mul(d(1).add(d(config.slippageRate).div(100)))
        : price.mul(d(1).sub(d(config.slippageRate).div(100)));
    const gross = signedPrice.mul(quantity),
      costs = costFor(gross, config),
      slip = signedPrice.sub(price).abs().mul(quantity);
    if (order.side === "BUY") {
      if (config.cashConstraint && cash.lt(gross.add(costs.total))) return false;
      cash = cash.sub(gross).sub(costs.total);
      averageCost = inventory.add(quantity).eq(0)
        ? d(0)
        : inventory.mul(averageCost).add(gross).div(inventory.add(quantity));
      inventory = inventory.add(quantity);
    } else {
      if (inventory.lt(quantity)) return false;
      cash = cash.add(gross).sub(costs.total);
      inventory = inventory.sub(quantity);
      const basis = averageCost.mul(quantity);
      realized = realized.add(gross.sub(costs.total).sub(basis));
    }
    fees = fees.add(costs.total);
    slippageTotal = slippageTotal.add(slip);
    order.status = "FILLED";
    order.filledAt = bar.timestamp;
    active.delete(order.gridIndex);
    const fill: BacktestFill = {
      id: `FILL-${fills.length + 1}`,
      orderId: order.id,
      timestamp: bar.timestamp,
      side: order.side,
      quantity: n(quantity),
      limitPrice: order.limitPrice,
      fillPrice: n(signedPrice),
      gross: n(gross),
      commission: n(costs.commission),
      exchangeFee: n(costs.exchangeFee),
      vat: n(costs.vat),
      slippage: n(slip),
    };
    fills.push(fill);
    if (order.side === "BUY")
      openBuys.set(order.gridIndex, [
        ...(openBuys.get(order.gridIndex) ?? []),
        { fill, costBasis: gross.add(costs.total), bar: barIndex },
      ]);
    else {
      const prior = openBuys.get(order.gridIndex - 1)?.shift();
      if (prior) {
        const net = gross.sub(costs.total).sub(prior.costBasis);
        gridProfit = gridProfit.add(net);
        cycles.push({
          id: `CYCLE-${cycles.length + 1}`,
          buyFillId: prior.fill.id,
          sellFillId: fill.id,
          quantity: n(quantity),
          grossProfit: n(gross.sub(prior.fill.gross)),
          netProfit: n(net),
          holdingBars: barIndex - prior.bar,
        });
      }
    }
    const paired = order.side === "BUY" ? order.gridIndex + 1 : order.gridIndex - 1;
    addOrder(paired, order.side === "BUY" ? "SELL" : "BUY", bar.timestamp);
    return true;
  };
  bars.forEach((bar, barIndex) => {
    for (const action of actions.filter((item) => item.date === dateOnly(bar.timestamp))) {
      if (action.type === "DIVIDEND" && config.dividendInclusion) {
        const dividend = inventory.mul(d(action.value));
        cash = config.dividendReinvestment ? cash : cash.add(dividend);
        if (config.dividendReinvestment)
          inventory = inventory.add(floorLot(dividend.div(d(bar.close)), lot));
      }
      if (action.type === "SPLIT" && action.value > 0) {
        inventory = inventory.mul(action.value);
        averageCost = averageCost.div(action.value);
      }
    }
    const candidates = [...active.values()].filter((order) =>
      order.side === "BUY" ? d(bar.low).lte(order.limitPrice) : d(bar.high).gte(order.limitPrice),
    );
    if (
      config.fillModel === "CONSERVATIVE" &&
      candidates.some((order) => order.side === "BUY") &&
      candidates.some((order) => order.side === "SELL")
    ) {
      ambiguousBars += 1;
    } else for (const order of candidates) fillAt(order, bar, barIndex, d(order.limitPrice));
    const equity = cash.add(inventory.mul(d(bar.close))),
      drawdown = peak.sub(equity).div(peak).mul(100);
    if (equity.gt(peak)) peak = equity;
    equityCurve.push({
      timestamp: bar.timestamp,
      equity: n(equity),
      cash: n(cash),
      inventoryValue: n(inventory.mul(d(bar.close))),
      drawdown: n(drawdown),
    });
  });
  const finalBar = bars[bars.length - 1];
  if (config.endTreatment === "FORCE_CLOSE" && inventory.gt(0)) {
    const forced = [...active.values()].filter((order) => order.side === "SELL");
    if (forced.length)
      fillAt(
        { ...forced[0], id: `FORCE-${orders.length + 1}`, status: "OPEN" },
        finalBar,
        bars.length - 1,
        d(finalBar.close),
      );
  }
  const finalEquity = cash.add(inventory.mul(d(finalBar.close))),
    startEquity = d(config.initialCapital),
    years = Math.max(
      1 / 365,
      (Date.parse(finalBar.timestamp) - Date.parse(bars[0].timestamp)) / 86_400_000 / 365,
    ),
    buyHold = d(finalBar.close).div(firstClose).sub(1).mul(100),
    totalReturn = finalEquity.div(startEquity).sub(1).mul(100),
    maxDrawdown = equityCurve.reduce((max, point) => Math.max(max, point.drawdown), 0);
  const warnings: BacktestWarning[] = [
    ...validation,
    ...(ambiguousBars
      ? [
          {
            code: "AMBIGUOUS_BARS",
            severity: "WARNING" as const,
            message:
              "Conservative fill model skipped bars where both buy and sell sides were touched.",
            count: ambiguousBars,
          },
        ]
      : []),
    ...(config.endTreatment === "KEEP_OPEN" && inventory.gt(0)
      ? [
          {
            code: "ENDING_INVENTORY",
            severity: "WARNING" as const,
            message: "Backtest ended with open inventory; result is mark-to-market.",
          },
        ]
      : []),
  ];
  const annual = [...new Set(bars.map((bar) => bar.timestamp.slice(0, 4)))].map((year) => {
    const points = equityCurve.filter((point) => point.timestamp.startsWith(year));
    const start = d(points[0]?.equity ?? 0),
      end = d(points[points.length - 1]?.equity ?? 0);
    return {
      year,
      startEquity: n(start),
      endEquity: n(end),
      netPnl: n(end.sub(start)),
      return: start.gt(0) ? n(end.div(start).sub(1).mul(100)) : 0,
      maxDrawdown: points.reduce((max, point) => Math.max(max, point.drawdown), 0),
      completedCycles: cycles.filter(
        (cycle) =>
          cycle.sellFillId &&
          fills.find((fill) => fill.id === cycle.sellFillId)?.timestamp.startsWith(year),
      ).length,
      fills: fills.filter((fill) => fill.timestamp.startsWith(year)).length,
      fees: n(fees),
      endingInventory: n(inventory),
      buyAndHoldReturn: null,
      alpha: null,
    };
  });
  const monthly = [...new Set(equityCurve.map((point) => point.timestamp.slice(0, 7)))].map(
    (key) => {
      const points = equityCurve.filter((point) => point.timestamp.startsWith(key));
      const start = points[0]?.equity ?? 0;
      const end = points[points.length - 1]?.equity ?? start;
      const [year, month] = key.split("-");
      return {
        year,
        month,
        return: start > 0 ? (end / start - 1) * 100 : 0,
        netPnl: end - start,
        cycles: cycles.filter((cycle) => {
          const fill = fills.find((item) => item.id === cycle.sellFillId);
          return Boolean(fill?.timestamp.startsWith(key));
        }).length,
      };
    },
  );
  const metrics: BacktestMetrics = {
    startEquity: n(startEquity),
    finalPortfolioValue: n(finalEquity),
    netPnl: n(finalEquity.sub(startEquity)),
    realizedPnl: n(realized),
    unrealizedPnl: n(inventory.mul(d(finalBar.close)).sub(inventory.mul(averageCost))),
    gridProfit: n(gridProfit),
    totalFees: n(fees),
    totalSlippage: n(slippageTotal),
    maxDrawdown,
    cagr: n(finalEquity.div(startEquity).pow(d(1).div(years)).sub(1).mul(100)),
    buyAndHoldReturn: n(buyHold),
    alpha: n(totalReturn.sub(buyHold)),
    orders: orders.length,
    fills: fills.length,
    buyFills: fills.filter((fill) => fill.side === "BUY").length,
    sellFills: fills.filter((fill) => fill.side === "SELL").length,
    completedCycles: cycles.length,
    openLots: [...openBuys.values()].reduce((sum, lots) => sum + lots.length, 0),
    endingInventory: n(inventory),
    ambiguousBars,
    annual,
    monthly,
  };
  return {
    id: `BT-${Date.now()}`,
    createdAt: new Date().toISOString(),
    engineVersion: "aot-backtest-1.0.0",
    config,
    gridLevels: levels,
    metrics,
    equityCurve,
    orders,
    fills,
    cycles,
    warnings,
  };
}
