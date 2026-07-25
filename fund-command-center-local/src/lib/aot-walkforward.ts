import {
  runAotBacktest,
  type BacktestConfig,
  type ExecutionMode,
  type GridType,
  type MarketBar,
} from "./aot-backtest.ts";

/**
 * Walk-forward evaluation shared by the CLI harness (scripts/aot-walkforward.mjs)
 * and the in-app Walk-Forward Lab. Extracting it means the education view shows the
 * SAME numbers as the committed E-series research — a divergence would teach a
 * falsehood. The protocol and pass criteria are declared in
 * docs/AOT_VALIDATION_CRITERIA.md and are not tuned to fit a result. This module
 * only measures; it decides nothing and places no order.
 */

// ---- protocol constants (docs/AOT_VALIDATION_CRITERIA.md §3) ----------------
export const IS_BARS = 504;
export const OOS_BARS = 252;
export const STEP = 252;
const MODES: ExecutionMode[] = ["CONSERVATIVE_OHLC", "WORST_CASE", "OPTIMISTIC_OHLC"];
const PASS_MODES: ExecutionMode[] = ["CONSERVATIVE_OHLC", "WORST_CASE"];
const GRID_COUNTS = [8, 10, 12];
const RANGE_SCALES = [0.9, 1.0, 1.1];
export const CAPITAL = 1_000_000;
const REGIME_FILTER = { lookback: 20, rankWindow: 252, upperRank: 80, lowerRank: 20 };

// Thai retail cost model, percent units (engine divides by 100).
export const COSTS = {
  commissionRate: 0.157,
  exchangeFeeRate: 0.005,
  vatRate: 7,
  slippageRate: 0.05,
};

export type CostModel = typeof COSTS;

export type WalkForwardOptions = {
  regime?: boolean;
  trailing?: boolean;
  exposureCap?: boolean;
  // Cost override for the education view: let a student watch the grid edge survive
  // gross and die net. Omitted keys fall back to the Thai-retail default, so the
  // no-argument call still reproduces the committed E-series numbers exactly.
  costs?: Partial<CostModel>;
  /**
   * Also measure OOS for the geometry candidates that selection REJECTED, so the
   * education view can show that winning in-sample does not predict out-of-sample.
   * Off by default and deliberately excluded from `runCount`: those runs are not
   * part of the protocol's multiple-testing surface (nothing is selected on them),
   * and inflating the reported count would misstate the research.
   */
  diagnostics?: boolean;
};

export type Geometry = { lowerPrice: number; upperPrice: number; gridCount: number; gridType: GridType };

export type FoldMeasure = {
  runId: string;
  configHash: string | null;
  totalReturn: number;
  maxDrawdown: number;
  robust: number;
  alpha: number;
  buyAndHoldReturn: number;
  completedCycles: number;
  fills: number;
  engaged: boolean;
  isReconciled: boolean;
  ambiguousBars: number;
  reAnchors: number;
  regimeSuspendedBars: number;
  totalFees: number;
  forcedLiquidation: boolean;
  endingInventory: number;
  maxCapitalDeployed: number;
};

/**
 * One geometry candidate scored on BOTH windows. `isRobust` is what selection is
 * allowed to see; `oosRobust` is what actually happened afterwards. Present only
 * when `diagnostics` is on — it is teaching material, not part of the protocol.
 */
export type CandidateScore = {
  gridType: GridType;
  gridCount: number;
  isRobust: number;
  oosRobust: number;
  selected: boolean;
};

export type WalkForwardFold = {
  index: number;
  isRange: [string, string];
  oosRange: [string, string];
  selected: Geometry;
  isRobust: number;
  oos: Record<string, FoldMeasure>;
  buyAndHoldDrawdown: number;
  perturbations: Array<{ gridCount: number; scale: number } & FoldMeasure>;
  candidates?: CandidateScore[];
};

export type ModeResult = {
  mode: string;
  folds: number;
  meanRobust: number;
  meanAlpha: number;
  meanReturn: number;
  meanBuyAndHold: number;
  meanDrawdown: number;
  meanBuyAndHoldDrawdown: number;
  engagedPct: number;
  beatsBuyHoldPct: number;
  reconciledAll: boolean;
  C1: boolean;
  C2: boolean;
  C3: boolean;
  C4: boolean;
  C6: boolean;
};

export type WalkForwardResult = {
  folds: WalkForwardFold[];
  modeResults: ModeResult[];
  C5: boolean;
  C6: boolean;
  C7: boolean;
  passed: boolean;
  flatSurfacePct: number;
  optimismGap: number;
  runCount: number;
  protocol: { IS_BARS: number; OOS_BARS: number; STEP: number; COSTS: typeof COSTS; CAPITAL: number };
};

