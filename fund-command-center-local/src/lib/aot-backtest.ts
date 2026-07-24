import Decimal from "decimal.js-light";

export type BacktestTimeframe = "1d" | "1h" | "15m";
export type FillModel = "CONSERVATIVE" | "OHLC_PATH";
export type ExecutionMode = "CONSERVATIVE_OHLC" | "OPTIMISTIC_OHLC" | "WORST_CASE" | "INTRABAR_EXACT";
export type EndTreatment = "MARK_TO_MARKET" | "FORCE_CLOSE" | "KEEP_OPEN";
export type GridType = "ARITHMETIC" | "GEOMETRIC";
export type RegimeState = "RANGE" | "TREND_UP" | "TREND_DOWN";
/**
 * Trailing re-anchor (E28). E27 established that suspending orders cannot
 * preserve upside on a fixed-level grid, because a held limit order still fills
 * at its original price. So the levels themselves move: when price closes above
 * the grid, the whole ladder is lifted — same width, same geometry — so the
 * grid keeps trading instead of standing sold-out while price runs away.
 * Upward only. Trailing down would chase a falling market and is a separate
 * mechanism that has NOT been tested.
 */
export type TrailingConfig = { mode: "TRAIL_UP" };
/**
 * Exposure cap at re-anchor (E29). E28's trailing keeps the book in the market
 * during a trend, which captures more upside but also lets long inventory
 * accumulate across re-anchors — so robust (return - 2*maxDD) got worse even as
 * alpha improved. GRID_CAPACITY caps long inventory at the initial grid's own
 * maximum long capacity (Σ quantity over the initial BUY levels): a BUY does not
 * fill while inventory sits at the cap, bounding the drawdown a reversal can
 * inflict, while the SELL side (trailing's alpha source) is untouched. Not a
 * tuned number — it is the grid's own geometry. `null` reproduces E28 exactly.
 */
export type ExposureCapConfig = { mode: "GRID_CAPACITY" };
/**
 * Percentile-rank trend detector (E14 established percentile rank as the
 * detector that works on this project's data). It was built to answer one E26
 * finding: a grid sells its inventory into a rally and then watches price run
 * away. In TREND_UP the sell side is suspended, in TREND_DOWN the buy side.
 * E27 ran it and it FAILED — suspension only delays a limit fill, so use this
 * for diagnosis, not as a fix. See VALIDATION_LOG § E27.
 */
