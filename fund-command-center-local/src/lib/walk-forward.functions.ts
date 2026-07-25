import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import aotCsv from "../../data/historical/AOT.BK_daily_2005-2026.csv?raw";
import { parseMarketCsv } from "./aot-backtest";
import {
  COSTS as DEFAULT_COSTS,
  runAotWalkForward,
  runFixedGeometryWalkForward,
  type CostModel,
  type WalkForwardResult,
} from "./aot-walkforward";

/**
 * Server function behind the Walk-Forward Lab education view. It runs the SAME
 * `runAotWalkForward` the CLI research uses over the committed AOT fixture (bundled
 * as a string via `?raw`, so this works in dev and on the Worker without disk
 * access). It is read-only research: no order, no live data.
 *
 * Variant maps to the E-series mechanisms so a student can compare the honest
 * results: baseline grid (E26), + trailing (E28), + trailing & exposure cap (E29).
 */
/**
 * These walk-forwards are pure: the fixture is bundled and the engine is
 * deterministic, so the same arguments always produce the same result. They are also
 * expensive — the comparison view alone is 972 backtests, ~8.9s of CPU — and every
 * page view was recomputing them from scratch. Memoise per isolate, bounded so a
 * user-driven key space (the paper console's geometry check) cannot grow unbounded.
 */
const CACHE_LIMIT = 32;
const cache = new Map<string, unknown>();
function memoise<T>(key: string, compute: () => T): T {
  const hit = cache.get(key);
  if (hit !== undefined) return hit as T;
  const value = compute();
  if (cache.size >= CACHE_LIMIT) cache.delete(cache.keys().next().value as string);
  cache.set(key, value);
  return value;
}

const VARIANTS = {
  baseline: {},
  trailing: { trailing: true },
  "exposure-cap": { exposureCap: true },
} as const;

export type WalkForwardVariant = keyof typeof VARIANTS;

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
     * "-17.97 vs buy-and-hold's -34.06, and the bar to pass is 0" is readable.
     */
    meanBuyAndHoldRobust: number;
  };
  criteria: { C1: boolean; C2: boolean; C3: boolean; C4: boolean; C5: boolean; C6: boolean; C7: boolean; passed: boolean };
  costs: CostModel;
  protocol: WalkForwardResult["protocol"];
};

const buildView = (variant: WalkForwardVariant, costs?: Partial<CostModel>): WalkForwardView =>
  memoise(`view:${variant}:${JSON.stringify(costs ?? null)}`, () => buildViewUncached(variant, costs));

const buildViewUncached = (variant: WalkForwardVariant, costs?: Partial<CostModel>): WalkForwardView => {
  const { bars } = parseMarketCsv(aotCsv);
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
};

export const getWalkForwardView = createServerFn({ method: "GET" })
  .validator(
    z.object({
      variant: z.enum(["baseline", "trailing", "exposure-cap"]).default("baseline"),
      // Student-adjustable cost knobs, clamped to sane education ranges. Omitted =
      // Thai-retail default (reproduces the committed research).
      commissionRate: z.number().min(0).max(2).optional(),
      slippageRate: z.number().min(0).max(2).optional(),
      exchangeFeeRate: z.number().min(0).max(2).optional(),
      vatRate: z.number().min(0).max(20).optional(),
    }),
  )
  .handler(({ data }) => {
    const costs: Partial<CostModel> = {};
    if (data.commissionRate !== undefined) costs.commissionRate = data.commissionRate;
    if (data.slippageRate !== undefined) costs.slippageRate = data.slippageRate;
    if (data.exchangeFeeRate !== undefined) costs.exchangeFeeRate = data.exchangeFeeRate;
    if (data.vatRate !== undefined) costs.vatRate = data.vatRate;
    return buildView(data.variant, Object.keys(costs).length ? costs : undefined);
  });

/**
 * "Take the grid I configured on the paper console and score it on 18 periods it
 * never saw." The paper console can only ever produce an in-sample number — the
 * geometry is chosen by a human looking at the same chart — so this is the missing
 * half its own "Out-of-sample: Not tested" panel admits to.
 */
export const getFixedGeometryWalkForward = createServerFn({ method: "GET" })
  .validator(
    z.object({
      lowerPrice: z.number().positive(),
      upperPrice: z.number().positive(),
      gridCount: z.number().int().min(2).max(200),
      gridType: z.enum(["ARITHMETIC", "GEOMETRIC"]),
      commissionRate: z.number().min(0).max(2).optional(),
      slippageRate: z.number().min(0).max(2).optional(),
    }),
  )
  .handler(({ data }) => {
    if (data.upperPrice <= data.lowerPrice) throw new Error("upperPrice must exceed lowerPrice");
    return memoise(`fixed:${JSON.stringify(data)}`, () => {
      const { bars } = parseMarketCsv(aotCsv);
      const costs: Partial<CostModel> = {};
      if (data.commissionRate !== undefined) costs.commissionRate = data.commissionRate;
      if (data.slippageRate !== undefined) costs.slippageRate = data.slippageRate;
      return runFixedGeometryWalkForward(
        bars,
        {
          lowerPrice: data.lowerPrice,
          upperPrice: data.upperPrice,
          gridCount: data.gridCount,
          gridType: data.gridType,
        },
        Object.keys(costs).length ? { costs } : {},
      );
    });
  });

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

/**
 * The overfitting lesson: score every geometry candidate on BOTH windows and show
 * that picking the in-sample winner does not predict the out-of-sample winner.
 * Uses the diagnostics option, which is excluded from the protocol's run count.
 */
export const getOverfitView = createServerFn({ method: "GET" }).handler((): OverfitView =>
  memoise("overfit", () => buildOverfitView()),
);

function buildOverfitView(): OverfitView {
  const { bars } = parseMarketCsv(aotCsv);
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

export type WalkForwardComparison = {
  variants: WalkForwardView[];
  // Per-fold robust and cycles across the three variants, so a student can see
  // which folds a mechanism actually moved (and which it silenced to cycles=0).
  folds: Array<{
    index: number;
    oosRange: [string, string];
    cells: Array<{ robust: number; alpha: number; cycles: number; engaged: boolean }>;
  }>;
};

/**
 * Runs all three variants over the AOT fixture and lines them up for the
 * E26 -> E28 -> E29 teaching comparison. Three walk-forwards is deliberately heavy
 * (~a few seconds); it is a research view, not a hot path.
 */
export const getWalkForwardComparison = createServerFn({ method: "GET" }).handler((): WalkForwardComparison => {
  const order: WalkForwardVariant[] = ["baseline", "trailing", "exposure-cap"];
  const variants = order.map((v) => buildView(v));
  const folds = variants[0].folds.map((fold, i) => ({
    index: fold.index,
    oosRange: fold.oosRange,
    cells: variants.map((v) => ({
      robust: v.folds[i].robust,
      alpha: v.folds[i].alpha,
      cycles: v.folds[i].completedCycles,
      engaged: v.folds[i].engaged,
    })),
  }));
  return { variants, folds };
});
