import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { z } from "zod";
import { GridBotRepository, type BotRecord, type D1DatabaseLike } from "./grid-bot-repository";
import { verifyGovernanceChains } from "./grid-bot-governance";
import { projectGridCycleProfit, projectedGridProfitTotal } from "./grid-profit";
import {
  cancelTestnetOrder,
  OrphanedTestnetOrdersError,
  placeSingleTestnetOrder,
  placeTestnetGrid,
} from "./binance-testnet-execution";
import { getBinanceTestnetGridStatus } from "./binance-testnet.server";
import { assertTestnetPlacementEnabled, reconcileTestnetGridSafely, runtimeSafetyPolicyFromEnv } from "./grid-runtime-safety";
import { dryLoopPolicyFromEnv, reconcileFleetWithOptionalDryLoop } from "./grid-runtime-fleet";
import { resolveActorIdentity } from "./actor-identity";
import {
  assertBotCreationAllowed,
  assertOrderPlacementAllowed,
  resolveGuardLimits,
  windowStart,
} from "./abuse-guards";

type CloudflareRequest = Request & {
  runtime?: {
    cloudflare?: { env?: { GOVERNANCE_DB?: D1DatabaseLike; AEGIS_PUBLIC_TEST_MODE?: string } };
  };
};

const runtimeEnv = (request: Request) => (request as CloudflareRequest).runtime?.cloudflare?.env;

const repository = () => {
  const db = runtimeEnv(getRequest())?.GOVERNANCE_DB;
  if (!db) throw new Error("Governance storage is unavailable; mutation blocked");
  return new GridBotRepository(db);
};

const publicTestMode = (request: Request) => {
  const fromBinding = runtimeEnv(request)?.AEGIS_PUBLIC_TEST_MODE;
  // The Cloudflare preset mirrors bindings/secrets onto globalThis.__env__ on
  // every invocation; this is where wrangler's .dev.vars land in dev.
  const fromGlobal = (globalThis as { __env__?: Record<string, string | undefined> }).__env__
    ?.AEGIS_PUBLIC_TEST_MODE;
  const fromProcess = (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env?.AEGIS_PUBLIC_TEST_MODE;
  return (fromBinding ?? fromGlobal ?? fromProcess)?.trim() === "true";
};

const GUARD_ENV_KEYS = [
  "AEGIS_MAX_BOTS",
  "AEGIS_MAX_CREATES_PER_WINDOW",
  "AEGIS_CREATE_WINDOW_MINUTES",
  "AEGIS_MAX_OPEN_ORDERS",
] as const;

const guardEnv = (request: Request) => {
  const binding = runtimeEnv(request) as Record<string, string | undefined> | undefined;
  const global = (globalThis as { __env__?: Record<string, string | undefined> }).__env__;
  const proc = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process
    ?.env;
  const merged: Record<string, string | undefined> = {};
  for (const key of GUARD_ENV_KEYS) merged[key] = binding?.[key] ?? global?.[key] ?? proc?.[key];
  return merged;
};

const runtimeSafetyEnv = (request: Request) => {
  const binding = runtimeEnv(request) as Record<string, string | undefined> | undefined;
  const global = (globalThis as { __env__?: Record<string, string | undefined> }).__env__;
  const proc = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  const keys = [
    "GRID_TESTNET_KILL_SWITCH",
    "GRID_SYNC_LEASE_SECONDS",
    "GRID_MAX_REPLENISHMENTS_PER_RUN",
    "GRID_MAX_CONSECUTIVE_FAILURES",
    "GRID_MAX_STATUS_AGE_SECONDS",
    "AEGIS_MAX_OPEN_ORDERS",
    "GRID_RECONCILE_DRY_LOOP",
    "GRID_RECONCILE_DRY_ROUNDS",
    "GRID_RECONCILE_MAX_ROUNDS",
  ];
  return Object.fromEntries(keys.map((key) => [key, binding?.[key] ?? global?.[key] ?? proc?.[key]]));
};

/** Reject before any durable write when creation would cross a public-deployment cap. */
const assertCreateAllowed = async (repo: GridBotRepository) => {
  const limits = resolveGuardLimits(guardEnv(getRequest()));
  const [totalBots, recentCreates] = await Promise.all([
    repo.countBots(),
    repo.countBotsCreatedSince(windowStart(limits)),
  ]);
  assertBotCreationAllowed({ totalBots, recentCreates }, limits);
};

/** Reject before any exchange call when a grid would cross the open-order cap. */
const assertPlacementAllowed = async (repo: GridBotRepository, incoming: number) => {
  const limits = resolveGuardLimits(guardEnv(getRequest()));
  assertOrderPlacementAllowed(
    { openOrders: await repo.countOpenTestnetOrders(), incoming },
    limits,
  );
};

const plannedOrderCount = (configuration: BotRecord["configuration"]) => {
  const grids = Number(configuration.grids);
  return Number.isFinite(grids) && grids > 0 ? grids : 0;
};

const actorIdentity = (localClaim?: string) => {
  const request = getRequest();
  return resolveActorIdentity({
    accessEmail: request.headers.get("cf-access-authenticated-user-email"),
    accessJwt: request.headers.get("cf-access-jwt-assertion"),
    hostname: new URL(request.url).hostname,
    localClaim,
    publicTestMode: publicTestMode(request),
  });
};

const createSchema = z.object({
  name: z.string().trim().min(1).max(120),
  environment: z.enum(["DEMO", "PAPER", "BINANCE_TESTNET"]),
  pair: z.string().regex(/^[A-Z0-9]{5,20}$/),
  makerId: z.string().trim().min(1).max(120),
  idempotencyKey: z.string().uuid(),
  configuration: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])),
  // Creation always enters the independent maker-checker queue. Keep accepting
  // the legacy field for compatible clients, but never let it create a DRAFT.
  submit: z.boolean().optional(),
});

