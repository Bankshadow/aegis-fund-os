/**
 * Resource guards for the login-less public research deployment.
 *
 * With `AEGIS_PUBLIC_TEST_MODE` enabled anyone on the internet can create and
 * start grid bots, so unbounded creation would let a single visitor fill the
 * governance database and spray testnet orders until the account's balance or
 * rate limits give out. These caps are deliberately coarse and fail closed: a
 * request that would cross a limit is rejected before any durable write or
 * exchange call.
 *
 * All limits are counted with plain D1 aggregates over existing tables, so no
 * migration or new state is required, and every threshold is env-overridable.
 */

export type GuardLimits = {
  maxBots: number;
  maxCreatesPerWindow: number;
  windowMinutes: number;
  maxOpenOrders: number;
};

export const DEFAULT_LIMITS: GuardLimits = {
  maxBots: 25,
  maxCreatesPerWindow: 5,
  windowMinutes: 10,
  maxOpenOrders: 120,
};

const positiveInt = (raw: string | undefined, fallback: number) => {
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
};

export function resolveGuardLimits(env: Record<string, string | undefined> | undefined): GuardLimits {
  return {
    maxBots: positiveInt(env?.AEGIS_MAX_BOTS, DEFAULT_LIMITS.maxBots),
    maxCreatesPerWindow: positiveInt(env?.AEGIS_MAX_CREATES_PER_WINDOW, DEFAULT_LIMITS.maxCreatesPerWindow),
    windowMinutes: positiveInt(env?.AEGIS_CREATE_WINDOW_MINUTES, DEFAULT_LIMITS.windowMinutes),
    maxOpenOrders: positiveInt(env?.AEGIS_MAX_OPEN_ORDERS, DEFAULT_LIMITS.maxOpenOrders),
  };
}

/** ISO timestamp marking the start of the current creation window. */
export const windowStart = (limits: GuardLimits, now: Date = new Date()) =>
  new Date(now.getTime() - limits.windowMinutes * 60_000).toISOString();

export function assertBotCreationAllowed(
  counts: { totalBots: number; recentCreates: number },
  limits: GuardLimits,
): void {
  if (counts.totalBots >= limits.maxBots)
    throw new Error(
      `Bot limit reached (${limits.maxBots}). Stop or remove an existing bot before creating another.`,
    );
  if (counts.recentCreates >= limits.maxCreatesPerWindow)
    throw new Error(
      `Too many bots created recently (${limits.maxCreatesPerWindow} per ${limits.windowMinutes} minutes). Try again later.`,
    );
}

export function assertOrderPlacementAllowed(
  counts: { openOrders: number; incoming: number },
  limits: GuardLimits,
): void {
  if (counts.openOrders + counts.incoming > limits.maxOpenOrders)
    throw new Error(
      `Open Testnet order limit reached (${limits.maxOpenOrders}); ${counts.openOrders} are already open. Stop a running bot first.`,
    );
}
