import {
  calculatePaperGrid,
  simulatePaperFill,
  type PaperAccount,
  type PaperGridConfig,
  type PaperOrder,
  type PaperStrategyStatus,
} from "./aot-paper-domain.ts";
import type { D1DatabaseLike, D1Statement } from "./grid-bot-repository.ts";

type StrategyRow = {
  id: string;
  name: string;
  symbol: "AOT";
  status: PaperStrategyStatus;
  configuration_json: string;
  validation_json: string;
  initial_cash: string;
  initial_inventory: string;
  available_cash: string;
  available_inventory: string;
  created_by: string;
  approved_by: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  started_at: string | null;
  stopped_at: string | null;
};
type OrderRow = {
  id: string;
  grid_level_id: string | null;
  side: "BUY" | "SELL";
  limit_price: string;
  original_quantity: string;
  filled_quantity: string;
  remaining_quantity: string;
  average_fill_price: string;
  status: PaperOrder["status"];
  reserved_amount: string;
};
export type PaperStrategyRecord = {
  id: string;
  name: string;
  symbol: "AOT";
  status: PaperStrategyStatus;
  config: PaperGridConfig;
  validation: ReturnType<typeof calculatePaperGrid>["validation"];
  initialCash: string;
  initialInventory: string;
  cash: string;
  inventory: string;
  makerId: string;
  checkerId?: string;
  version: number;
  updatedAt: string;
};
const id = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;
const fromRow = (row: StrategyRow): PaperStrategyRecord => ({
  id: row.id,
  name: row.name,
  symbol: row.symbol,
  status: row.status,
  config: JSON.parse(row.configuration_json),
  validation: JSON.parse(row.validation_json),
  initialCash: row.initial_cash,
  initialInventory: row.initial_inventory,
  cash: row.available_cash,
  inventory: row.available_inventory,
  makerId: row.created_by,
  checkerId: row.approved_by ?? undefined,
  version: row.version,
  updatedAt: row.updated_at,
});

