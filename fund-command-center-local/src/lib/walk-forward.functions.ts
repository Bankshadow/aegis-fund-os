import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import aotCsv from "../../data/historical/AOT.BK_daily_2005-2026.csv?raw";
import { parseMarketCsv } from "./aot-backtest";
import { COSTS as DEFAULT_COSTS, runAotWalkForward, type CostModel, type WalkForwardResult } from "./aot-walkforward";

/**
 * Server function behind the Walk-Forward Lab education view. It runs the SAME
 * `runAotWalkForward` the CLI research uses over the committed AOT fixture (bundled
 * as a string via `?raw`, so this works in dev and on the Worker without disk
 * access). It is read-only research: no order, no live data.
 *
 * Variant maps to the E-series mechanisms so a student can compare the honest
 * results: baseline grid (E26), + trailing (E28), + trailing & exposure cap (E29).
 */
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
  };
  criteria: { C1: boolean; C2: boolean; C3: boolean; C4: boolean; C5: boolean; C6: boolean; C7: boolean; passed: boolean };
  costs: CostModel;
  protocol: WalkForwardResult["protocol"];
};

const buildView = (variant: WalkForwardVariant, costs?: Partial<CostModel>): WalkForwardView => {
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
    }),
  )
  .handler(({ data }) => {
    const costs: Partial<CostModel> = {};
    if (data.commissionRate !== undefined) costs.commissionRate = data.commissionRate;
    if (data.slippageRate !== undefined) costs.slippageRate = data.slippageRate;
    return buildView(data.variant, Object.keys(costs).length ? costs : undefined);
  });

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
