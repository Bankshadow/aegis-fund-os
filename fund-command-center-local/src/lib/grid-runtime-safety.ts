import type { BotRecord, GridBotRepository } from "./grid-bot-repository.ts";
import type { ReconcileDeps, ReconcileResult } from "./grid-reconcile.ts";
import { reconcileOneTestnetGrid } from "./grid-reconcile.ts";
import { classifyReconcileRoute } from "./grid-runtime-graph.ts";

export type RuntimeSafetyPolicy = {
  /** Environment kill switch. Any value other than false blocks placement. */
  killSwitch?: boolean;
  leaseSeconds?: number;
  maxPlacementsPerRun?: number;
  maxConsecutiveFailures?: number;
  maxStatusAgeSeconds?: number;
  maxOpenOrders?: number;
};

export class GridRuntimeSafetyError extends Error {}

/** Shared preflight for every Testnet order-placement entrypoint, including initial grid starts. */
export const assertTestnetPlacementEnabled = (policy: RuntimeSafetyPolicy) => {
  if (policy.killSwitch)
    throw new GridRuntimeSafetyError("Testnet placement is disabled by the global kill switch");
};

const defaults = {
  leaseSeconds: 120,
  maxPlacementsPerRun: 8,
  maxConsecutiveFailures: 3,
  maxStatusAgeSeconds: 30,
  maxOpenOrders: 250,
};

/**
 * Schema-drift guard for the safety tables (migration 0006/0007).
 *
 * The 0005 incident showed how this fails in production: the deploy workflow's
 * migration step is skippable, so code can ship against a database without its
 * tables. Here the consequence is worse than a missing column — the lease, the
 * run ledger and the breaker counter all live in those tables, so every reconcile
 * would die on a raw `D1_ERROR: no such table` that names nothing actionable.
 *
 * Degrading is NOT an option: placing orders without a lease is exactly what the
 * lease exists to prevent. So this stays fail-closed and only improves the
 * diagnosis. It is deliberately raised before the durable run is created, so a
 * pending migration never burns the consecutive-failure budget and halts a fleet
 * of healthy bots for what is a deployment problem.
 */
const SAFETY_TABLES = ["grid_runtime_controls", "grid_runtime_leases", "grid_runtime_runs"];

export const isMissingSafetyTableError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  return /no such table/i.test(message) && SAFETY_TABLES.some((table) => message.includes(table));
};

const withStorageDiagnosis = async <T>(operation: () => Promise<T>): Promise<T> => {
  try {
    return await operation();
  } catch (error) {
    if (isMissingSafetyTableError(error))
      throw new GridRuntimeSafetyError(
        "Runtime safety storage is missing; placement blocked. Apply the pending D1 migrations " +
          "(wrangler d1 migrations apply GOVERNANCE_DB --remote) before enabling the grid loop.",
      );
    throw error;
  }
};

const positive = (candidate: number | undefined, fallback: number) =>
  Number.isInteger(candidate) && candidate! > 0 ? candidate! : fallback;

const nonNegative = (candidate: number | undefined, fallback: number) =>
  Number.isInteger(candidate) && candidate! >= 0 ? candidate! : fallback;

/**
 * Safety wrapper around the pure reconciliation core. It is deliberately the
 * only production entrypoint: a D1 compare-and-set lease precedes every
 * exchange placement, and every attempted run gets a durable outcome record.
 */