const dateOnly = (timestamp: string) => timestamp.slice(0, 10);
const mean = (values: number[]) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0);
const pct = (part: number, whole: number) => (whole ? (part / whole) * 100 : 0);

/** Buy-and-hold max drawdown over a bar window, in percent (C3 needs this). */
function buyAndHoldDrawdown(bars: MarketBar[]) {
  let peak = bars[0].close;
  let maxDd = 0;
  for (const bar of bars) {
    peak = Math.max(peak, bar.high ?? bar.close);
    const low = bar.low ?? bar.close;
    maxDd = Math.max(maxDd, ((peak - low) / peak) * 100);
  }
  return maxDd;
}

/**
 * Grid geometry derived from IN-SAMPLE bars only. Widening the range with any
 * out-of-sample bar would be lookahead — AOT ran 5 -> 64 THB, so a range fitted on
 * the whole file silently guarantees a good result.
 */
function geometryFromInSample(isBars: MarketBar[], gridCount: number, rangeScale: number, gridType: GridType): Geometry {
  const closes = isBars.map((bar) => bar.close).sort((a, b) => a - b);
  const at = (q: number) => closes[Math.min(closes.length - 1, Math.floor(q * closes.length))];
  const mid = at(0.5);
  const lower = mid - (mid - at(0.05)) * rangeScale;
  const upper = mid + (at(0.95) - mid) * rangeScale;
  return { lowerPrice: Math.max(0.01, lower), upperPrice: upper, gridCount, gridType };
}

function configFor(geometry: Geometry, window: MarketBar[], executionMode: ExecutionMode, firstClose: number, options: WalkForwardOptions): BacktestConfig {
  // Standard grid posture: half the book in stock so sells above the reference
  // level are possible from bar one; the rest in cash to buy the way down.
  const inventory = Math.floor(CAPITAL / 2 / firstClose / 100) * 100;
  const trailingOn = Boolean(options.trailing) || Boolean(options.exposureCap);
  const costs = { ...COSTS, ...(options.costs ?? {}) };
  return {
    symbol: "AOT",
    startDate: dateOnly(window[0].timestamp),
    endDate: dateOnly(window[window.length - 1].timestamp),
    initialCapital: CAPITAL,
    initialCash: CAPITAL - inventory * firstClose,
    initialInventory: inventory,
    ...geometry,
    tickSize: 0.25,
    boardLot: 100,
    ...costs,
    fillModel: "CONSERVATIVE",
    endTreatment: "MARK_TO_MARKET",
    dividendInclusion: false,
    dividendReinvestment: false,
    cashConstraint: true,
    executionMode,
    regimeFilter: options.regime ? REGIME_FILTER : null,
    trailing: trailingOn ? { mode: "TRAIL_UP" } : null,
    exposureCap: options.exposureCap ? { mode: "GRID_CAPACITY" } : null,
  };
}

export type FixedGeometryFold = {
  index: number;
  oosRange: [string, string];
  /** The user's geometry exactly as configured. */
  absolute: FoldMeasure;
  /** Same shape (width ratio, count, type) re-anchored to that era's price level. */
  scaled: FoldMeasure;
  scaledBounds: [number, number];
  buyAndHoldDrawdown: number;
  /** Nudged variants of the shape-adjusted grid, scored on the same OOS window. */
  perturbations: Array<{ gridCount: number; scale: number; robust: number; engaged: boolean }>;
};

export type FixedGeometryResult = {
  geometry: Geometry;
  folds: FixedGeometryFold[];
  summary: {
    folds: number;
    absolute: { meanRobust: number; meanAlpha: number; meanDrawdown: number; engagedPct: number };
    scaled: { meanRobust: number; meanAlpha: number; meanDrawdown: number; engagedPct: number };
    meanBuyAndHoldRobust: number;
    /**
     * C7-style sensitivity on the shape-adjusted grid: share of nudged variants that
     * still score robust > 0. A result that only survives at the exact settings the
     * user typed is a knife-edge, not an edge.
     */
    flatSurfacePct: number;
    perturbationCount: number;
    /** Spread of robust across the nudged variants, averaged per fold. */
    meanPerturbationSpread: number;
  };
};

