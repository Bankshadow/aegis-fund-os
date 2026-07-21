import "@tanstack/react-start/server-only";

import { GridBotRepository, type D1DatabaseLike } from "./grid-bot-repository";
import { getBinanceTestnetGridStatus } from "./binance-testnet.server";
import { placeSingleTestnetOrder } from "./binance-testnet-execution";
import { reconcileAllRunningTestnetGrids } from "./grid-reconcile";

/** Server-only scheduled reconciliation driver. */
export async function runScheduledGridReconciliation(env: {
  GOVERNANCE_DB?: D1DatabaseLike;
  GRID_CRON_ENABLED?: string;
}): Promise<{
  enabled: boolean;
  results: Awaited<ReturnType<typeof reconcileAllRunningTestnetGrids>>;
}> {
  if (env.GRID_CRON_ENABLED?.trim() !== "true") return { enabled: false, results: [] };
  if (!env.GOVERNANCE_DB)
    throw new Error("Governance storage is unavailable; scheduled reconcile blocked");
  const repo = new GridBotRepository(env.GOVERNANCE_DB);
  const results = await reconcileAllRunningTestnetGrids(repo, "system:grid-cron", {
    getStatus: getBinanceTestnetGridStatus,
    placeOrder: placeSingleTestnetOrder,
  });
  return { enabled: true, results };
}