export const createGovernedGridBot = createServerFn({ method: "POST" })
  .validator(createSchema)
  .handler(async ({ data }) => {
    const repo = repository();
    const makerId = actorIdentity(data.makerId);
    await assertCreateAllowed(repo);
    const bot = await repo.createDraft(
      {
        name: data.name,
        environment: data.environment,
        pair: data.pair,
        makerId,
        configuration: data.configuration,
      },
      data.idempotencyKey,
    );
    return bot.state === "DRAFT" ? repo.submit(bot.id, makerId) : bot;
  });

export const createAndStartTestnetGridBot = createServerFn({ method: "POST" })
  .validator(createSchema)
  .handler(async ({ data }) => {
    if (data.environment !== "BINANCE_TESTNET")
      throw new Error("One-click execution is restricted to Binance Spot Testnet");
    const repo = repository();
    const makerId = actorIdentity(data.makerId);
    assertTestnetPlacementEnabled(runtimeSafetyPolicyFromEnv(runtimeSafetyEnv(getRequest())));
    await assertCreateAllowed(repo);
    await assertPlacementAllowed(repo, plannedOrderCount(data.configuration));
    const draft = await repo.createDraft(
      {
        name: data.name,
        environment: data.environment,
        pair: data.pair,
        makerId,
        configuration: data.configuration,
      },
      data.idempotencyKey,
    );
    const approved = draft.state === "DRAFT" ? await repo.autoApproveTestnet(draft.id) : draft;
    if (approved.state !== "APPROVED") throw new Error("Testnet bot is not eligible to start");
    const placed = await placeTestnetGrid(approved);
    try {
      return await repo.recordTestnetStart(approved.id, makerId, placed);
    } catch (error) {
      const outcomes = await Promise.allSettled(
        placed.map((order) => cancelTestnetOrder(approved.pair, order.clientOrderId)),
      );
      const orphaned = placed.filter((_, index) => outcomes[index].status === "rejected");
      if (orphaned.length > 0) {
        throw new OrphanedTestnetOrdersError(error, orphaned);
      }
      throw error;
    }
  });

