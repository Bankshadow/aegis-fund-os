import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import aotCsv from "../../data/historical/AOT.BK_daily_2005-2026.csv?raw";
import { parseMarketCsv } from "./aot-backtest";
import { runAotWalkForward, type WalkForwardResult } from "./aot-walkforward";

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
  protocol: WalkForwardResult["protocol"];
};

const buildView = (variant: WalkForwardVariant): WalkForwardView => {
  const { bars } = parseMarketCsv(aotCsv);
  const result = runAotWalkForward(bars, VARIANTS[variant]);
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
    protocol: result.protocol,
  };
};

export const getWalkForwardView = createServerFn({ method: "GET" })
  .validator(z.object({ variant: z.enum(["baseline", "trailing", "exposure-cap"]).default("baseline") }))
  .handler(({ data }) => buildView(data.variant));