/**
 * Evaluate ONE fixed geometry across every out-of-sample window — the question a
 * user of the paper console actually has: "the grid I configured, what would it have
 * done in 18 periods it never saw?" There is no selection step, so nothing here is
 * fitted to the data it is scored on.
 *
 * Two rows, because a grid written in absolute prices carries a hidden assumption.
 * AOT ran roughly 5 -> 64 THB over this file, so a 60-70 THB grid is simply absent
 * from the market for most of the history: `absolute` shows that honestly (expect
 * engaged to collapse), while `scaled` keeps the same width ratio and level count
 * but re-anchors to each era's price, isolating whether the SHAPE has any merit.
 */
export function runFixedGeometryWalkForward(
  bars: MarketBar[],
  geometry: Geometry,
  options: WalkForwardOptions = {},
): FixedGeometryResult {
  const WARMUP = REGIME_FILTER.rankWindow + REGIME_FILTER.lookback + 30;
  const withWarmup = (from: number, to: number) => bars.slice(Math.max(0, from - WARMUP), to);
  const measure = (geo: Geometry, window: MarketBar[], supplied: MarketBar[]): FoldMeasure => {
    const config = configFor(geo, window, "CONSERVATIVE_OHLC", window[0].close, options);
    const run = runAotBacktest(config, supplied);
    const m = run.metrics;
    return {
      runId: run.id,
      configHash: run.metadata?.configurationHash ?? null,
      totalReturn: m.totalReturn,
      maxDrawdown: m.maxDrawdown,
      robust: m.totalReturn - 2 * m.maxDrawdown,
      alpha: m.alpha ?? 0,
      buyAndHoldReturn: m.buyAndHoldReturn ?? 0,
      completedCycles: m.completedCycles,
      fills: m.fills,
      engaged: m.completedCycles >= 1,
      isReconciled: m.isReconciled,
      ambiguousBars: m.ambiguousBars,
      reAnchors: m.reAnchors,
      regimeSuspendedBars: m.regimeSuspendedBars,
      totalFees: m.totalFees,
      forcedLiquidation: m.forcedLiquidation,
      endingInventory: m.endingInventory,
      maxCapitalDeployed: m.maxCapitalDeployed,
    };
  };

  const folds: FixedGeometryFold[] = [];
  const midpoint = (geometry.lowerPrice + geometry.upperPrice) / 2;
  for (let start = 0; start + IS_BARS + OOS_BARS <= bars.length; start += STEP) {
    const isWindow = bars.slice(start, start + IS_BARS);
    const oosWindow = bars.slice(start + IS_BARS, start + IS_BARS + OOS_BARS);
    const oosSupplied = withWarmup(start + IS_BARS, start + IS_BARS + OOS_BARS);

    // Re-anchor on the IN-SAMPLE median only: using out-of-sample prices to place
    // the grid would be lookahead, which is the whole thing this page must not do.
    const closes = isWindow.map((bar) => bar.close).sort((a, b) => a - b);
    const isMedian = closes[Math.floor(closes.length / 2)];
    const factor = midpoint > 0 ? isMedian / midpoint : 1;
    const scaledGeometry: Geometry = {
      ...geometry,
      lowerPrice: Math.max(0.01, geometry.lowerPrice * factor),
      upperPrice: Math.max(0.02, geometry.upperPrice * factor),
    };

    // Parameter sensitivity: nudge count and width around the shape-adjusted grid
    // (the absolute one is era-locked and mostly out of the market, so perturbing it
    // would measure absence rather than sensitivity).
    const scaledMid = (scaledGeometry.lowerPrice + scaledGeometry.upperPrice) / 2;
    const perturbations: FixedGeometryFold["perturbations"] = [];
    for (const gridCount of [geometry.gridCount - 2, geometry.gridCount, geometry.gridCount + 2]) {
      if (gridCount < 4) continue;
      for (const scale of RANGE_SCALES) {
        const variant: Geometry = {
          ...scaledGeometry,
          gridCount,
          lowerPrice: Math.max(0.01, scaledMid - (scaledMid - scaledGeometry.lowerPrice) * scale),
          upperPrice: scaledMid + (scaledGeometry.upperPrice - scaledMid) * scale,
        };
        const result = measure(variant, oosWindow, oosSupplied);
        perturbations.push({ gridCount, scale, robust: result.robust, engaged: result.engaged });
      }
    }

    folds.push({
      index: folds.length + 1,
      oosRange: [dateOnly(oosWindow[0].timestamp), dateOnly(oosWindow[oosWindow.length - 1].timestamp)],
      absolute: measure(geometry, oosWindow, oosSupplied),
      scaled: measure(scaledGeometry, oosWindow, oosSupplied),
      scaledBounds: [scaledGeometry.lowerPrice, scaledGeometry.upperPrice],
      buyAndHoldDrawdown: buyAndHoldDrawdown(oosWindow),
      perturbations,
    });
  }

  const allPerturbations = folds.flatMap((fold) => fold.perturbations);
  const agg = (pick: (fold: FixedGeometryFold) => FoldMeasure) => ({
    meanRobust: mean(folds.map((f) => pick(f).robust)),
    meanAlpha: mean(folds.map((f) => pick(f).alpha)),
    meanDrawdown: mean(folds.map((f) => pick(f).maxDrawdown)),
    engagedPct: pct(folds.filter((f) => pick(f).engaged).length, folds.length),
  });

  return {
    geometry,
    folds,
    summary: {
      folds: folds.length,
      absolute: agg((f) => f.absolute),
      scaled: agg((f) => f.scaled),
      meanBuyAndHoldRobust: mean(folds.map((f) => f.absolute.buyAndHoldReturn - 2 * f.buyAndHoldDrawdown)),
      flatSurfacePct: pct(
        allPerturbations.filter((p) => p.robust > 0).length,
        allPerturbations.length,
      ),
      perturbationCount: allPerturbations.length,
      meanPerturbationSpread: mean(
        folds.map((fold) =>
          fold.perturbations.length
            ? Math.max(...fold.perturbations.map((p) => p.robust)) -
              Math.min(...fold.perturbations.map((p) => p.robust))
            : 0,
        ),
      ),
    },
  };
}