export const getGridBotGovernance = createServerFn({ method: "GET" }).handler(async () => {
  const repo = repository();
  const [bots, events, orders, recentRuntimeRuns] = await Promise.all([
    repo.listBots(),
    repo.listEvents(),
    repo.listAllOrders(),
    repo.listRecentRuntimeRuns(),
  ]);
  const profitByBot = Object.fromEntries(
    bots.map((bot) => {
      const projections = orders
        .filter((order) => order.botId === bot.id)
        .map((order) => projectGridCycleProfit(bot, order));
      return [
        bot.id,
        {
          orderCount: projections.length,
          estimatedCycleProfit: projectedGridProfitTotal(projections),
        },
      ];
    }),
  );
  const runtimeSafetyByBot = Object.fromEntries(
    await Promise.all(bots.map(async (bot) => [bot.id, await repo.getRuntimeSafetyControl(`BOT:${bot.id}`)] as const)),
  );
  return {
    bots,
    events,
    profitByBot,
    auditValid: await verifyGovernanceChains(events),
    recentRuntimeRuns,
    runtimeSafetyByBot,
    publicTestMode: publicTestMode(getRequest()),
  };
});

/** Clears only an automatic per-bot breaker; the bot remains PAUSED until separately resumed. */
export const clearGridBotSafetyHalt = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional(), reason: z.string().trim().min(3).max(500) }))
  .handler(({ data }) => repository().clearRuntimeSafetyHalt(data.botId, actorIdentity(data.actorId), data.reason));

export const getGridBotOrders = createServerFn({ method: "GET" })
  .validator(z.object({ botId: z.string().min(1) }))
  .handler(({ data }) => repository().listOrders(data.botId));

export const getGridBotTestnetStatus = createServerFn({ method: "GET" })
  .validator(z.object({ botId: z.string().min(1) }))
  .handler(async ({ data }) => {
    const repo = repository();
    const bot = await repo.getBot(data.botId);
    if (!bot || bot.environment !== "BINANCE_TESTNET" || bot.pair !== "BTCUSDT")
      throw new Error("Binance Spot Testnet bot not found");
    const [ledgerOrders, remote] = await Promise.all([
      repo.listOrders(bot.id),
      getBinanceTestnetGridStatus("BTCUSDT"),
    ]);
    const ledgerClientIds = new Set(ledgerOrders.map((order) => order.clientOrderId));
    const ledgerExchangeIds = new Set(ledgerOrders.map((order) => order.exchangeOrderId));
    const matchingOpenOrders = remote.openOrders.filter((order) =>
      ledgerClientIds.has(order.clientOrderId),
    );
    const matchingTrades = remote.trades.filter((trade) =>
      ledgerExchangeIds.has(String(trade.orderId)),
    );
    return {
      checkedAt: remote.checkedAt,
      ledgerOrderCount: ledgerOrders.length,
      matchingOpenOrderCount: matchingOpenOrders.length,
      matchingTradeCount: matchingTrades.length,
      realizedPnl: matchingTrades.length === 0 ? "0.0000" : null,
      reconciliationRequired: matchingTrades.length > 0,
    };
  });

export const decideGridBotApproval = createServerFn({ method: "POST" })
  .validator(
    z.object({
      botId: z.string().min(1),
      checkerId: z.string().trim().min(1),
      decision: z.enum(["APPROVED", "REJECTED"]),
      reason: z.string().trim().min(3).max(500),
    }),
  )
  .handler(({ data }) =>
    repository().decide(data.botId, actorIdentity(data.checkerId), data.decision, data.reason),
  );

export const transitionGridBotRuntime = createServerFn({ method: "POST" })
  .validator(
    z.object({
      botId: z.string().min(1),
      actorId: z.string().trim().min(1).optional(),
      nextState: z.enum(["RUNNING", "PAUSED", "STOPPED"]),
    }),
  )
  .handler(({ data }) =>
    repository().transitionRuntime(data.botId, actorIdentity(data.actorId), data.nextState),
  );

export const startBinanceTestnetGridBot = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot) throw new Error("Bot not found");
    assertTestnetPlacementEnabled(runtimeSafetyPolicyFromEnv(runtimeSafetyEnv(getRequest())));
    const existing = await repo.listOrders(bot.id);
    if (existing.length)
      throw new Error("This bot already has a Testnet execution ledger; duplicate start blocked");
    await assertPlacementAllowed(repo, plannedOrderCount(bot.configuration));
    const placed = await placeTestnetGrid(bot);
    try {
      return await repo.recordTestnetStart(bot.id, actorId, placed);
    } catch (error) {
      const outcomes = await Promise.allSettled(
        placed.map((order) => cancelTestnetOrder(bot.pair, order.clientOrderId)),
      );
      const orphaned = placed.filter((_, index) => outcomes[index].status === "rejected");
      if (orphaned.length > 0) {
        throw new OrphanedTestnetOrdersError(error, orphaned);
      }
      throw error;
    }
  });

