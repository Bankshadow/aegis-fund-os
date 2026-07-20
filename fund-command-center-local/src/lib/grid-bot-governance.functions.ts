import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { z } from "zod";
import { GridBotRepository, type BotRecord, type D1DatabaseLike } from "./grid-bot-repository";
import { verifyGovernanceChains } from "./grid-bot-governance";
import {
  cancelTestnetOrder,
  OrphanedTestnetOrdersError,
  placeSingleTestnetOrder,
  placeTestnetGrid,
} from "./binance-testnet-execution";
import { projectGridCycleProfit, projectedGridProfitTotal } from "./grid-profit";
import { getBinanceTestnetGridStatus } from "./binance-testnet.server";
import {
  reconcileAllRunningTestnetGrids,
  reconcileOneTestnetGrid,
  type ReconcileDeps,
} from "./grid-reconcile";
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
  const fromProcess = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
    ?.AEGIS_PUBLIC_TEST_MODE;
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
  const proc = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  const merged: Record<string, string | undefined> = {};
  for (const key of GUARD_ENV_KEYS) merged[key] = binding?.[key] ?? global?.[key] ?? proc?.[key];
  return merged;
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
  assertOrderPlacementAllowed({ openOrders: await repo.countOpenTestnetOrders(), incoming }, limits);
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
      if (orphaned.length > 0) throw new OrphanedTestnetOrdersError(error, orphaned);
      throw error;
    }
  });

export const getGridBotGovernance = createServerFn({ method: "GET" }).handler(async () => {
  const repo = repository();
  const [bots, events, orders] = await Promise.all([repo.listBots(), repo.listEvents(), repo.listAllOrders()]);
  const profitByBot = Object.fromEntries(
    bots.map((bot) => {
      const projections = orders.filter((order) => order.botId === bot.id).map((order) => projectGridCycleProfit(bot, order));
      return [bot.id, { orderCount: projections.length, estimatedCycleProfit: projectedGridProfitTotal(projections) }];
    }),
  );
  return {
    bots,
    events,
    profitByBot,
    auditValid: await verifyGovernanceChains(events),
    publicTestMode: publicTestMode(getRequest()),
  };
});

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
    const [ledgerOrders, remote] = await Promise.all([repo.listOrders(bot.id), getBinanceTestnetGridStatus("BTCUSDT")]);
    const ledgerClientIds = new Set(ledgerOrders.map((order) => order.clientOrderId));
    const ledgerExchangeIds = new Set(ledgerOrders.map((order) => order.exchangeOrderId));
    const matchingOpenOrders = remote.openOrders.filter((order) => ledgerClientIds.has(order.clientOrderId));
    const matchingTrades = remote.trades.filter((trade) => ledgerExchangeIds.has(String(trade.orderId)));
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
    const existing = await repo.listOrders(bot.id);
    if (existing.length) throw new Error("This bot already has a Testnet execution ledger; duplicate start blocked");
    await assertPlacementAllowed(repo, plannedOrderCount(bot.configuration));
    const placed = await placeTestnetGrid(bot);
    try {
      return await repo.recordTestnetStart(bot.id, actorId, placed);
    } catch (error) {
      const outcomes = await Promise.allSettled(
        placed.map((order) => cancelTestnetOrder(bot.pair, order.clientOrderId)),
      );
      const orphaned = placed.filter((_, index) => outcomes[index].status === "rejected");
      if (orphaned.length > 0) throw new OrphanedTestnetOrdersError(error, orphaned);
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
const testnetReconcileDeps: ReconcileDeps = {
  getStatus: getBinanceTestnetGridStatus,
  placeOrder: placeSingleTestnetOrder,
};

export const syncBinanceTestnetGridBot = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot) throw new Error("Binance Spot Testnet bot not found");
    return reconcileOneTestnetGrid(repo, bot, actorId, testnetReconcileDeps);
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
    return { results: await reconcileAllRunningTestnetGrids(repo, actorId, testnetReconcileDeps) };
  });

/**
 * Scheduled (cron) driver. Fail-closed behind `GRID_CRON_ENABLED`: the wrangler
 * cron trigger fires unconditionally, but this returns a no-op unless the
 * operator has explicitly enabled the automatic loop, so deploying the trigger
 * never turns on autonomous trading by itself. Runs under a distinct system
 * actor so its audit events can never be mistaken for a human operator's.
 */
export async function runScheduledGridReconciliation(env: {
  GOVERNANCE_DB?: D1DatabaseLike;
  GRID_CRON_ENABLED?: string;
}): Promise<{ enabled: boolean; results: Awaited<ReturnType<typeof reconcileAllRunningTestnetGrids>> }> {
  if (env.GRID_CRON_ENABLED?.trim() !== "true") return { enabled: false, results: [] };
  if (!env.GOVERNANCE_DB) throw new Error("Governance storage is unavailable; scheduled reconcile blocked");
  const repo = new GridBotRepository(env.GOVERNANCE_DB);
  const results = await reconcileAllRunningTestnetGrids(repo, "system:grid-cron", testnetReconcileDeps);
  return { enabled: true, results };
}

export const stopBinanceTestnetGridBot = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot || bot.environment !== "BINANCE_TESTNET") throw new Error("Binance Testnet bot not found");
    const orders = await repo.listOrders(bot.id);
    const statuses = new Map<string, string>();
    for (const order of orders.filter((item) => item.status === "NEW" || item.status === "PARTIALLY_FILLED")) {
      const cancelled = await cancelTestnetOrder(bot.pair, order.clientOrderId);
      statuses.set(order.clientOrderId, cancelled.status ?? "CANCELED");
    }
    return repo.recordTestnetStop(bot.id, actorId, statuses);
  });
