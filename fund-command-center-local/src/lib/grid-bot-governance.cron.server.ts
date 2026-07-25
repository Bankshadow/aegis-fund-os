import "@tanstack/react-start/server-only";

import { GridBotRepository, type D1DatabaseLike } from "./grid-bot-repository";
import { getBinanceTestnetGridStatus } from "./binance-testnet.server";
import { placeSingleTestnetOrder } from "./binance-testnet-execution";
import { runtimeSafetyPolicyFromEnv } from "./grid-runtime-safety";
import { dryLoopPolicyFromEnv, reconcileFleetWithOptionalDryLoop, summarizeDryLoopTelemetry } from "./grid-runtime-fleet";
import { summarizeFleetRoutes } from "./grid-runtime-graph";
import type { ReconcileResult } from "./grid-reconcile";

/** Server-only scheduled reconciliation driver. */
export async function runScheduledGridReconciliation(env: {
  GOVERNANCE_DB?: D1DatabaseLike;
  GRID_CRON_ENABLED?: string;
  GRID_TESTNET_KILL_SWITCH?: string;
  GRID_SYNC_LEASE_SECONDS?: string;
  GRID_MAX_REPLENISHMENTS_PER_RUN?: string;
  GRID_MAX_CONSECUTIVE_FAILURES?: string;
  GRID_MAX_STATUS_AGE_SECONDS?: string;
  AEGIS_MAX_OPEN_ORDERS?: string;
  GRID_RECONCILE_DRY_LOOP?: string;
  GRID_RECONCILE_DRY_ROUNDS?: string;
  GRID_RECONCILE_MAX_ROUNDS?: string;
}): Promise<{
  enabled: boolean;
  results: Array<ReconcileResult | { botId: string; error: string }>;
  fleet: ReturnType<typeof summarizeFleetRoutes>;
  dryLoop: { enabled: boolean; outcomes: unknown[] };
  telemetry: ReturnType<typeof summarizeDryLoopTelemetry>;
}> {
  if (env.GRID_CRON_ENABLED?.trim() !== "true")
    return {
      enabled: false,
      results: [],
      fleet: summarizeFleetRoutes([]),
      dryLoop: { enabled: false, outcomes: [] },
      telemetry: summarizeDryLoopTelemetry(false, []),
    };
  if (!env.GOVERNANCE_DB)
    throw new Error("Governance storage is unavailable; scheduled reconcile blocked");
  const repo = new GridBotRepository(env.GOVERNANCE_DB);
  const fleet = await reconcileFleetWithOptionalDryLoop(
    repo,
    "system:grid-cron",
    { getStatus: getBinanceTestnetGridStatus, placeOrder: placeSingleTestnetOrder },
    runtimeSafetyPolicyFromEnv(env),
    dryLoopPolicyFromEnv(env),
  );
  return { enabled: true, ...fleet };
}