export type RegimeFilterConfig = {
  lookback: number;
  rankWindow: number;
  upperRank: number;
  lowerRank: number;
};
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
  executionMode?: ExecutionMode;
  maxParticipationRatePct?: number;
  regimeFilter?: RegimeFilterConfig | null;
  trailing?: TrailingConfig | null;
  exposureCap?: ExposureCapConfig | null;
};
export type BacktestOrder = {
  id: string;
  gridIndex: number;
  side: "BUY" | "SELL";
  limitPrice: number;
  quantity: number;
  status: "OPEN" | "FILLED" | "REJECTED" | "FORCE_CLOSED" | "CANCELLED";
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
export type BacktestEvent = {
  id: string;
  timestamp: string;
  sequence: number;
  type:
    | "MARKET_EVENT"
    | "STRATEGY_DECISION"
    | "ORDER_SUBMITTED"
    | "ORDER_QUEUED"
    | "ORDER_CANCELLED"
    | "FILL"
    | "FEE"
    | "LOT_UPDATE"
    | "PORTFOLIO_VALUATION";
  referenceId?: string;
  payload: Record<string, number | string | boolean | null>;
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
export type BacktestRunMetadata = {
  runId: string;
  strategyId: string;
  strategyVersion: string;
  codeCommitHash?: string;
  datasetId: string;
  datasetVersion: string;
  dataSource: string;
  dataRetrievedAt?: string;
  configurationHash: string;
  randomSeed?: number;
  startedAt: string;
  completedAt: string;
  executionDurationMs: number;
  engineVersion: string;
  environment?: string;
  timezone: string;
  currency: string;
  tradingCalendar: string;
  executionMode: ExecutionMode;
  intrabarBarsUsed: number;
  intrabarFallback: boolean;
};
export type BacktestMetrics = {
  startEquity: number;
  initialCash: number;
  initialInventoryMarketValue: number;
  endingCash: number;
  endingInventoryMarketValue: number;
  finalPortfolioValue: number;
  netPnl: number;
  totalReturn: number;
  durationDays: number;
  durationYears: number;
  realizedPnl: number;
  unrealizedPnl: number;
  dividendIncome: number;
  reconciliationDifference: number;
  isReconciled: boolean;
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
  winRate: number | null;
  profitFactor: number | null;
  expectancyPerCycle: number | null;
  averageWin: number | null;
  averageLoss: number | null;
  maxConsecutiveLosses: number;
  maxCapitalDeployed: number;
  averageCapitalDeployed: number;
  timeUnderwaterPct: number;
  longestRecoveryBars: number;
  forcedLiquidation: boolean;
  openLots: number;
  endingInventory: number;
  ambiguousBars: number;
  regimeSuspendedBars: number;
  regimeBarCounts: Record<RegimeState, number>;
  reAnchors: number;
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
  metadata: BacktestRunMetadata;
  events: BacktestEvent[];
};

const d = (value: number | string) => new Decimal(value);
const n = (value: Decimal) => Number(value.toFixed(10));
const roundTick = (value: Decimal, tick: Decimal) =>
  value.div(tick).toDecimalPlaces(0, Decimal.ROUND_HALF_UP).mul(tick);
const floorLot = (value: Decimal, lot: Decimal) =>
  value.div(lot).toDecimalPlaces(0, Decimal.ROUND_FLOOR).mul(lot);
const dateOnly = (value: string) => value.slice(0, 10);
const hashText = (value: string) => {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
};
let runSequence = 0;

/**
 * Regime state per bar, with no lookahead: the state applied to bar `i` is
 * ranked from momentum that was complete at the close of bar `i-1`.
 * Pass every bar available including warm-up history; the caller aligns the
 * result to the bars actually simulated.
 */
export function computeRegimeStates(
  bars: MarketBar[],
  filter?: RegimeFilterConfig | null,
): RegimeState[] {
  const states: RegimeState[] = new Array(bars.length).fill("RANGE");
  if (!filter) return states;
  const { lookback, rankWindow, upperRank, lowerRank } = filter;
  if (lookback < 1 || rankWindow < 2) return states;
  const momentum = bars.map((bar, index) =>
    index < lookback || bars[index - lookback].close <= 0
      ? null
      : bar.close / bars[index - lookback].close - 1,
  );
  const MIN_HISTORY = 30;
  for (let index = 1; index < bars.length; index += 1) {
    const decided = index - 1; // information complete before bar `index` trades
    const current = momentum[decided];
    if (current == null) continue;
    const history: number[] = [];
    for (let k = Math.max(0, decided - rankWindow + 1); k <= decided; k += 1) {
      const value = momentum[k];
      if (value != null) history.push(value);
    }
    if (history.length < Math.min(rankWindow, MIN_HISTORY)) continue;
    const rank = (history.filter((value) => value <= current).length / history.length) * 100;
    states[index] =
      rank >= upperRank ? "TREND_UP" : rank <= lowerRank ? "TREND_DOWN" : "RANGE";
  }
  return states;
}

export function analyzeMarketData(bars: MarketBar[]) {
  const timestamps = new Set<string>();
  let duplicates = 0;
  let missingOhlcv = 0;
  let invalidPrices = 0;
  let negativeVolume = 0;
  let abnormalGaps = 0;
  let previousTime: number | null = null;
  for (const bar of bars) {
    if (timestamps.has(bar.timestamp)) duplicates += 1;
    timestamps.add(bar.timestamp);
    if (![bar.open, bar.high, bar.low, bar.close].every(Number.isFinite)) missingOhlcv += 1;
    if (bar.open <= 0 || bar.high <= 0 || bar.low <= 0 || bar.close <= 0 || bar.high < bar.low) invalidPrices += 1;
    if (bar.volume != null && bar.volume < 0) negativeVolume += 1;
    const currentTime = Date.parse(bar.timestamp);
    if (previousTime != null && currentTime - previousTime > 4 * 86_400_000) abnormalGaps += 1;
    if (Number.isFinite(currentTime)) previousTime = currentTime;
  }
  return { bars: bars.length, duplicates, missingOhlcv, invalidPrices, negativeVolume, abnormalGaps };
}

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
  runMetadata?: Partial<BacktestRunMetadata>,
  intrabarBars: MarketBar[] = [],
): BacktestRun {
  const startedAt = new Date().toISOString();
  const validation = validateMarketBars(inputBars, config.startDate, config.endDate);
  if (validation.some((warning) => warning.severity === "BLOCKED"))
    throw new Error(validation.map((warning) => warning.message).join(" "));
  const bars = inputBars.filter(
    (bar) =>
      dateOnly(bar.timestamp) >= config.startDate && dateOnly(bar.timestamp) <= config.endDate,
  );
  if (!bars.length) throw new Error("No historical bars in selected range.");
  // Rank regime over every supplied bar so bars before startDate serve as
  // warm-up. Warm-up is past data, so this adds history without adding
  // lookahead; without it a one-year window would spend months un-ranked.
  const regimeOffset = inputBars.findIndex((bar) => bar.timestamp === bars[0].timestamp);
  const regimeStates = computeRegimeStates(inputBars, config.regimeFilter).slice(
    Math.max(0, regimeOffset),
  );
  const executionMode = config.executionMode ?? "CONSERVATIVE_OHLC";
  const intrabar = intrabarBars
    .filter((bar) => Date.parse(bar.timestamp) >= Date.parse(bars[0].timestamp) && Date.parse(bar.timestamp) <= Date.parse(bars[bars.length - 1].timestamp))
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  let levels = levelsOf(config);
  const initialLevels = [...levels];
  const
    lot = d(config.boardLot),
    tick = d(config.tickSize);
  let cash = d(config.initialCash ?? config.initialCapital),
    inventory = d(config.initialInventory ?? 0),
    inventoryCost = inventory.mul(d(bars[0].close)),
    averageCost = inventory.gt(0) ? d(bars[0].close) : d(0),
    realized = d(0),
    dividendIncome = d(0),
    gridProfit = d(0),
    fees = d(0),
    slippageTotal = d(0),
    peak = d(config.initialCash ?? config.initialCapital).add(inventory.mul(d(bars[0].close))),
    deployedSum = d(0),
    maxDeployed = d(0),
    ambiguousBars = 0,
    regimeSuspendedBars = 0,
    reAnchors = 0;
  const regimeBarCounts: Record<RegimeState, number> = { RANGE: 0, TREND_UP: 0, TREND_DOWN: 0 };
  const orders: BacktestOrder[] = [],
    fills: BacktestFill[] = [],
    cycles: GridCycle[] = [],
    events: BacktestEvent[] = [],
    equityCurve: EquityPoint[] = [],
    openBuys = new Map<number, Array<{ fill: BacktestFill; costBasis: Decimal; bar: number }>>();
  const active = new Map<number, BacktestOrder>();
  const emit = (
    timestamp: string,
    type: BacktestEvent["type"],
    payload: BacktestEvent["payload"],
    referenceId?: string,
  ) => {
    events.push({
      id: `EVT-${events.length + 1}`,
      timestamp,
      sequence: events.length + 1,
      type,
      referenceId,
      payload,
    });
  };
  const firstClose = d(bars[0].close);
  const referenceFor = (price: Decimal) =>
    levels.reduce(
      (best, value, index) =>
        d(value).sub(price).abs().lt(d(levels[best]).sub(price).abs()) ? index : best,
      0,
    );
  let reference = referenceFor(firstClose);
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
    emit(timestamp, "ORDER_SUBMITTED", { side, limitPrice: order.limitPrice, quantity: order.quantity }, order.id);
    emit(timestamp, "ORDER_QUEUED", { gridIndex: index, queuePosition: 0 }, order.id);
  };
  const armGrid = (timestamp: string) => {
    for (let index = 0; index < levels.length; index += 1)
      if (index !== reference) addOrder(index, index < reference ? "BUY" : "SELL", timestamp);
  };
  armGrid(bars[0].timestamp);
  // E29 exposure cap: the initial grid's maximum long capacity = Σ quantity over
  // the BUY levels as first armed. Fixed once here and held across re-anchors — the
  // point is to bound long inventory to the ORIGINAL grid, not to grow the cap as
  // the ladder lifts. Derived from geometry, so there is no tunable number.
  const longCap =
    config.exposureCap?.mode === "GRID_CAPACITY"
      ? initialLevels.reduce(
          (sum, level, index) => (index < reference ? sum.add(quantityFor(d(level))) : sum),
          d(0),
        )
      : null;
  /**
   * Lift the whole ladder so `price` sits back inside it, keeping the existing
   * width ratio and spacing. Open orders are genuinely cancelled — not held —
   * because E27 showed a held order simply fills later at its stale price.
   * Cash and inventory are untouched: this re-prices future intent, it does not
   * liquidate anything.
   */
  const reAnchor = (price: Decimal, timestamp: string) => {
    const top = d(levels[levels.length - 1]);
    if (!top.gt(0) || !price.gt(top)) return;
    const shift = price.div(top);
    for (const [index, order] of active) {
      order.status = "CANCELLED";
      emit(timestamp, "ORDER_CANCELLED", { gridIndex: index, reason: "TRAILING_REANCHOR" }, order.id);
    }
    active.clear();
    levels = levels.map((level) => n(roundTick(d(level).mul(shift), tick)));
    reference = referenceFor(price);
    reAnchors += 1;
    emit(timestamp, "STRATEGY_DECISION", {
      reAnchor: reAnchors,
      lower: levels[0],
      upper: levels[levels.length - 1],
    });
    armGrid(timestamp);
  };
  const fillAt = (order: BacktestOrder, bar: MarketBar, barIndex: number, price: Decimal) => {
    const quantity = d(order.quantity);
    if (
      order.side === "BUY" &&
      config.maxInventory !== undefined &&
      inventory.add(quantity).gt(config.maxInventory)
    )
      return false;
    // E29: do not fill a BUY while inventory sits at the grid-capacity cap. The
    // order stays open at its geometry price and fills once a SELL frees room, so
    // this bounds max long (and thus reversal drawdown) without cancelling or
    // force-selling anything. Inactive when exposureCap is null → E28 unchanged.
    if (order.side === "BUY" && longCap !== null && inventory.add(quantity).gt(longCap)) return false;
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
      inventoryCost = inventoryCost.add(gross).add(costs.total);
      inventory = inventory.add(quantity);
      averageCost = inventory.gt(0) ? inventoryCost.div(inventory) : d(0);
    } else {
      if (inventory.lt(quantity)) return false;
      cash = cash.add(gross).sub(costs.total);
      inventory = inventory.sub(quantity);
      const basis = inventory.gt(0)
        ? inventoryCost.mul(quantity).div(inventory.add(quantity))
        : inventoryCost;
      inventoryCost = inventoryCost.sub(basis);
      realized = realized.add(gross.sub(costs.total).sub(basis));
      averageCost = inventory.gt(0) ? inventoryCost.div(inventory) : d(0);
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
    emit(bar.timestamp, "FILL", { side: order.side, quantity: fill.quantity, fillPrice: fill.fillPrice, gross: fill.gross }, fill.id);
    emit(bar.timestamp, "FEE", { commission: fill.commission, exchangeFee: fill.exchangeFee, vat: fill.vat }, fill.id);
    emit(bar.timestamp, "LOT_UPDATE", { inventory: n(inventory), averageCost: n(averageCost) }, fill.id);
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
    emit(bar.timestamp, "MARKET_EVENT", { open: bar.open, high: bar.high, low: bar.low, close: bar.close, volume: bar.volume ?? null });
    const regime = regimeStates[barIndex] ?? "RANGE";
    // Suspend the side that fights the trend. Orders are not cancelled, only
    // held, so the grid resumes intact once the regime normalises.
    const suspendedSide =
      regime === "TREND_UP" ? "SELL" : regime === "TREND_DOWN" ? "BUY" : null;
    if (suspendedSide) regimeSuspendedBars += 1;
    regimeBarCounts[regime] += 1;
    emit(bar.timestamp, "STRATEGY_DECISION", { activeOrders: active.size, inventory: n(inventory), cash: n(cash), regime, suspendedSide });
    for (const action of actions.filter((item) => item.date === dateOnly(bar.timestamp))) {
      if (action.type === "DIVIDEND" && config.dividendInclusion) {
        const dividend = inventory.mul(d(action.value));
        dividendIncome = dividendIncome.add(dividend);
        cash = config.dividendReinvestment ? cash : cash.add(dividend);
        if (config.dividendReinvestment)
          inventory = inventory.add(floorLot(dividend.div(d(bar.close)), lot));
      }
      if (action.type === "SPLIT" && action.value > 0) {
        inventory = inventory.mul(action.value);
        averageCost = inventory.gt(0) ? inventoryCost.div(inventory) : d(0);
      }
    }
    const slices = executionMode === "INTRABAR_EXACT"
      ? intrabar.filter((slice) => dateOnly(slice.timestamp) === dateOnly(bar.timestamp))
      : [];
    const executionSlices = slices.length ? slices : [bar];
    for (const slice of executionSlices) {
      const candidates = [...active.values()].filter(
        (order) =>
          order.side !== suspendedSide &&
          (order.side === "BUY"
            ? d(slice.low).lte(order.limitPrice)
            : d(slice.high).gte(order.limitPrice)),
      );
      const ambiguous =
        candidates.some((order) => order.side === "BUY") &&
        candidates.some((order) => order.side === "SELL");
      if (ambiguous && executionMode === "CONSERVATIVE_OHLC") {
        ambiguousBars += 1;
      } else {
        // A real intrabar slice resolves the path, so it needs no assumption.
        // Otherwise each mode states its own, and the three must bracket the
        // truth: OPTIMISTIC >= CONSERVATIVE >= WORST_CASE. Ordering matters even
        // on a single-sided bar, because the cash and inventory constraints
        // decide which levels of that side actually get filled.
        const assumed = slices.length ? "CONSERVATIVE_OHLC" : executionMode;
        // On an ambiguous bar the worst path fills only the exposure-increasing
        // leg: inventory is added and the offsetting sell never happens.
        const eligible =
          ambiguous && assumed === "WORST_CASE"
            ? candidates.filter((order) => order.side === "BUY")
            : candidates;
        // Rank by how bad a fill is for the book. A buy is worse the higher it
        // pays; a sell is worse the lower it accepts. The old comparator sorted
        // both sides by gridIndex, which made WORST_CASE pick the worst buys but
        // the *best* sells — that is why it could outscore CONSERVATIVE.
        const adversity = (order: BacktestOrder) =>
          order.side === "BUY" ? order.limitPrice : -order.limitPrice;
        const ordered = [...eligible].sort((a, b) => {
          if (assumed === "WORST_CASE") return adversity(b) - adversity(a);
          if (assumed === "OPTIMISTIC_OHLC") {
            // Buy first, then sell, so an ambiguous bar completes a cycle.
            if (a.side !== b.side) return a.side === "BUY" ? -1 : 1;
            return adversity(a) - adversity(b);
          }
          return a.gridIndex - b.gridIndex;
        });
        for (const order of ordered) {
          const limit = d(order.limitPrice);
          const open = d(slice.open);
          const touched = order.side === "BUY" ? d(slice.low).lte(limit) : d(slice.high).gte(limit);
          if (!touched) continue;
          const gapPrice = order.side === "BUY" && open.lt(limit) ? open : order.side === "SELL" && open.gt(limit) ? open : limit;
          fillAt(order, slice, barIndex, gapPrice);
        }
      }
    }
    // Decided on the close, after this bar's fills, so the lift never front-runs
    // a move it has not yet seen.
    if (config.trailing?.mode === "TRAIL_UP") reAnchor(d(bar.close), bar.timestamp);
    const deployed = inventory.mul(d(bar.close));
    deployedSum = deployedSum.add(deployed);
    if (deployed.gt(maxDeployed)) maxDeployed = deployed;
    const equity = cash.add(deployed);
    if (equity.gt(peak)) peak = equity;
    const rawDrawdown = peak.gt(0) ? peak.sub(equity).div(peak).mul(100) : d(0);
    const drawdown = rawDrawdown.gt(0) ? rawDrawdown : d(0);
    equityCurve.push({
      timestamp: bar.timestamp,
      equity: n(equity),
      cash: n(cash),
      inventoryValue: n(inventory.mul(d(bar.close))),
      drawdown: n(drawdown),
    });
    emit(bar.timestamp, "PORTFOLIO_VALUATION", { equity: n(equity), cash: n(cash), inventoryValue: n(inventory.mul(d(bar.close))), drawdown: n(drawdown) });
  });
  const finalBar = bars[bars.length - 1];
  let forcedLiquidation = false;
  if (config.endTreatment === "FORCE_CLOSE" && inventory.gt(0)) {
    const forced = [...active.values()].filter((order) => order.side === "SELL");
    for (const order of forced) {
      if (inventory.lte(0)) break;
      forcedLiquidation =
        fillAt(
          { ...order, id: `FORCE-${orders.length + 1}`, status: "OPEN" },
          finalBar,
          bars.length - 1,
          d(finalBar.close),
        ) || forcedLiquidation;
    }
    const finalPoint = equityCurve[equityCurve.length - 1];
    if (finalPoint) {
      const closeEquity = cash.add(inventory.mul(d(finalBar.close)));
      equityCurve[equityCurve.length - 1] = {
        ...finalPoint,
        equity: n(closeEquity),
        cash: n(cash),
        inventoryValue: n(inventory.mul(d(finalBar.close))),
      };
    }
  }
  const finalEquity = cash.add(inventory.mul(d(finalBar.close))),
    initialCash = d(config.initialCash ?? config.initialCapital),
    initialInventoryMarketValue = d(config.initialInventory ?? 0).mul(firstClose),
    startEquity = initialCash.add(initialInventoryMarketValue),
    durationDays = Math.max(
      1,
      Math.round((Date.parse(finalBar.timestamp) - Date.parse(bars[0].timestamp)) / 86_400_000),
    ),
    years = Math.max(1 / 365, durationDays / 365),
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
    ...(forcedLiquidation
      ? [
          {
            code: "FORCED_LIQUIDATION",
            severity: "WARNING" as const,
            message: "Ending inventory was force-closed at the final bar close.",
          },
        ]
      : []),
    ...(Math.abs(
      finalEquity
        .sub(startEquity)
        .sub(realized)
        .sub(inventory.mul(d(finalBar.close)).sub(inventory.mul(averageCost)))
        .sub(dividendIncome)
        .toNumber(),
    ) > 0.01
      ? [
          {
            code: "RECONCILIATION_FAILED",
            severity: "WARNING" as const,
            message: "Reported P/L does not reconcile within the ฿0.01 tolerance.",
          },
        ]
      : []),
  ];
  const annual = [...new Set(bars.map((bar) => bar.timestamp.slice(0, 4)))].map((year) => {
    const points = equityCurve.filter((point) => point.timestamp.startsWith(year));
    const yearBars = bars.filter((bar) => bar.timestamp.startsWith(year));
    const yearFills = fills.filter((fill) => fill.timestamp.startsWith(year));
    const start = d(points[0]?.equity ?? 0),
      end = d(points[points.length - 1]?.equity ?? 0);
    const yearBuyAndHold =
      yearBars.length > 1
        ? (yearBars[yearBars.length - 1].close / yearBars[0].close - 1) * 100
        : null;
    const yearFees = yearFills.reduce(
      (sum, fill) => sum + fill.commission + fill.exchangeFee + fill.vat,
      0,
    );
    const yearReturn = start.gt(0) ? n(end.div(start).sub(1).mul(100)) : 0;
    return {
      year,
      startEquity: n(start),
      endEquity: n(end),
      netPnl: n(end.sub(start)),
      return: yearReturn,
      maxDrawdown: points.reduce((max, point) => Math.max(max, point.drawdown), 0),
      completedCycles: cycles.filter(
        (cycle) =>
          cycle.sellFillId &&
          fills.find((fill) => fill.id === cycle.sellFillId)?.timestamp.startsWith(year),
      ).length,
      fills: yearFills.length,
      fees: yearFees,
      endingInventory: n(inventory),
      buyAndHoldReturn: yearBuyAndHold,
      alpha: yearBuyAndHold == null ? null : yearReturn - yearBuyAndHold,
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
  const positiveCycles = cycles.filter((cycle) => cycle.netProfit > 0);
  const negativeCycles = cycles.filter((cycle) => cycle.netProfit < 0);
  const grossWins = positiveCycles.reduce((sum, cycle) => sum + cycle.netProfit, 0);
  const grossLosses = Math.abs(negativeCycles.reduce((sum, cycle) => sum + cycle.netProfit, 0));
  let consecutiveLosses = 0;
  let maxConsecutiveLosses = 0;
  for (const cycle of cycles) {
    consecutiveLosses = cycle.netProfit < 0 ? consecutiveLosses + 1 : 0;
    maxConsecutiveLosses = Math.max(maxConsecutiveLosses, consecutiveLosses);
  }
  let underwaterBars = 0;
  let recoveryBars = 0;
  let longestRecoveryBars = 0;
  for (const point of equityCurve) {
    if (point.drawdown > 0) {
      underwaterBars += 1;
      recoveryBars += 1;
    } else {
      longestRecoveryBars = Math.max(longestRecoveryBars, recoveryBars);
      recoveryBars = 0;
    }
  }
  longestRecoveryBars = Math.max(longestRecoveryBars, recoveryBars);
  const endingInventoryMarketValue = inventory.mul(d(finalBar.close));
  const unrealizedPnl = endingInventoryMarketValue.sub(inventory.mul(averageCost));
  const reportedNetPnl = finalEquity.sub(startEquity);
  const reconciliationDifference = reportedNetPnl
    .sub(realized)
    .sub(unrealizedPnl)
    .sub(dividendIncome);
  const metrics: BacktestMetrics = {
    startEquity: n(startEquity),
    initialCash: n(initialCash),
    initialInventoryMarketValue: n(initialInventoryMarketValue),
    endingCash: n(cash),
    endingInventoryMarketValue: n(endingInventoryMarketValue),
    finalPortfolioValue: n(finalEquity),
    netPnl: n(reportedNetPnl),
    totalReturn: n(totalReturn),
    durationDays,
    durationYears: n(d(durationDays).div(365)),
    realizedPnl: n(realized),
    unrealizedPnl: n(unrealizedPnl),
    dividendIncome: n(dividendIncome),
    reconciliationDifference: n(reconciliationDifference),
    isReconciled: reconciliationDifference.abs().lte(0.01),
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
    winRate: cycles.length ? (positiveCycles.length / cycles.length) * 100 : null,
    profitFactor: grossLosses > 0 ? grossWins / grossLosses : null,
    expectancyPerCycle: cycles.length ? (grossWins - grossLosses) / cycles.length : null,
    averageWin: positiveCycles.length ? grossWins / positiveCycles.length : null,
    averageLoss: negativeCycles.length ? -grossLosses / negativeCycles.length : null,
    maxConsecutiveLosses,
    maxCapitalDeployed: n(maxDeployed),
    averageCapitalDeployed: n(deployedSum.div(bars.length)),
    timeUnderwaterPct: equityCurve.length ? (underwaterBars / equityCurve.length) * 100 : 0,
    longestRecoveryBars,
    forcedLiquidation,
    openLots: [...openBuys.values()].reduce((sum, lots) => sum + lots.length, 0),
    endingInventory: n(inventory),
    ambiguousBars,
    regimeSuspendedBars,
    regimeBarCounts,
    reAnchors,
    annual,
    monthly,
  };
  const completedAt = new Date().toISOString();
  runSequence += 1;
  const runId = `BT-${Date.now()}-${runSequence.toString(36)}-${hashText(JSON.stringify(config))}`;
  return {
    id: runId,
    createdAt: new Date().toISOString(),
    engineVersion: "aot-backtest-1.0.0",
    config,
    gridLevels: initialLevels,
    metrics,
    equityCurve,
    orders,
    fills,
    cycles,
    warnings,
    metadata: {
      runId,
      strategyId: runMetadata?.strategyId ?? "aot-paper-grid",
      strategyVersion: runMetadata?.strategyVersion ?? "aot-grid-v1",
      codeCommitHash: runMetadata?.codeCommitHash,
      datasetId: runMetadata?.datasetId ?? `${config.symbol}-ohlcv`,
      datasetVersion: runMetadata?.datasetVersion ?? `${bars[0].timestamp.slice(0, 10)}:${bars[bars.length - 1].timestamp.slice(0, 10)}:${bars.length}`,
      dataSource: runMetadata?.dataSource ?? (config.symbol.includes("SYNTHETIC") ? "Synthetic scenario" : "Client-uploaded OHLCV CSV"),
      dataRetrievedAt: runMetadata?.dataRetrievedAt,
      configurationHash: hashText(JSON.stringify(config)),
      randomSeed: runMetadata?.randomSeed,
      startedAt,
      completedAt,
      executionDurationMs: Math.max(0, Date.parse(completedAt) - Date.parse(startedAt)),
      engineVersion: "aot-backtest-1.1.0",
      environment: runMetadata?.environment ?? "paper-research",
      timezone: runMetadata?.timezone ?? "Asia/Bangkok",
      currency: "THB",
      tradingCalendar: runMetadata?.tradingCalendar ?? "SET daily calendar inferred from timestamps",
      executionMode,
      intrabarBarsUsed: intrabar.length,
      intrabarFallback: executionMode === "INTRABAR_EXACT" && intrabar.length === 0,
    },
    events,
  };
}
