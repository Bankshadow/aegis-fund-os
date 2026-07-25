/**
 * L3 runtime graph helpers — deterministic severity + dry-loop routing.
 *
 * Firewall: never import agent harness, models, or LLM tooling. These helpers
 * classify reconcile outcomes and decide whether another *code* pass is warranted.
 * They do not place orders; callers keep using grid-runtime-safety for placement.
 */

export type ReconcileSummaryLike = {
  filled: number;
  placed: number;
  statusUpdated: number;
  reconciliationRequired: number;
  deferred: number;
};

export type ReconcileSeverity = "ok" | "deferred" | "mismatch" | "error";
export type ReconcileAction = "continue" | "retry_next" | "operator_review";

export type ReconcileRoute = {
  severity: ReconcileSeverity;
  action: ReconcileAction;
  /** True when another reconcile pass may still drain work (deferred/mismatch). */
  workRemaining: boolean;
};

export type FleetGraphSummary = {
  ok: number;
  deferred: number;
  mismatch: number;
  error: number;
  /** Highest severity seen across the batch (error > mismatch > deferred > ok). */
  peakSeverity: ReconcileSeverity;
  action: ReconcileAction;
  workRemaining: boolean;
};

const RANK: Record<ReconcileSeverity, number> = {
  ok: 0,
  deferred: 1,
  mismatch: 2,
  error: 3,
};

/**
 * Classify one reconcile summary. Placement behavior is unchanged by this call —
 * it only names the edge for operators and dry-loop planners.
 */
export function classifyReconcileRoute(
  summary: ReconcileSummaryLike,
  failed = false,
): ReconcileRoute {
  if (failed) {
    return { severity: "error", action: "operator_review", workRemaining: true };
  }
  if (summary.reconciliationRequired > 0) {
    return { severity: "mismatch", action: "operator_review", workRemaining: true };
  }
  if (summary.deferred > 0) {
    return { severity: "deferred", action: "retry_next", workRemaining: true };
  }
  return { severity: "ok", action: "continue", workRemaining: false };
}

export function summarizeFleetRoutes(
  items: Array<{ route?: ReconcileRoute; error?: string }>,
): FleetGraphSummary {
  const tallies = { ok: 0, deferred: 0, mismatch: 0, error: 0 };
  let peak: ReconcileSeverity = "ok";
  for (const item of items) {
    const route =
      item.error !== undefined
        ? classifyReconcileRoute(
            { filled: 0, placed: 0, statusUpdated: 0, reconciliationRequired: 0, deferred: 0 },
            true,
          )
        : item.route ?? classifyReconcileRoute(
            { filled: 0, placed: 0, statusUpdated: 0, reconciliationRequired: 0, deferred: 0 },
          );
    tallies[route.severity] += 1;
    if (RANK[route.severity] > RANK[peak]) peak = route.severity;
  }
  const routed = classifyReconcileRoute(
    {
      filled: 0,
      placed: 0,
      statusUpdated: 0,
      reconciliationRequired: peak === "mismatch" ? 1 : 0,
      deferred: peak === "deferred" ? 1 : 0,
    },
    peak === "error",
  );
  return {
    ...tallies,
    peakSeverity: peak,
    action: routed.action,
    workRemaining: routed.workRemaining || tallies.deferred + tallies.mismatch + tallies.error > 0,
  };
}

/**
 * Loop-until-dry planner for reconcile passes. Dedupes round fingerprints so a
 * repeated identical "still deferred" state counts toward dryness only when the
 * fingerprint changes or work hits zero. Does not invoke exchange I/O.
 */
export function shouldContinueReconcileLoop(
  history: readonly ReconcileRoute[],
  options: { dryRounds?: number; maxRounds?: number } = {},
): { continue: boolean; dryStreak: number; reason: string } {
  const dryRounds = options.dryRounds ?? 2;
  const maxRounds = options.maxRounds ?? 8;
  if (dryRounds < 1 || maxRounds < 1) {
    throw new Error("dryRounds and maxRounds must be >= 1");
  }
  if (history.length >= maxRounds) {
    return { continue: false, dryStreak: 0, reason: "max_rounds" };
  }
  if (history.length === 0) {
    return { continue: true, dryStreak: 0, reason: "first_pass" };
  }
  let dry = 0;
  for (let i = history.length - 1; i >= 0; i -= 1) {
    if (history[i].workRemaining) break;
    dry += 1;
  }
  if (dry >= dryRounds) {
    return { continue: false, dryStreak: dry, reason: "dry" };
  }
  const last = history[history.length - 1];
  if (!last.workRemaining) {
    return { continue: true, dryStreak: dry, reason: "approaching_dry" };
  }
  if (last.severity === "mismatch" || last.severity === "error") {
    return { continue: false, dryStreak: dry, reason: "operator_review" };
  }
  return { continue: true, dryStreak: dry, reason: "work_remaining" };
}
