import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import aotCsv from "../../data/historical/AOT.BK_daily_2005-2026.csv?raw";
import precomputed from "../generated/walk-forward-data.json";
import { parseMarketCsv } from "./aot-backtest";
import { runFixedGeometryWalkForward, type CostModel } from "./aot-walkforward";
import type {
  CostPresetId,
  OverfitView,
  WalkForwardComparison,
  WalkForwardVariant,
  WalkForwardView,
} from "./walk-forward-views";

export type {
  CostPresetId,
  OverfitView,
  WalkForwardComparison,
  WalkForwardFoldRow,
  WalkForwardVariant,
  WalkForwardView,
} from "./walk-forward-views";

/**
 * The Walk-Forward Lab views are served from `scripts/precompute-walkforward.mjs`
 * output, not computed per request.
 *
 * They are pure and expensive — the comparison is 972 backtests, ~8.9s of CPU — and
 * a Worker request is the wrong place for that: it is slow for the student and can
 * exceed the Worker CPU limit outright. Per-isolate memoisation was not enough,
 * since every cold isolate pays the cost again. The fixture and engine are static,
 * so the result cannot change between deploys.
 *
 * Read-only research: no order, no live data.
 */
const DATA = precomputed as unknown as {
  generatedAt: string;
  views: Record<string, WalkForwardView>;
  comparison: WalkForwardComparison;
  overfit: OverfitView;
};

const viewKey = (variant: WalkForwardVariant, cost: CostPresetId) => `${variant}:${cost}`;

export const getWalkForwardView = createServerFn({ method: "GET" })
  .validator(
    z.object({
      variant: z.enum(["baseline", "trailing", "exposure-cap"]).default("baseline"),
      // Closed preset set, not free-form numbers: every reachable combination is
      // precomputed, so no student request can trigger a walk-forward on the Worker.
      cost: z.enum(["thai", "zero", "heavy"]).default("thai"),
    }),
  )
  .handler(({ data }): WalkForwardView => {
    const view = DATA.views[viewKey(data.variant, data.cost)];
    if (!view) throw new Error(`No precomputed view for ${viewKey(data.variant, data.cost)}`);
    return view;
  });

export const getWalkForwardComparison = createServerFn({ method: "GET" }).handler(
  (): WalkForwardComparison => DATA.comparison,
);

export const getOverfitView = createServerFn({ method: "GET" }).handler((): OverfitView => DATA.overfit);

/**
 * "Take the grid I configured on the paper console and score it on 18 periods it
 * never saw." The paper console can only ever produce an in-sample number — the
 * geometry is chosen by a human looking at the same chart — so this is the missing
 * half its own "Out-of-sample: Not tested" panel admits to.
 *
 * This one cannot be precomputed: the geometry comes from the user. It is a single
 * fixed-geometry pass plus the sensitivity sweep (~1.3s), it runs only on an
 * explicit button press, and it lives on the operations console rather than a
 * student page. Results are memoised per isolate, bounded so a user-driven key space
 * cannot grow without limit.
 */
const CACHE_LIMIT = 32;
const cache = new Map<string, unknown>();

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
    const key = JSON.stringify(data);
    const hit = cache.get(key);
    if (hit !== undefined) return hit as ReturnType<typeof runFixedGeometryWalkForward>;

    const { bars } = parseMarketCsv(aotCsv);
    const costs: Partial<CostModel> = {};
    if (data.commissionRate !== undefined) costs.commissionRate = data.commissionRate;
    if (data.slippageRate !== undefined) costs.slippageRate = data.slippageRate;
    const value = runFixedGeometryWalkForward(
      bars,
      {
        lowerPrice: data.lowerPrice,
        upperPrice: data.upperPrice,
        gridCount: data.gridCount,
        gridType: data.gridType,
      },
      Object.keys(costs).length ? { costs } : {},
    );
    if (cache.size >= CACHE_LIMIT) cache.delete(cache.keys().next().value as string);
    cache.set(key, value);
    return value;
  });
