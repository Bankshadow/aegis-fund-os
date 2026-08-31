import type { MarketBar } from "./aot-backtest.ts";
import {
  COSTS as DEFAULT_COSTS,
  runAotWalkForward,
  type CostModel,
  type WalkForwardResult,
} from "./aot-walkforward.ts";

/**
 * Pure builders for the Walk-Forward Lab views, deliberately free of any server
 * plumbing so the build-time precompute script can call them directly.
 *
 * These are the SAME `runAotWalkForward` the CLI research uses. Bars are passed in
 * rather than imported, so this module works under plain Node (the precompute
 * script) as well as under Vite. Read-only research: no order, no live data.
 *
 * They are also expensive — the comparison view alone is 1,296 backtests (four
 * mechanisms) and roughly 12s of CPU. That is fine at build time and NOT fine
 * inside a Cloudflare Worker request, which is why `scripts/precompute-walkforward.mjs`
 * runs everything ahead of time and the server functions only look results up.
 */
const VARIANTS = {
  baseline: {},
  trailing: { trailing: true },
  "exposure-cap": { exposureCap: true },
  "inventory-recycle": { inventoryRecycle: true },
} as const;

export type WalkForwardVariant = keyof typeof VARIANTS;

/**
 * Cost scenarios offered to students. A closed set rather than free-form numbers:
 * it keeps every reachable page precomputable, so no student request can trigger a
 * multi-second walk-forward on the Worker. "No cost" zeroes EVERY component — a
 * student testing the "it's just the fees" theory must get a genuinely fee-free run.
 */
export const COST_PRESETS = {
  thai: undefined,
  zero: { commissionRate: 0, slippageRate: 0, exchangeFeeRate: 0, vatRate: 0 },
  heavy: { commissionRate: 0.5, slippageRate: 0.3 },
} as const satisfies Record<string, Partial<CostModel> | undefined>;

export type CostPresetId = keyof typeof COST_PRESETS;
export const COST_PRESET_IDS = Object.keys(COST_PRESETS) as CostPresetId[];
export const VARIANT_IDS = Object.keys(VARIANTS) as WalkForwardVariant[];

export type WalkForwardFoldRow = {
  index: number;
  oosRange: [string, string];
  gridType: string;
  gridCount: number;
  totalReturn: number;
  buyAndHoldReturn: number;
  alpha: number;
  maxDrawdown: number;
  buyAndHoldDrawdown: number;
  robust: number;
  completedCycles: number;
  engaged: boolean;
};

export type WalkForwardView = {
  variant: WalkForwardVariant;
  folds: WalkForwardFoldRow[];
  summary: {
    folds: number;
    meanRobust: number;
    meanAlpha: number;
    meanReturn: number;
    meanBuyAndHold: number;
    meanDrawdown: number;
    meanBuyAndHoldDrawdown: number;
    engagedPct: number;
    beatsBuyHoldPct: number;
    flatSurfacePct: number;
    /**
     * Buy-and-hold scored on the SAME robust formula, averaged per fold. Without
     * this a student has no scale: "robust -17.97" means nothing on its own, but
     * "-17.97 vs buy-and-hold's -34.07, and the bar to pass is 0" is readable.
     */
    meanBuyAndHoldRobust: number;
  };
  criteria: { C1: boolean; C2: boolean; C3: boolean; C4: boolean; C5: boolean; C6: boolean; C7: boolean; passed: boolean };
  costs: CostModel;
  protocol: WalkForwardResult["protocol"];
};

export type OverfitView = {
  folds: Array<{
    index: number;
    isRange: [string, string];
    oosRange: [string, string];
    candidates: Array<{ label: string; isRobust: number; oosRobust: number; selected: boolean; oosRank: number }>;
    pickOosRank: number;
  }>;
  summary: {
    folds: number;
    candidatesPerFold: number;
    /** How often the in-sample winner was also the out-of-sample winner. */
    pickWasBest: number;
    /** Same, if you had picked at random: folds / candidatesPerFold. */
    randomWouldBe: number;
    meanPickRank: number;
    /** Mean rank a random pick would get, i.e. (n+1)/2. */
    randomMeanRank: number;
    meanPickOos: number;
    meanCandidateOos: number;
    /** Best OOS candidate per fold, averaged — the unattainable hindsight ceiling. */
    meanHindsightBestOos: number;
  };
};

export type WalkForwardComparison = {
  variants: WalkForwardView[];
  // Per-fold robust and cycles across the mechanism variants, so a student can see
  // which folds a mechanism actually moved (and which it silenced to cycles=0).
  folds: Array<{
    index: number;
    oosRange: [string, string];
    cells: Array<{ robust: number; alpha: number; cycles: number; engaged: boolean }>;
  }>;
};