export async function reconcileTestnetGridSafely(
  repo: GridBotRepository,
  bot: BotRecord,
  actorId: string,
  deps: ReconcileDeps,
  policy: RuntimeSafetyPolicy = {},
): Promise<ReconcileResult> {
  assertTestnetPlacementEnabled(policy);
  const perBot = await withStorageDiagnosis(() => repo.getRuntimeSafetyControl(`BOT:${bot.id}`));
  if (perBot.placementDisabled)
    throw new GridRuntimeSafetyError(`Testnet placement is disabled for this bot: ${perBot.reason ?? "safety halt"}`);

  const now = new Date();
  const holder = `${actorId}:${crypto.randomUUID()}`;
  const leaseSeconds = positive(policy.leaseSeconds, defaults.leaseSeconds);
  const acquired = await withStorageDiagnosis(() =>
    repo.acquireRuntimeLease(
      bot.id,
      holder,
      new Date(now.getTime() + leaseSeconds * 1_000).toISOString(),
      now.toISOString(),
    ),
  );
  if (!acquired) throw new GridRuntimeSafetyError("Grid reconciliation already holds an active lease");

  // The lease is already held here, so a failure to open the run record must release
  // it explicitly — the try/finally below only starts once `runId` exists, and a
  // leaked lease would block every reconcile for this bot until it expired.
  let runId: string;
  try {
    runId = await withStorageDiagnosis(() => repo.startRuntimeRun(bot.id, actorId, holder, now.toISOString()));
  } catch (error) {
    await repo.releaseRuntimeLease(bot.id, holder);
    throw error;
  }
  try {
    const maxStatusAgeSeconds = positive(policy.maxStatusAgeSeconds, defaults.maxStatusAgeSeconds);
    const maxOpenOrders = positive(policy.maxOpenOrders, defaults.maxOpenOrders);
    const status = await deps.getStatus("BTCUSDT");
    const checkedAt = Date.parse(status.checkedAt ?? "");
    const evidenceAge = Date.now() - checkedAt;
    if (!Number.isFinite(checkedAt) || evidenceAge < 0 || evidenceAge > maxStatusAgeSeconds * 1_000)
      throw new GridRuntimeSafetyError("Exchange status evidence is stale or invalid; placement blocked");
    const result = await reconcileOneTestnetGrid(repo, bot, actorId, {
      ...deps,
      getStatus: async () => status,
      beforePlace: async (alreadyPlaced) => {
        const renewalNow = new Date();
        const renewed = await repo.renewRuntimeLease(
          bot.id, holder, new Date(renewalNow.getTime() + leaseSeconds * 1_000).toISOString(), renewalNow.toISOString(),
        );
        if (!renewed) throw new GridRuntimeSafetyError("Grid reconciliation lease expired before placement");
        const openOrders = await repo.countOpenTestnetOrders();
        if (openOrders + alreadyPlaced >= maxOpenOrders)
          throw new GridRuntimeSafetyError(`Open-order safety cap reached: ${openOrders + alreadyPlaced} >= ${maxOpenOrders}`);
      },
    }, {
      maxPlacements: nonNegative(policy.maxPlacementsPerRun, defaults.maxPlacementsPerRun),
    });
    await repo.recordRuntimeSafety(bot.id, actorId, { failed: false, threshold: positive(policy.maxConsecutiveFailures, defaults.maxConsecutiveFailures) });
    await repo.finishRuntimeRun(
      runId,
      "SUCCEEDED",
      null,
      result.summary.placed,
      result.route,
      result.summary.deferred,
    );
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await repo.recordRuntimeSafety(bot.id, actorId, {
      failed: true,
      threshold: positive(policy.maxConsecutiveFailures, defaults.maxConsecutiveFailures),
      reason: message,
    });
    await repo.finishRuntimeRun(
      runId,
      "FAILED",
      message.slice(0, 500),
      0,
      classifyReconcileRoute(
        { filled: 0, placed: 0, statusUpdated: 0, reconciliationRequired: 0, deferred: 0 },
        true,
      ),
      0,
    );
    throw error;
  } finally {
    await repo.releaseRuntimeLease(bot.id, holder);
  }
}

export type RuntimeSafetyEnv = {
  GRID_TESTNET_KILL_SWITCH?: string;
  GRID_SYNC_LEASE_SECONDS?: string;
  GRID_MAX_REPLENISHMENTS_PER_RUN?: string;
  GRID_MAX_CONSECUTIVE_FAILURES?: string;
  GRID_MAX_STATUS_AGE_SECONDS?: string;
  AEGIS_MAX_OPEN_ORDERS?: string;
};

export const runtimeSafetyPolicyFromEnv = (env: RuntimeSafetyEnv): RuntimeSafetyPolicy => ({
  // Exact opt-in is intentional: unset/invalid means safe (placements allowed
  // only because the existing Testnet execution path is otherwise authorized).
  killSwitch: env.GRID_TESTNET_KILL_SWITCH?.trim() === "true",
  leaseSeconds: Number(env.GRID_SYNC_LEASE_SECONDS),
  maxPlacementsPerRun: Number(env.GRID_MAX_REPLENISHMENTS_PER_RUN),
  maxConsecutiveFailures: Number(env.GRID_MAX_CONSECUTIVE_FAILURES),
  maxStatusAgeSeconds: Number(env.GRID_MAX_STATUS_AGE_SECONDS),
  maxOpenOrders: Number(env.AEGIS_MAX_OPEN_ORDERS),
});
