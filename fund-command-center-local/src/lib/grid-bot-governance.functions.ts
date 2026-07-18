import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { z } from "zod";
import { GridBotRepository, type D1DatabaseLike } from "./grid-bot-repository";
import { verifyGovernanceChains } from "./grid-bot-governance";
import {
  cancelTestnetOrder,
  OrphanedTestnetOrdersError,
  placeSingleTestnetOrder,
  placeTestnetGrid,
} from "./binance-testnet-execution";
import { projectGridCycleProfit, projectedGridProfitTotal } from "./grid-profit";
import { getBinanceTestnetGridStatus } from "./binance-testnet.server";
import { planGridReconciliation } from "./grid-runtime";

type CloudflareRequest = Request & {
  runtime?: { cloudflare?: { env?: { GOVERNANCE_DB?: D1DatabaseLike } } };
};

const repository = () => {
  const db = (getRequest() as CloudflareRequest).runtime?.cloudflare?.env?.GOVERNANCE_DB;
  if (!db) throw new Error("Governance storage is unavailable; mutation blocked");
  return new GridBotRepository(db);
};

const actorIdentity = (localClaim?: string) => {
  const request = getRequest();
  const accessEmail = request.headers.get("cf-access-authenticated-user-email")?.trim();
  const accessJwt = request.headers.get("cf-access-jwt-assertion")?.trim();
  if (accessEmail && accessJwt) return accessEmail.toLowerCase();
  const host = new URL(request.url).hostname;
  if ((host === "127.0.0.1" || host === "localhost") && localClaim?.trim())
    return localClaim.trim().toLowerCase();
  throw new Error("Verified Cloudflare Access identity is required; mutation blocked");
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
  return { bots, events, profitByBot, auditValid: await verifyGovernanceChains(events) };
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
export const syncBinanceTestnetGridBot = createServerFn({ method: "POST" })
  .validator(z.object({ botId: z.string().min(1), actorId: z.string().trim().min(1).optional() }))
  .handler(async ({ data }) => {
    const repo = repository();
    const actorId = actorIdentity(data.actorId);
    const bot = await repo.getBot(data.botId);
    if (!bot || bot.environment !== "BINANCE_TESTNET" || bot.pair !== "BTCUSDT")
      throw new Error("Binance Spot Testnet bot not found");
    if (bot.runtimeState !== "RUNNING") throw new Error("Only a RUNNING bot can reconcile grid fills");

    const [orders, remote] = await Promise.all([
      repo.listOrders(bot.id),
      getBinanceTestnetGridStatus("BTCUSDT"),
    ]);
    const plan = await planGridReconciliation(
      bot.id,
      orders,
      remote.openOrders.map((order) => ({ clientOrderId: order.clientOrderId, status: order.status })),
      remote.trades.map((trade) => ({ exchangeOrderId: String(trade.orderId) })),
    );

    const targetedSources = new Set(plan.replenishments.map((item) => item.sourceClientOrderId));
    const placedSources = new Set<string>();
    const placements: Array<{
      clientOrderId: string; exchangeOrderId: string; side: "BUY" | "SELL";
      price: string; quantity: string; gridIndex: number; status: string;
    }> = [];
    let placementError: unknown = null;
    for (const replenishment of plan.replenishments) {
      try {
        const placed = await placeSingleTestnetOrder(bot.pair, replenishment);
        placements.push({
          clientOrderId: replenishment.clientOrderId,
          exchangeOrderId: String(placed.orderId),
          side: replenishment.side,
          price: replenishment.price,
          quantity: replenishment.quantity,
          gridIndex: replenishment.gridIndex,
          status: placed.status,
        });
        placedSources.add(replenishment.sourceClientOrderId);
      } catch (error) {
        placementError = error;
        break;
      }
    }
    // Commit a fill only if it needs no replenishment (grid boundary) or its
    // replenishment was actually placed; otherwise leave it for the next poll.
    const filled = plan.filled.filter(
      (fill) => !targetedSources.has(fill.clientOrderId) || placedSources.has(fill.clientOrderId),
    );
    const result = await repo.recordGridSync(bot.id, actorId, {
      statusUpdates: plan.statusUpdates,
      filled,
      reconciliationRequired: plan.reconciliationRequired,
      placements,
    });
    if (placementError) throw placementError;
    return {
      ...result,
      summary: {
        filled: filled.length,
        placed: placements.length,
        statusUpdated: plan.statusUpdates.length,
        reconciliationRequired: plan.reconciliationRequired.length,
      },
    };
  });

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