export function buildView(
  bars: MarketBar[],
  variant: WalkForwardVariant,
  costPreset: CostPresetId = "thai",
): WalkForwardView {
  const costs = COST_PRESETS[costPreset];
  const effectiveCosts = { ...DEFAULT_COSTS, ...(costs ?? {}) };
  const result = runAotWalkForward(bars, { ...VARIANTS[variant], costs });
  const conservative = result.modeResults.find((r) => r.mode === "CONSERVATIVE_OHLC")!;
  const folds: WalkForwardFoldRow[] = result.folds.map((fold) => {
    const c = fold.oos.CONSERVATIVE_OHLC;
    return {
      index: fold.index,
      oosRange: fold.oosRange,
      gridType: fold.selected.gridType,
      gridCount: fold.selected.gridCount,
      totalReturn: c.totalReturn,
      buyAndHoldReturn: c.buyAndHoldReturn,
      alpha: c.alpha,
      maxDrawdown: c.maxDrawdown,
      buyAndHoldDrawdown: fold.buyAndHoldDrawdown,
      robust: c.robust,
      completedCycles: c.completedCycles,
      engaged: c.engaged,
    };
  });
  return {
    variant,
    folds,
    summary: {
      folds: conservative.folds,
      meanRobust: conservative.meanRobust,
      meanAlpha: conservative.meanAlpha,
      meanReturn: conservative.meanReturn,
      meanBuyAndHold: conservative.meanBuyAndHold,
      meanDrawdown: conservative.meanDrawdown,
      meanBuyAndHoldDrawdown: conservative.meanBuyAndHoldDrawdown,
      engagedPct: conservative.engagedPct,
      beatsBuyHoldPct: conservative.beatsBuyHoldPct,
      flatSurfacePct: result.flatSurfacePct,
      meanBuyAndHoldRobust:
        folds.reduce((sum, fold) => sum + (fold.buyAndHoldReturn - 2 * fold.buyAndHoldDrawdown), 0) /
        (folds.length || 1),
    },
    criteria: {
      C1: conservative.C1,
      C2: conservative.C2,
      C3: conservative.C3,
      C4: conservative.C4,
      C5: result.C5,
      C6: result.C6,
      C7: result.C7,
      passed: result.passed,
    },
    costs: effectiveCosts,
    protocol: result.protocol,
  };
}

/**
 * The overfitting lesson: score every geometry candidate on BOTH windows and show
 * that picking the in-sample winner does not predict the out-of-sample winner.
 * Uses the diagnostics option, which is excluded from the protocol's run count.
 */
export function buildOverfitView(bars: MarketBar[]): OverfitView {
  const result = runAotWalkForward(bars, { diagnostics: true });
  const folds = result.folds.map((fold) => {
    const scored = fold.candidates ?? [];
    const byOos = [...scored].sort((a, b) => b.oosRobust - a.oosRobust);
    const candidates = scored.map((candidate) => ({
      label: `${candidate.gridType === "GEOMETRIC" ? "GEO" : "ARI"} ×${candidate.gridCount}`,
      isRobust: candidate.isRobust,
      oosRobust: candidate.oosRobust,
      selected: candidate.selected,
      oosRank: byOos.findIndex((c) => c.gridType === candidate.gridType && c.gridCount === candidate.gridCount) + 1,
    }));
    return {
      index: fold.index,
      isRange: fold.isRange,
      oosRange: fold.oosRange,
      candidates,
      pickOosRank: candidates.find((c) => c.selected)?.oosRank ?? 0,
    };
  });
  const avg = (values: number[]) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0);
  const n = folds[0]?.candidates.length ?? 0;
  return {
    folds,
    summary: {
      folds: folds.length,
      candidatesPerFold: n,
      pickWasBest: folds.filter((f) => f.pickOosRank === 1).length,
      randomWouldBe: n ? folds.length / n : 0,
      meanPickRank: avg(folds.map((f) => f.pickOosRank)),
      randomMeanRank: (n + 1) / 2,
      meanPickOos: avg(folds.map((f) => f.candidates.find((c) => c.selected)?.oosRobust ?? 0)),
      meanCandidateOos: avg(folds.map((f) => avg(f.candidates.map((c) => c.oosRobust)))),
      meanHindsightBestOos: avg(folds.map((f) => Math.max(...f.candidates.map((c) => c.oosRobust)))),
    },
  };
}

/** Lines the four mechanisms up for the E26 -> E28 -> E29 -> E30 teaching comparison. */
export function buildComparison(views: WalkForwardView[]): WalkForwardComparison {
  const folds = views[0].folds.map((fold, i) => ({
    index: fold.index,
    oosRange: fold.oosRange,
    cells: views.map((v) => ({
      robust: v.folds[i].robust,
      alpha: v.folds[i].alpha,
      cycles: v.folds[i].completedCycles,
      engaged: v.folds[i].engaged,
    })),
  }));
  return { variants: views, folds };
}