export class AotPaperRepository {
  constructor(private db: D1DatabaseLike) {}
  async get(idValue: string) {
    const row = await this.db
      .prepare("SELECT * FROM paper_strategies WHERE id=?")
      .bind(idValue)
      .first<StrategyRow>();
    return row ? fromRow(row) : null;
  }
  async list() {
    const rows = await this.db
      .prepare("SELECT * FROM paper_strategies ORDER BY updated_at DESC")
      .all<StrategyRow>();
    return (rows.results ?? []).map(fromRow);
  }
  async listOrders(strategyId: string): Promise<PaperOrder[]> {
    const rows = await this.db
      .prepare("SELECT * FROM paper_orders WHERE strategy_id=? ORDER BY created_at")
      .bind(strategyId)
      .all<OrderRow>();
    return (rows.results ?? []).map((row) => ({
      id: row.id,
      gridIndex: Number(row.grid_level_id?.replace("LVL-", "") ?? 0),
      side: row.side,
      limitPrice: row.limit_price,
      originalQuantity: row.original_quantity,
      filledQuantity: row.filled_quantity,
      remainingQuantity: row.remaining_quantity,
      averageFillPrice: row.average_fill_price,
      status: row.status,
      reservedAmount: row.reserved_amount,
    }));
  }
  async create(config: PaperGridConfig, actor: string) {
    const calculation = calculatePaperGrid(config);
    const now = new Date().toISOString();
    const strategyId = id("PSTR");
    const blocked = calculation.validation.some((item) => item.level === "BLOCKED");
    const status: PaperStrategyStatus = "DRAFT";
    const statements: D1Statement[] = [
      this.db
        .prepare(
          "INSERT INTO paper_strategies (id,name,symbol,status,configuration_json,validation_json,initial_cash,initial_inventory,available_cash,available_inventory,created_by,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        )
        .bind(
          strategyId,
          config.name,
          "AOT",
          status,
          JSON.stringify(config),
          JSON.stringify(calculation.validation),
          config.initialCash,
          config.initialInventory,
          config.initialCash,
          config.initialInventory,
          actor,
          1,
          now,
          now,
        ),
    ];
    for (const level of calculation.levels)
      statements.push(
        this.db
          .prepare(
            "INSERT INTO paper_grid_levels (id,strategy_id,grid_index,side,price,quantity,paired_price,status) VALUES (?,?,?,?,?,?,?,?)",
          )
          .bind(
            `LVL-${level.index}`,
            strategyId,
            level.index,
            level.side,
            level.price,
            level.quantity,
            level.pairedPrice ?? null,
            level.side === "REFERENCE" ? "REFERENCE" : "PREVIEW",
          ),
      );
    statements.push(
      this.audit(
        strategyId,
        "strategy.created",
        actor,
        null,
        status,
        null,
        { blocked, validation: calculation.validation.length },
        now,
      ),
    );
    await this.db.batch(statements);
    return (await this.get(strategyId))!;
  }
  async requestApproval(strategyId: string, actor: string) {
    return this.transition(
      strategyId,
      actor,
      "PENDING_APPROVAL",
      "approval.requested",
      (current) => {
        if (current.status !== "DRAFT" || current.makerId !== actor)
          throw new Error("Only the draft maker can request approval");
        if (current.validation.some((v) => v.level === "BLOCKED"))
          throw new Error("Blocked validation prevents approval request");
      },
    );
  }
  async approve(strategyId: string, actor: string, approved: boolean, reason: string) {
    return this.transition(
      strategyId,
      actor,
      approved ? "APPROVED" : "DRAFT",
      approved ? "approval.approved" : "approval.rejected",
      (current) => {
        if (current.status !== "PENDING_APPROVAL")
          throw new Error("Strategy is not pending approval");
        if (current.makerId === actor) throw new Error("Maker cannot approve their own strategy");
      },
      reason,
      approved ? actor : undefined,
    );
  }
  async runtime(strategyId: string, actor: string, next: PaperStrategyStatus) {
    return this.transition(strategyId, actor, next, `strategy.${next.toLowerCase()}`, (current) => {
      const allowed: Record<string, string[]> = {
        APPROVED: ["RUNNING"],
        RUNNING: ["PAUSED", "STOPPED"],
        PAUSED: ["RUNNING", "STOPPED"],
      };
      if (!allowed[current.status]?.includes(next))
        throw new Error(`Invalid paper strategy transition: ${current.status} -> ${next}`);
    });
  }
  async applyPrice(
    strategyId: string,
    actor: string,
    eventId: string,
    price: string,
    volume: string,
    timestamp: string,
  ) {
    const strategy = await this.require(strategyId);
    if (strategy.status !== "RUNNING")
      throw new Error("Only a RUNNING paper strategy accepts a simulated price");
    const prior = await this.db
      .prepare("SELECT id FROM paper_price_events WHERE event_id=?")
      .bind(eventId)
      .first<{ id: string }>();
    if (prior) return { strategy, orders: await this.listOrders(strategyId), idempotent: true };
    const orders = await this.listOrders(strategyId);
    let account: PaperAccount = {
      initialCash: strategy.initialCash,
      cash: strategy.cash,
      inventory: strategy.inventory,
      averageCost: "0",
      realizedGridProfit: "0",
      realizedAssetPnl: "0",
      costs: "0",
      slippage: "0",
      currentPrice: price,
      maxDrawdown: "0",
      completedCycles: 0,
    };
    const statements: D1Statement[] = [
      this.db
        .prepare(
          "INSERT INTO paper_price_events (id,strategy_id,event_id,price,volume,source,occurred_at,created_at) VALUES (?,?,?,?,?,?,?,?)",
        )
        .bind(
          id("PPE"),
          strategyId,
          eventId,
          price,
          volume,
          "MANUAL",
          timestamp,
          new Date().toISOString(),
        ),
    ];
    for (const order of orders.filter(
      (order) =>
        order.status === "OPEN" &&
        ((order.side === "BUY" && Number(price) <= Number(order.limitPrice)) ||
          (order.side === "SELL" && Number(price) >= Number(order.limitPrice))),
    )) {
      const result = simulatePaperFill(order, account, price, order.remainingQuantity);
      account = result.account;
      statements.push(
        this.db
          .prepare(
            "UPDATE paper_orders SET filled_quantity=?,remaining_quantity=?,average_fill_price=?,status=?,updated_at=?,filled_at=? WHERE id=?",
          )
          .bind(
            result.order.filledQuantity,
            result.order.remainingQuantity,
            result.order.averageFillPrice,
            result.order.status,
            timestamp,
            timestamp,
            order.id,
          ),
      );
      statements.push(
        this.db
          .prepare(
            "INSERT INTO paper_fills (id,strategy_id,order_id,event_id,side,quantity,price,gross_amount,cost,slippage,source,occurred_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
          )
          .bind(
            id("PFL"),
            strategyId,
            order.id,
            `${eventId}:${order.id}`,
            order.side,
            order.remainingQuantity,
            price,
            String(Number(price) * Number(order.remainingQuantity)),
            result.account.costs,
            "0",
            "MANUAL",
            timestamp,
          ),
      );
    }
    statements.push(
      this.db
        .prepare(
          "UPDATE paper_strategies SET available_cash=?,available_inventory=?,version=version+1,updated_at=? WHERE id=? AND version=?",
        )
        .bind(account.cash, account.inventory, timestamp, strategyId, strategy.version),
    );
    statements.push(
      this.db
        .prepare(
          "INSERT INTO paper_account_snapshots (id,strategy_id,cash,inventory,average_cost,realized_grid_profit,realized_asset_pnl,costs,current_price,snapshot_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        )
        .bind(
          id("PAC"),
          strategyId,
          account.cash,
          account.inventory,
          account.averageCost,
          account.realizedGridProfit,
          account.realizedAssetPnl,
          account.costs,
          price,
          timestamp,
        ),
    );
    statements.push(
      this.audit(
        strategyId,
        "price.applied",
        actor,
        "RUNNING",
        "RUNNING",
        null,
        { price, volume, source: "MANUAL" },
        timestamp,
      ),
    );
    await this.db.batch(statements);
    return {
      strategy: await this.require(strategyId),
      orders: await this.listOrders(strategyId),
      idempotent: false,
    };
  }
  async openOrders(strategyId: string, actor: string) {
    const strategy = await this.require(strategyId);
    const calculation = calculatePaperGrid(strategy.config);
    if (calculation.validation.some((v) => v.level === "BLOCKED"))
      throw new Error("Validation blocks paper orders");
    const now = new Date().toISOString();
    const statements: D1Statement[] = [];
    for (const level of calculation.levels.filter((level) => level.side !== "REFERENCE"))
      statements.push(
        this.db
          .prepare(
            "INSERT OR IGNORE INTO paper_orders (id,strategy_id,grid_level_id,symbol,side,limit_price,original_quantity,remaining_quantity,status,reserved_amount,simulation_source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
          )
          .bind(
            id("POR"),
            strategyId,
            `LVL-${level.index}`,
            "AOT",
            level.side,
            level.price,
            level.quantity,
            level.quantity,
            "OPEN",
            level.notional,
            "PAPER",
            now,
            now,
          ),
      );
    statements.push(
      this.audit(
        strategyId,
        "orders.opened",
        actor,
        strategy.status,
        strategy.status,
        null,
        { orderCount: calculation.levels.length - 1 },
        now,
      ),
    );
    await this.db.batch(statements);
    return this.listOrders(strategyId);
  }
  private async transition(
    strategyId: string,
    actor: string,
    next: PaperStrategyStatus,
    eventType: string,
    check: (value: PaperStrategyRecord) => void,
    reason?: string,
    approver?: string,
  ) {
    const current = await this.require(strategyId);
    check(current);
    const now = new Date().toISOString();
    await this.db.batch([
      this.db
        .prepare(
          "UPDATE paper_strategies SET status=?,approved_by=COALESCE(?,approved_by),approved_at=CASE WHEN ?='APPROVED' THEN ? ELSE approved_at END,started_at=CASE WHEN ?='RUNNING' THEN ? ELSE started_at END,stopped_at=CASE WHEN ?='STOPPED' THEN ? ELSE stopped_at END,version=?,updated_at=? WHERE id=? AND version=?",
        )
        .bind(
          next,
          approver ?? null,
          next,
          now,
          next,
          now,
          next,
          now,
          current.version + 1,
          now,
          strategyId,
          current.version,
        ),
      this.audit(strategyId, eventType, actor, current.status, next, null, {}, now, reason),
    ]);
    return await this.require(strategyId);
  }
  private async require(strategyId: string) {
    const strategy = await this.get(strategyId);
    if (!strategy) throw new Error("Paper strategy not found");
    return strategy;
  }
  private audit(
    strategyId: string,
    eventType: string,
    actor: string,
    previous: string | null,
    next: string | null,
    related: string | null,
    metadata: Record<string, unknown>,
    occurredAt: string,
    reason?: string,
  ) {
    return this.db
      .prepare(
        "INSERT INTO paper_audit_events (event_id,strategy_id,event_type,actor_id,previous_state,new_state,related_entity_id,reason,metadata_json,correlation_id,occurred_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
      )
      .bind(
        id("PAU"),
        strategyId,
        eventType,
        actor,
        previous,
        next,
        related,
        reason ?? null,
        JSON.stringify(metadata),
        crypto.randomUUID(),
        occurredAt,
      );
  }
}
