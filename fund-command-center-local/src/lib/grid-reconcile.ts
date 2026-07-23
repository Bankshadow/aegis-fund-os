import type { GridBotRepository, BotRecord } from "./grid-bot-repository.ts";
import { planGridReconciliation } from "./grid-runtime.ts";
import { aggregateFillsByOrder, type ExchangeTrade } from "./grid-fills.ts";
import { classifyReconcileRoute, type ReconcileRoute } from "./grid-runtime-graph.ts";

/**
 * Shared grid reconciliation core, independent of transport and identity.
 *
 * Both the human-triggered server function and the scheduled (cron) driver call
 * `reconcileOneTestnetGrid`; only the exchange access (`getStatus`/`placeOrder`)
 * and the actor identity are injected. Keeping the loop here means one tested
 * code path decides fills and replenishments regardless of who runs it.
 */

export type ReconcileDeps = {
  getStatus: (symbol: "BTCUSDT") => Promise<{
    checkedAt?: string;
    openOrders: Array<{ clientOrderId: string; status: string }>;
    trades: Array<Partial<ExchangeTrade> & { orderId: number | string }>;
  }>;
  placeOrder: (
    symbol: string,
    order: { side: "BUY" | "SELL"; price: string; quantity: string; clientOrderId: string },
  ) => Promise<{ orderId: number | string; status: string }>;
  /** Invoked immediately before every placement; safety wrappers use this to renew a lease and re-check caps. */
  beforePlace?: (alreadyPlaced: number) => Promise<void>;
};

export type ReconcileResult = {
  botId: string;
  changed: boolean;
  summary: {
    filled: number;
    placed: number;
    statusUpdated: number;
    reconciliationRequired: number;
    /** Replenishments left for a later run because this run's placement budget was exhausted. */
    deferred: number;
  };
  /** Additive L3 graph route — classification only; does not change placement. */
  route: ReconcileRoute;
};

export type ReconcileLimits = { maxPlacements?: number };

export async function reconcileOneTestnetGrid(
  repo: GridBotRepository,
  bot: BotRecord,
  actorId: string,
  deps: ReconcileDeps,
  limits: ReconcileLimits = {},
): Promise<ReconcileResult> {
  if (bot.environment !== "BINANCE_TESTNET" || bot.pair !== "BTCUSDT")
    throw new Error("Only a BTCUSDT Binance Spot Testnet bot can reconcile grid fills");
  if (bot.runtimeState !== "RUNNING") throw new Error("Only a RUNNING bot can reconcile grid fills");

  const [orders, remote] = await Promise.all([repo.listOrders(bot.id), deps.getStatus("BTCUSDT")]);
  // Fold the raw trade list into one execution record per order so the plan (and
  // therefore the ledger) carries real fill prices and fees, not just "it filled".
  const fills = aggregateFillsByOrder(
    remote.trades.map((trade) => ({
      orderId: trade.orderId,
      qty: trade.qty ?? "0",
      quoteQty: trade.quoteQty ?? "0",
      commission: trade.commission ?? "0",
      commissionAsset: trade.commissionAsset ?? "",
    })),
  );
  const plan = await planGridReconciliation(
    bot.id,
    orders,
    remote.openOrders.map((order) => ({ clientOrderId: order.clientOrderId, status: order.status })),
    [...fills.values()],
  );
  // The placement budget throttles how many orders one run may send; it is not an
  // error condition. Placing the first `maxPlacements` and leaving the rest for the
  // next run lets a backlog drain, whereas rejecting the whole run would deadlock:
  // the backlog never shrinks, every later run fails identically, and the circuit
  // breaker halts a bot that never actually malfunctioned.
  const scheduled =
    limits.maxPlacements !== undefined && plan.replenishments.length > limits.maxPlacements
      ? plan.replenishments.slice(0, limits.maxPlacements)
      : plan.replenishments;
  const deferred = plan.replenishments.length - scheduled.length;

  // Every planned replenishment is a targeted source, including the deferred ones:
  // a fill whose replenishment was not placed must stay un-terminal so the next run
  // re-plans it. Only `placedSources` releases a fill for commit.
  const targetedSources = new Set(plan.replenishments.map((item) => item.sourceClientOrderId));
  const placedSources = new Set<string>();
  const placements: Array<{
    clientOrderId: string; exchangeOrderId: string; side: "BUY" | "SELL";
    price: string; quantity: string; gridIndex: number; status: string;
  }> = [];
  let placementError: unknown = null;
  for (const replenishment of scheduled) {
    try {
      await deps.beforePlace?.(placements.length);
      const placed = await deps.placeOrder(bot.pair, replenishment);
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
  // replenishment was actually placed; otherwise leave it for the next run.
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
  const summary = {
    filled: filled.length,
    placed: placements.length,
    statusUpdated: plan.statusUpdates.length,
    reconciliationRequired: plan.reconciliationRequired.length,
    deferred,
  };
  return {
    botId: bot.id,
    changed: result.changed,
    summary,
    route: classifyReconcileRoute(summary),
  };
}

/**
 * Reconcile every RUNNING Binance Spot Testnet BTCUSDT bot in one pass. A single
 * bot failing (e.g. an orphaned rollback) is isolated and reported; it never
 * aborts the others. Used by the scheduled cron driver.
 */
export async function reconcileAllRunningTestnetGrids(
  repo: GridBotRepository,
  actorId: string,
  deps: ReconcileDeps,
): Promise<Array<ReconcileResult | { botId: string; error: string }>> {
  const bots = await repo.listBots();
  const running = bots.filter(
    (bot) => bot.environment === "BINANCE_TESTNET" && bot.pair === "BTCUSDT" && bot.runtimeState === "RUNNING",
  );
  const results: Array<ReconcileResult | { botId: string; error: string }> = [];
  for (const bot of running) {
    try {
      results.push(await reconcileOneTestnetGrid(repo, bot, actorId, deps));
    } catch (error) {
      results.push({ botId: bot.id, error: error instanceof Error ? error.message : String(error) });
    }
  }
  return results;
}
