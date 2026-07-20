import Decimal from "decimal.js-light";
import { hmacSha256Hex } from "./binance-signing.ts";
import type { TestnetOrderRow } from "./grid-bot-repository.ts";

/**
 * Grid runtime reconciliation.
 *
 * A grid bot harvests oscillation: when a BUY fills, a SELL is placed one grid
 * line up (sell what was just bought); when a SELL fills, a BUY is placed one
 * grid line down (buy it back cheaper). This module is a pure planner — given
 * the durable order ledger plus the exchange's current open orders and fills it
 * decides which ledger rows changed and which paired replenishment orders to
 * place next. It transmits nothing; the caller places orders and persists the
 * plan atomically, so the planner stays fully testable offline.
 *
 * Fail-closed rules:
 *  - A ledger order that is neither open on the exchange nor backed by a fill is
 *    marked RECONCILIATION_REQUIRED and never triggers a replenishment.
 *  - Replenishment prices are always existing grid lines (members of the ladder
 *    derived from the ledger), so the grid geometry can never drift.
 *  - A fill at the very edge of the grid has no adjacent line and places nothing.
 *  - Replenishment client-order ids are deterministic, so re-running a sync after
 *    a fill was already processed places no duplicate order.
 */

const ACTIVE_STATUSES = new Set(["NEW", "PARTIALLY_FILLED"]);

export type RemoteOpenOrder = { clientOrderId: string; status: string };
/** Actual execution detail for a filled order (see `grid-fills.ts`). */
export type RemoteFill = {
  exchangeOrderId: string;
  filledQuantity?: string;
  avgFillPrice?: string;
  commission?: string;
  commissionAsset?: string;
};

export type PlannedReplenishment = {
  clientOrderId: string;
  side: "BUY" | "SELL";
  price: string;
  quantity: string;
  gridIndex: number;
  sourceClientOrderId: string;
};

export type FilledOrder = {
  clientOrderId: string;
  side: "BUY" | "SELL";
  price: string;
  /** Actual execution detail, when the exchange reported it. */
  filledQuantity?: string;
  avgFillPrice?: string;
  commission?: string;
  commissionAsset?: string;
};

export type ReconciliationPlan = {
  statusUpdates: Array<{ clientOrderId: string; status: string }>;
  filled: FilledOrder[];
  reconciliationRequired: Array<{ clientOrderId: string }>;
  replenishments: PlannedReplenishment[];
};

const ladderOf = (orders: TestnetOrderRow[]): Decimal[] => {
  const byPrice = new Map<string, Decimal>();
  for (const order of orders) if (!byPrice.has(order.price)) byPrice.set(order.price, new Decimal(order.price));
  return [...byPrice.values()].sort((a, b) => a.cmp(b));
};

const nextLineUp = (ladder: Decimal[], price: Decimal) => ladder.find((line) => line.gt(price));
const nextLineDown = (ladder: Decimal[], price: Decimal) =>
  [...ladder].reverse().find((line) => line.lt(price));

/** Deterministic id so a replayed sync never double-places the same cycle order. */
export async function replenishmentClientOrderId(
  botId: string,
  sourceClientOrderId: string,
  side: "BUY" | "SELL",
  price: string,
): Promise<string> {
  const digest = await hmacSha256Hex(botId, `replenish:${sourceClientOrderId}:${side}:${price}`);
  return `aegis-r-${digest.slice(0, 22)}`;
}

export async function planGridReconciliation(
  botId: string,
  orders: TestnetOrderRow[],
  remoteOpenOrders: RemoteOpenOrder[],
  remoteFills: RemoteFill[],
): Promise<ReconciliationPlan> {
  const openStatusByClient = new Map(remoteOpenOrders.map((order) => [order.clientOrderId, order.status]));
  const fillByExchangeId = new Map(remoteFills.map((fill) => [fill.exchangeOrderId, fill]));
  const knownClientIds = new Set(orders.map((order) => order.clientOrderId));
  const ladder = ladderOf(orders);

  const plan: ReconciliationPlan = {
    statusUpdates: [],
    filled: [],
    reconciliationRequired: [],
    replenishments: [],
  };

  for (const order of orders) {
    if (!ACTIVE_STATUSES.has(order.status)) continue; // already terminal — processed earlier
    const remoteStatus = openStatusByClient.get(order.clientOrderId);
    if (remoteStatus !== undefined) {
      if (remoteStatus !== order.status) plan.statusUpdates.push({ clientOrderId: order.clientOrderId, status: remoteStatus });
      continue;
    }
    const fill = fillByExchangeId.get(order.exchangeOrderId);
    if (!fill) {
      plan.reconciliationRequired.push({ clientOrderId: order.clientOrderId });
      continue;
    }
    plan.filled.push({
      clientOrderId: order.clientOrderId,
      side: order.side,
      price: order.price,
      filledQuantity: fill.filledQuantity,
      avgFillPrice: fill.avgFillPrice,
      commission: fill.commission,
      commissionAsset: fill.commissionAsset,
    });
    const price = new Decimal(order.price);
    const target = order.side === "BUY" ? nextLineUp(ladder, price) : nextLineDown(ladder, price);
    if (!target) continue; // grid boundary reached; harvest ends on this side
    const side: "BUY" | "SELL" = order.side === "BUY" ? "SELL" : "BUY";
    const targetPrice = target.toFixed();
    const clientOrderId = await replenishmentClientOrderId(botId, order.clientOrderId, side, targetPrice);
    if (knownClientIds.has(clientOrderId)) continue; // already replenished — idempotent
    knownClientIds.add(clientOrderId); // guard against duplicates inside this batch
    plan.replenishments.push({
      clientOrderId,
      side,
      price: targetPrice,
      quantity: order.quantity,
      gridIndex: order.gridIndex,
      sourceClientOrderId: order.clientOrderId,
    });
  }
  return plan;
}