/**
 * One iteration of the grid runtime loop: poll the exchange, mark filled and
 * externally-cancelled ledger orders, and place the paired replenishment order
 * for each fill so the grid keeps cycling. Restricted to a RUNNING Binance Spot
 * Testnet BTCUSDT bot and fail-closed on identity. A replenishment placement
 * that fails leaves its source fill un-terminal so the next poll retries it,
 * and the error is surfaced only after the ledger is made consistent.
 */
export const syncBinanceTestnetGridBot = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot) throw new Error("Binance Spot Testnet bot not found");
    return reconcileTestnetGridSafely(repo, bot, actorId, {
      getStatus: getBinanceTestnetGridStatus,
      placeOrder: placeSingleTestnetOrder,
    }, runtimeSafetyPolicyFromEnv(runtimeSafetyEnv(getRequest())));
  });

/**
 * Reconcile every RUNNING Binance Spot Testnet bot in one call. This is the
 * human-triggered "sync all" and the same code the cron driver runs. Fail-closed
 * on identity; one bot failing is isolated and reported, never aborting others.
 */
export const syncAllRunningTestnetGrids = createServerFn({ method: "POST" })
  .validator(z.object({ actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const env = runtimeSafetyEnv(getRequest());
    return reconcileFleetWithOptionalDryLoop(
      repo,
      actorId,
      { getStatus: getBinanceTestnetGridStatus, placeOrder: placeSingleTestnetOrder },
      runtimeSafetyPolicyFromEnv(env),
      dryLoopPolicyFromEnv(env),
    );
  });

/**
 * Operator control to cancel a single stuck Testnet order and close its ledger row.
 * Covers the case that previously needed a manual script: a stray order still open
 * on the exchange, or one the reconciler flagged RECONCILIATION_REQUIRED because its
 * exchange twin was cancelled out of band.
 *
 * The exchange cancel is attempted first. If Binance reports the order is already
 * gone (-2011 unknown order / -2013 no such order), that is treated as success —
 * the whole point is to reconcile a ledger row whose exchange side no longer exists
 * — and the ledger is still closed to CANCELED. Any other exchange error fails
 * closed and the ledger is left untouched.
 */
const ALREADY_GONE = /(-2011|-2013|Unknown order|No such order)/i;

export const cancelTestnetGridOrder = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), clientOrderId: z.string().trim().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot || bot.environment !== "BINANCE_TESTNET") throw new Error("Binance Testnet bot not found");
    const order = (await repo.listOrders(bot.id)).find((item) => item.clientOrderId === data.clientOrderId);
    if (!order) throw new Error("Order not found in the durable ledger");
    if (order.status === "FILLED" || order.status === "CANCELED")
      throw new Error(`Order is already ${order.status}; nothing to cancel`);

    let status = "CANCELED";
    try {
      const cancelled = await cancelTestnetOrder(bot.pair, order.clientOrderId);
      status = cancelled.status ?? "CANCELED";
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!ALREADY_GONE.test(message)) throw error; // real exchange error: leave the ledger untouched
      status = "CANCELED"; // already off the book — reconcile the ledger to match
    }
    return repo.recordSingleTestnetOrderCancel(bot.id, actorId, order.clientOrderId, status);
  });

export const stopBinanceTestnetGridBot = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot || bot.environment !== "BINANCE_TESTNET")
      throw new Error("Binance Testnet bot not found");
    const orders = await repo.listOrders(bot.id);
    const statuses = new Map<string, string>();
    for (const order of orders.filter(
      (item) => item.status === "NEW" || item.status === "PARTIALLY_FILLED",
    )) {
      const cancelled = await cancelTestnetOrder(bot.pair, order.clientOrderId);
      statuses.set(order.clientOrderId, cancelled.status ?? "CANCELED");
    }
    return repo.recordTestnetStop(bot.id, actorId, statuses);
  });
