/**
 * Opt-in dry-loop + fleet driver for Testnet reconciliation.
 *
 * Default remains one pass per bot. When GRID_RECONCILE_DRY_LOOP=true, each bot
 * may take additional safe passes until deferred work drains or a hard cap /
 * operator-review stop fires. Never imports agent/LLM modules.
 */
import type { BotRecord, GridBotRepository } from "./grid-bot-repository.ts";
import type { ReconcileDeps, ReconcileResult } from "./grid-reconcile.ts";
import {
  shouldContinueReconcileLoop,
  summarizeFleetRoutes,
  type FleetGraphSummary,
  type ReconcileRoute,
} from "./grid-runtime-graph.ts";
import {
  reconcileTestnetGridSafely,
  type RuntimeSafetyPolicy,
} from "./grid-runtime-safety.ts";

export type DryLoopPolicy = {
  enabled: boolean;
  dryRounds: number;
  maxRounds: number;
};

export type DryLoopOutcome = {
  botId: string;
  result?: ReconcileResult;
  error?: string;
  rounds: number;
  stopReason: string;
  history: ReconcileRoute[];
};

/** Compact measurement rollup for an opt-in dry-loop window (no placement authority). */
export type DryLoopTelemetry = {
  enabled: boolean;
  bots: number;
  totalPasses: number;
  avgPassesPerBot: number;
  maxPasses: number;
  stopReasons: Record<string, number>;
  deferredEnds: number;
  mismatchOrErrorEnds: number;
  drainedEnds: number;
  /** True when any bot hit the round cap while still deferred — raise budget before raising maxRounds. */
  backlogStillDeferred: boolean;
};

export type FleetDryLoopResult = {
  results: Array<ReconcileResult | { botId: string; error: string }>;
  fleet: FleetGraphSummary;
  dryLoop: { enabled: boolean; outcomes: DryLoopOutcome[] };
  telemetry: DryLoopTelemetry;
};

const DEFAULT_DRY_ROUNDS = 1;
const DEFAULT_MAX_ROUNDS = 3;
const HARD_MAX_ROUNDS = 5;

export function dryLoopPolicyFromEnv(env: {
  GRID_RECONCILE_DRY_LOOP?: string;
  GRID_RECONCILE_DRY_ROUNDS?: string;
  GRID_RECONCILE_MAX_ROUNDS?: string;
}): DryLoopPolicy {
  const dryRounds = Number(env.GRID_RECONCILE_DRY_ROUNDS);
  const maxRounds = Number(env.GRID_RECONCILE_MAX_ROUNDS);
  return {
    enabled: env.GRID_RECONCILE_DRY_LOOP?.trim() === "true",
    dryRounds:
      Number.isInteger(dryRounds) && dryRounds > 0 ? Math.min(dryRounds, HARD_MAX_ROUNDS) : DEFAULT_DRY_ROUNDS,
    maxRounds:
      Number.isInteger(maxRounds) && maxRounds > 0
        ? Math.min(maxRounds, HARD_MAX_ROUNDS)
        : DEFAULT_MAX_ROUNDS,
  };
}

export function summarizeDryLoopTelemetry(
  enabled: boolean,
  outcomes: readonly DryLoopOutcome[],
): DryLoopTelemetry {
  const stopReasons: Record<string, number> = {};
  let totalPasses = 0;
  let maxPasses = 0;
  let deferredEnds = 0;
  let mismatchOrErrorEnds = 0;
  let drainedEnds = 0;
  let backlogStillDeferred = false;
  for (const outcome of outcomes) {
    totalPasses += outcome.rounds;
    if (outcome.rounds > maxPasses) maxPasses = outcome.rounds;
    stopReasons[outcome.stopReason] = (stopReasons[outcome.stopReason] ?? 0) + 1;
    const last = outcome.history.at(-1);
    if (last?.severity === "deferred") {
      deferredEnds += 1;
      if (outcome.stopReason === "max_rounds") backlogStillDeferred = true;
    } else if (last?.severity === "mismatch" || last?.severity === "error" || outcome.error) {
      mismatchOrErrorEnds += 1;
    } else if (last && !last.workRemaining) {
      drainedEnds += 1;
    }
  }
  return {
    enabled,
    bots: outcomes.length,
    totalPasses,
    avgPassesPerBot: outcomes.length ? Number((totalPasses / outcomes.length).toFixed(2)) : 0,
    maxPasses,
    stopReasons,
    deferredEnds,
    mismatchOrErrorEnds,
    drainedEnds,
    backlogStillDeferred,
  };
}