/**
 * Run the anchored-rolling walk-forward over `bars` (already parsed and quality-
 * checked by the caller). `bars` must be the full series so warm-up before each
 * window comes from real past data, not lookahead.
 */
export function runAotWalkForward(bars: MarketBar[], options: WalkForwardOptions = {}): WalkForwardResult {
  let runCount = 0;
  const WARMUP = REGIME_FILTER.rankWindow + REGIME_FILTER.lookback + 30;
  const withWarmup = (from: number, to: number) => bars.slice(Math.max(0, from - WARMUP), to);

  const measure = (
    geometry: Geometry,
    window: MarketBar[],
    executionMode: ExecutionMode,
    supplied: MarketBar[] = window,
    // Diagnostic runs feed the education view only; they select nothing, so they are
    // kept out of the multiple-testing count the research reports.
    countsTowardProtocol = true,
  ): FoldMeasure => {
    if (countsTowardProtocol) runCount += 1;
    const config = configFor(geometry, window, executionMode, window[0].close, options);
    const run = runAotBacktest(config, supplied);
    const m = run.metrics;
    return {
      runId: run.id,
      configHash: run.metadata?.configurationHash ?? null,
      totalReturn: m.totalReturn,
      maxDrawdown: m.maxDrawdown,
      robust: m.totalReturn - 2 * m.maxDrawdown,
      alpha: m.alpha ?? 0,
      buyAndHoldReturn: m.buyAndHoldReturn ?? 0,
      completedCycles: m.completedCycles,
      fills: m.fills,
      engaged: m.completedCycles >= 1,
      isReconciled: m.isReconciled,
      ambiguousBars: m.ambiguousBars,
      reAnchors: m.reAnchors,
      regimeSuspendedBars: m.regimeSuspendedBars,
      totalFees: m.totalFees,
      forcedLiquidation: m.forcedLiquidation,
      endingInventory: m.endingInventory,
      maxCapitalDeployed: m.maxCapitalDeployed,
    };
  };

  const folds: WalkForwardFold[] = [];
  for (let start = 0; start + IS_BARS + OOS_BARS <= bars.length; start += STEP) {
    const isWindow = bars.slice(start, start + IS_BARS);
    const oosWindow = bars.slice(start + IS_BARS, start + IS_BARS + OOS_BARS);
    const isSupplied = withWarmup(start, start + IS_BARS);
    const oosSupplied = withWarmup(start + IS_BARS, start + IS_BARS + OOS_BARS);

    // Selection step: pick geometry on IS only, by IS robust score.
    let selected: { geometry: Geometry; result: FoldMeasure } | null = null;
    const tried: Array<{ geometry: Geometry; isRobust: number }> = [];
    for (const gridType of ["ARITHMETIC", "GEOMETRIC"] as GridType[]) {
      for (const gridCount of GRID_COUNTS) {
        const geometry = geometryFromInSample(isWindow, gridCount, 1.0, gridType);
        const result = measure(geometry, isWindow, "CONSERVATIVE_OHLC", isSupplied);
        tried.push({ geometry, isRobust: result.robust });
        if (!selected || result.robust > selected.result.robust) selected = { geometry, result };
      }
    }
    if (!selected) continue;

    const oos: Record<string, FoldMeasure> = {};
    for (const mode of MODES) oos[mode] = measure(selected.geometry, oosWindow, mode, oosSupplied);

    // Education diagnostic: score every candidate on OOS too, including the ones
    // selection rejected. The selected one reuses its already-measured OOS run.
    let candidates: CandidateScore[] | undefined;
    if (options.diagnostics) {
      candidates = tried.map((candidate) => {
        const isSelected =
          candidate.geometry.gridType === selected!.geometry.gridType &&
          candidate.geometry.gridCount === selected!.geometry.gridCount;
        const oosRobust = isSelected
          ? oos.CONSERVATIVE_OHLC.robust
          : measure(candidate.geometry, oosWindow, "CONSERVATIVE_OHLC", oosSupplied, false).robust;
        return {
          gridType: candidate.geometry.gridType,
          gridCount: candidate.geometry.gridCount,
          isRobust: candidate.isRobust,
          oosRobust,
          selected: isSelected,
        };
      });
    }

    // C7 sensitivity: perturb the selected geometry, evaluate on OOS.
    const perturbations: Array<{ gridCount: number; scale: number } & FoldMeasure> = [];
    for (const gridCount of [selected.geometry.gridCount - 2, selected.geometry.gridCount, selected.geometry.gridCount + 2]) {
      if (gridCount < 4) continue;
      for (const scale of RANGE_SCALES) {
        const geometry = geometryFromInSample(isWindow, gridCount, scale, selected.geometry.gridType);
        perturbations.push({ gridCount, scale, ...measure(geometry, oosWindow, "CONSERVATIVE_OHLC", oosSupplied) });
      }
    }

    folds.push({
      index: folds.length + 1,
      isRange: [dateOnly(isWindow[0].timestamp), dateOnly(isWindow[isWindow.length - 1].timestamp)],
      oosRange: [dateOnly(oosWindow[0].timestamp), dateOnly(oosWindow[oosWindow.length - 1].timestamp)],
      selected: selected.geometry,
      isRobust: selected.result.robust,
      oos,
      buyAndHoldDrawdown: buyAndHoldDrawdown(oosWindow),
      candidates,
      perturbations,
    });
  }

  const evaluateMode = (mode: string): ModeResult => {
    const rows = folds.map((fold) => fold.oos[mode]);
    const engaged = rows.filter((row) => row.engaged);
    const beatsBuyHold = rows.filter((row) => row.alpha > 0);
    const meanDd = mean(rows.map((row) => row.maxDrawdown));
    const meanBhDd = mean(folds.map((fold) => fold.buyAndHoldDrawdown));
    return {
      mode,
      folds: rows.length,
      meanRobust: mean(rows.map((row) => row.robust)),
      meanAlpha: mean(rows.map((row) => row.alpha)),
      meanReturn: mean(rows.map((row) => row.totalReturn)),
      meanBuyAndHold: mean(rows.map((row) => row.buyAndHoldReturn)),
      meanDrawdown: meanDd,
      meanBuyAndHoldDrawdown: meanBhDd,
      engagedPct: pct(engaged.length, rows.length),
      beatsBuyHoldPct: pct(beatsBuyHold.length, rows.length),
      reconciledAll: rows.every((row) => row.isReconciled),
      C1: mean(rows.map((row) => row.robust)) > 0,
      C2: mean(rows.map((row) => row.alpha)) > 0 && pct(beatsBuyHold.length, rows.length) > 50,
      C3: meanDd <= meanBhDd,
      C4: pct(engaged.length, rows.length) >= 50,
      C6: rows.every((row) => row.isReconciled) && folds.every((_, i) => pct(rows[i].ambiguousBars, OOS_BARS) <= 5),
    };
  };

  const modeResults = PASS_MODES.map(evaluateMode);
  const allPerturbations = folds.flatMap((fold) => fold.perturbations);
  const flatSurfacePct = pct(allPerturbations.filter((row) => row.robust > 0).length, allPerturbations.length);
  const C5 = modeResults.every((r) => r.C1 && r.C2 && r.C3 && r.C4);
  const C7 = flatSurfacePct >= 60;
  const C6 = modeResults.every((r) => r.C6);
  const passed = C5 && C6 && C7;
  const optimismGap =
    mean(folds.map((fold) => fold.oos.OPTIMISTIC_OHLC.totalReturn)) -
    mean(folds.map((fold) => fold.oos.CONSERVATIVE_OHLC.totalReturn));

  return {
    folds,
    modeResults,
    C5,
    C6,
    C7,
    passed,
    flatSurfacePct,
    optimismGap,
    runCount,
    protocol: { IS_BARS, OOS_BARS, STEP, COSTS, CAPITAL },
  };
}