/**
 * Run one bot through optional loop-until-dry. Each iteration uses the full
 * safety wrapper (lease + durable run row), so concurrent callers still fail closed.
 */
export async function reconcileBotWithOptionalDryLoop(
  repo: GridBotRepository,
  bot: BotRecord,
  actorId: string,
  deps: ReconcileDeps,
  safety: RuntimeSafetyPolicy,
  dryLoop: DryLoopPolicy,
): Promise<DryLoopOutcome> {
  if (!dryLoop.enabled) {
    try {
      const result = await reconcileTestnetGridSafely(repo, bot, actorId, deps, safety);
      return {
        botId: bot.id,
        result,
        rounds: 1,
        stopReason: "single_pass",
        history: [result.route],
      };
    } catch (error) {
      return {
        botId: bot.id,
        error: error instanceof Error ? error.message : String(error),
        rounds: 1,
        stopReason: "error",
        history: [{ severity: "error", action: "operator_review", workRemaining: true }],
      };
    }
  }

  const history: ReconcileRoute[] = [];
  let last: ReconcileResult | undefined;
  let stopReason = "max_rounds";
  const maxRounds = Math.min(Math.max(dryLoop.maxRounds, 1), HARD_MAX_ROUNDS);
  const dryRounds = Math.min(Math.max(dryLoop.dryRounds, 1), HARD_MAX_ROUNDS);

  for (let round = 0; round < maxRounds; round += 1) {
    try {
      last = await reconcileTestnetGridSafely(repo, bot, actorId, deps, safety);
      history.push(last.route);
      const decision = shouldContinueReconcileLoop(history, { dryRounds, maxRounds });
      if (!decision.continue) {
        stopReason = decision.reason;
        break;
      }
    } catch (error) {
      history.push({ severity: "error", action: "operator_review", workRemaining: true });
      return {
        botId: bot.id,
        error: error instanceof Error ? error.message : String(error),
        rounds: history.length,
        stopReason: "error",
        history,
      };
    }
  }

  return {
    botId: bot.id,
    result: last,
    rounds: history.length,
    stopReason,
    history,
  };
}

export async function reconcileFleetWithOptionalDryLoop(
  repo: GridBotRepository,
  actorId: string,
  deps: ReconcileDeps,
  safety: RuntimeSafetyPolicy,
  dryLoop: DryLoopPolicy,
  bots?: BotRecord[],
): Promise<FleetDryLoopResult> {
  const all = bots ?? (await repo.listBots());
  const running = all.filter(
    (bot) => bot.environment === "BINANCE_TESTNET" && bot.pair === "BTCUSDT" && bot.runtimeState === "RUNNING",
  );
  const outcomes = await Promise.all(
    running.map((bot) => reconcileBotWithOptionalDryLoop(repo, bot, actorId, deps, safety, dryLoop)),
  );
  const results = outcomes.map((outcome) =>
    outcome.result
      ? outcome.result
      : { botId: outcome.botId, error: outcome.error ?? "reconcile failed" },
  );
  return {
    results,
    fleet: summarizeFleetRoutes(results),
    dryLoop: { enabled: dryLoop.enabled, outcomes },
    telemetry: summarizeDryLoopTelemetry(dryLoop.enabled, outcomes),
  };
}
