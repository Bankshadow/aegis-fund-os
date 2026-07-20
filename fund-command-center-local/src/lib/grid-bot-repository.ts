import {
  appendGovernanceEvent,
  decideApproval,
  sha256,
  submitForApproval,
  transitionRuntime,
  type GovernanceEvent,
  type GovernanceState,
  type RuntimeState,
} from "./grid-bot-governance.ts";

export interface D1Result<T = unknown> {
  success: boolean;
  results?: T[];
  meta?: { changes?: number };
}

export interface D1Statement {
  bind(...values: unknown[]): D1Statement;
  first<T = unknown>(): Promise<T | null>;
  all<T = unknown>(): Promise<D1Result<T>>;
  run<T = unknown>(): Promise<D1Result<T>>;
}

export interface D1DatabaseLike {
  prepare(sql: string): D1Statement;
  batch<T = unknown>(statements: D1Statement[]): Promise<D1Result<T>[]>;
}

export type BotRecord = {
  id: string;
  name: string;
  environment: "DEMO" | "PAPER" | "BINANCE_TESTNET";
  pair: string;
  configuration: Record<string, string | number | boolean | null>;
  state: GovernanceState;
  runtimeState: RuntimeState;
  makerId: string;
  checkerId?: string;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type TestnetOrderRow = {
  id: string;
  executionId: string;
  botId: string;
  symbol: string;
  exchangeOrderId: string;
  clientOrderId: string;
  gridIndex: number;
  side: "BUY" | "SELL";
  price: string;
  quantity: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  /** Actual execution detail, populated at reconciliation (migration 0005). */
  filledQuantity?: string;
  avgFillPrice?: string;
  commission?: string;
  commissionAsset?: string;
};

type TestnetOrderDbRow = {
  id: string; execution_id: string; bot_id: string; symbol: string;
  exchange_order_id: string; client_order_id: string; grid_index: number;
  side: "BUY" | "SELL"; price: string; quantity: string; status: string;
  created_at: string; updated_at: string;
  filled_quantity: string | null; avg_fill_price: string | null;
  commission: string | null; commission_asset: string | null;
};

type BotRow = {
  id: string;
  name: string;
  environment: BotRecord["environment"];
  pair: string;
  configuration_json: string;
  state: GovernanceState;
  runtime_state: RuntimeState;
  maker_id: string;
  checker_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

type AuditRow = {
  event_id: string;
  bot_id: string;
  event_type: GovernanceEvent["eventType"];
  actor_id: string;
  payload_json: string;
  previous_hash: string;
  event_hash: string;
  occurred_at: string;
};

const botFromRow = (row: BotRow): BotRecord => ({
  id: row.id,
  name: row.name,
  environment: row.environment,
  pair: row.pair,
  configuration: JSON.parse(row.configuration_json),
  state: row.state,
  runtimeState: row.runtime_state,
  makerId: row.maker_id,
  checkerId: row.checker_id ?? undefined,
  version: row.version,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

const orderFromRow = (row: TestnetOrderDbRow): TestnetOrderRow => ({
  id: row.id, executionId: row.execution_id, botId: row.bot_id, symbol: row.symbol,
  exchangeOrderId: row.exchange_order_id, clientOrderId: row.client_order_id,
  gridIndex: row.grid_index, side: row.side, price: row.price, quantity: row.quantity,
  status: row.status, createdAt: row.created_at, updatedAt: row.updated_at,
  filledQuantity: row.filled_quantity ?? undefined,
  avgFillPrice: row.avg_fill_price ?? undefined,
  commission: row.commission ?? undefined,
  commissionAsset: row.commission_asset ?? undefined,
});

const eventFromRow = (row: AuditRow): GovernanceEvent => ({
  eventId: row.event_id,
  botId: row.bot_id,
  eventType: row.event_type,
  actorId: row.actor_id,
  payload: JSON.parse(row.payload_json),
  previousHash: row.previous_hash,
  eventHash: row.event_hash,
  occurredAt: row.occurred_at,
});

const id = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;

export class GridBotRepository {
  private readonly db: D1DatabaseLike;

  constructor(db: D1DatabaseLike) {
    this.db = db;
  }

  async getBot(botId: string) {
    const row = await this.db
      .prepare("SELECT * FROM grid_bots WHERE id = ?")
      .bind(botId)
      .first<BotRow>();
    return row ? botFromRow(row) : null;
  }

  async listBots() {
    const rows = await this.db
      .prepare("SELECT * FROM grid_bots ORDER BY updated_at DESC")
      .all<BotRow>();
    return (rows.results ?? []).map(botFromRow);
  }

  async listEvents(botId?: string) {
    const statement = botId
      ? this.db
          .prepare("SELECT * FROM grid_bot_audit WHERE bot_id = ? ORDER BY sequence")
          .bind(botId)
      : this.db.prepare("SELECT * FROM grid_bot_audit ORDER BY sequence");
    const rows = await statement.all<AuditRow>();
    return (rows.results ?? []).map(eventFromRow);
  }

  /** Aggregate counts backing the public-deployment abuse guards. */
  async countBots(): Promise<number> {
    const row = await this.db.prepare("SELECT count(*) AS n FROM grid_bots").first<{ n: number }>();
    return Number(row?.n ?? 0);
  }

  async countBotsCreatedSince(isoTimestamp: string): Promise<number> {
    const row = await this.db
      .prepare("SELECT count(*) AS n FROM grid_bots WHERE created_at >= ?")
      .bind(isoTimestamp)
      .first<{ n: number }>();
    return Number(row?.n ?? 0);
  }

  async countOpenTestnetOrders(): Promise<number> {
    const row = await this.db
      .prepare("SELECT count(*) AS n FROM grid_bot_orders WHERE status IN ('NEW','PARTIALLY_FILLED')")
      .first<{ n: number }>();
    return Number(row?.n ?? 0);
  }

  async listOrders(botId: string): Promise<TestnetOrderRow[]> {
    const rows = await this.db
      .prepare("SELECT * FROM grid_bot_orders WHERE bot_id = ? ORDER BY grid_index")
      .bind(botId)
      .all<TestnetOrderDbRow>();
    return (rows.results ?? []).map(orderFromRow);
  }

  async listAllOrders(): Promise<TestnetOrderRow[]> {
    const rows = await this.db
      .prepare("SELECT * FROM grid_bot_orders ORDER BY bot_id, grid_index")
      .all<TestnetOrderDbRow>();
    return (rows.results ?? []).map(orderFromRow);
  }

  async recordTestnetStart(
    botId: string,
    actorId: string,
    orders: Array<Omit<TestnetOrderRow, "id" | "executionId" | "botId" | "symbol" | "createdAt" | "updatedAt">>,
  ) {
    const current = await this.requireBot(botId);
    if (current.environment !== "BINANCE_TESTNET") throw new Error("Bot is not a Binance Testnet bot");
    const next = transitionRuntime(current.state, current.runtimeState, "RUNNING");
    if (!orders.length) throw new Error("No Testnet orders were accepted");
    const executionId = id("EXE");
    const now = new Date().toISOString();
    const nextVersion = current.version + 1;
    const previous = (await this.listEvents(botId)).at(-1);
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"), botId, eventType: "testnet.orders_placed", actorId,
      payload: { executionId, orderCount: orders.length, environment: "BINANCE_TESTNET" }, occurredAt: now,
    });
    const statements = [
      this.db.prepare("INSERT INTO grid_bot_executions (id,bot_id,environment,status,order_count,started_by,started_at) VALUES (?,?,?,?,?,?,?)")
        .bind(executionId, botId, "BINANCE_TESTNET", "ACTIVE", orders.length, actorId, now),
      ...orders.map((order) => this.db.prepare("INSERT INTO grid_bot_orders (id,execution_id,bot_id,symbol,exchange_order_id,client_order_id,grid_index,side,price,quantity,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)")
        .bind(id("ORD"), executionId, botId, current.pair, order.exchangeOrderId, order.clientOrderId, order.gridIndex, order.side, order.price, order.quantity, order.status, now, now)),
      this.db.prepare("UPDATE grid_bots SET runtime_state=?,version=?,updated_at=? WHERE id=? AND runtime_state='IDLE' AND state='APPROVED' AND version=?")
        .bind(next, nextVersion, now, botId, current.version),
      this.auditInsert(event, nextVersion),
    ];
    await this.db.batch(statements);
    return { bot: { ...current, runtimeState: next, version: nextVersion, updatedAt: now }, orders: await this.listOrders(botId) };
  }

  /**
   * Persist one grid runtime reconciliation atomically: mark filled and
   * externally-cancelled orders, apply exchange status changes, insert the
   * paired replenishment orders under the same active execution, and append a
   * single hash-chained `testnet.grid_synced` event. A poll that found nothing
   * writes nothing (no empty audit noise, no version churn).
   */
  async recordGridSync(
    botId: string,
    actorId: string,
    sync: {
      statusUpdates: Array<{ clientOrderId: string; status: string }>;
      filled: Array<{
        clientOrderId: string;
        filledQuantity?: string;
        avgFillPrice?: string;
        commission?: string;
        commissionAsset?: string;
      }>;
      reconciliationRequired: Array<{ clientOrderId: string }>;
      placements: Array<{
        clientOrderId: string;
        exchangeOrderId: string;
        side: "BUY" | "SELL";
        price: string;
        quantity: string;
        gridIndex: number;
        status: string;
      }>;
    },
  ) {
    const current = await this.requireBot(botId);
    if (current.environment !== "BINANCE_TESTNET") throw new Error("Bot is not a Binance Testnet bot");
    if (current.runtimeState !== "RUNNING") throw new Error("Only a RUNNING bot can reconcile grid fills");
    const changeCount =
      sync.statusUpdates.length + sync.filled.length + sync.reconciliationRequired.length + sync.placements.length;
    if (changeCount === 0) return { bot: current, orders: await this.listOrders(botId), changed: false };

    const execution = await this.db
      .prepare("SELECT id FROM grid_bot_executions WHERE bot_id=? AND status='ACTIVE'")
      .bind(botId)
      .first<{ id: string }>();
    if (!execution) throw new Error("No active Testnet execution to reconcile");

    const now = new Date().toISOString();
    const nextVersion = current.version + 1;
    const previous = (await this.listEvents(botId)).at(-1);
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"),
      botId,
      eventType: "testnet.grid_synced",
      actorId,
      payload: {
        filled: sync.filled.length,
        placed: sync.placements.length,
        statusUpdated: sync.statusUpdates.length,
        reconciliationRequired: sync.reconciliationRequired.length,
        environment: "BINANCE_TESTNET",
      },
      occurredAt: now,
    });
    const statements: D1Statement[] = [
      ...sync.filled.map((order) =>
        this.db
          .prepare("UPDATE grid_bot_orders SET status='FILLED',updated_at=? WHERE bot_id=? AND client_order_id=?")
          .bind(now, botId, order.clientOrderId),
      ),
      ...sync.reconciliationRequired.map((order) =>
        this.db
          .prepare("UPDATE grid_bot_orders SET status='RECONCILIATION_REQUIRED',updated_at=? WHERE bot_id=? AND client_order_id=?")
          .bind(now, botId, order.clientOrderId),
      ),
      ...sync.statusUpdates.map((order) =>
        this.db
          .prepare("UPDATE grid_bot_orders SET status=?,updated_at=? WHERE bot_id=? AND client_order_id=?")
          .bind(order.status, now, botId, order.clientOrderId),
      ),
      ...sync.placements.map((order) =>
        this.db
          .prepare(
            "INSERT INTO grid_bot_orders (id,execution_id,bot_id,symbol,exchange_order_id,client_order_id,grid_index,side,price,quantity,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
          )
          .bind(
            id("ORD"),
            execution.id,
            botId,
            current.pair,
            order.exchangeOrderId,
            order.clientOrderId,
            order.gridIndex,
            order.side,
            order.price,
            order.quantity,
            order.status,
            now,
            now,
          ),
      ),
      this.db
        .prepare("UPDATE grid_bots SET version=?,updated_at=? WHERE id=? AND runtime_state='RUNNING' AND version=?")
        .bind(nextVersion, now, botId, current.version),
      this.auditInsert(event, nextVersion),
    ];
    await this.db.batch(statements);
    await this.recordFillDetails(botId, now, sync.filled);
    return {
      bot: { ...current, version: nextVersion, updatedAt: now },
      orders: await this.listOrders(botId),
      changed: true,
    };
  }

  /**
   * Enrich filled orders with what the exchange actually executed. Deliberately
   * outside the atomic batch and best-effort: this detail improves realized-P/L
   * accuracy but is not required for correctness, so a database that has not yet
   * taken migration 0005 must not break reconciliation — the ledger still records
   * the fill, and realized P/L simply falls back to the estimate. COALESCE keeps
   * previously captured detail when a later sync reports nothing.
   */
  private async recordFillDetails(
    botId: string,
    now: string,
    filled: Array<{
      clientOrderId: string;
      filledQuantity?: string;
      avgFillPrice?: string;
      commission?: string;
      commissionAsset?: string;
    }>,
  ) {
    const withDetail = filled.filter(
      (order) => order.filledQuantity || order.avgFillPrice || order.commission || order.commissionAsset,
    );
    if (withDetail.length === 0) return;
    try {
      await this.db.batch(
        withDetail.map((order) =>
          this.db
            .prepare(
              "UPDATE grid_bot_orders SET updated_at=?," +
                "filled_quantity=COALESCE(?,filled_quantity),avg_fill_price=COALESCE(?,avg_fill_price)," +
                "commission=COALESCE(?,commission),commission_asset=COALESCE(?,commission_asset) " +
                "WHERE bot_id=? AND client_order_id=?",
            )
            .bind(
              now,
              order.filledQuantity ?? null,
              order.avgFillPrice ?? null,
              order.commission ?? null,
              order.commissionAsset ?? null,
              botId,
              order.clientOrderId,
            ),
        ),
      );
    } catch (error) {
      console.warn("grid fill-detail capture skipped (is migration 0005 applied?):", error);
    }
  }

  async recordTestnetStop(botId: string, actorId: string, statuses: Map<string, string>) {
    const current = await this.requireBot(botId);
    const next = transitionRuntime(current.state, current.runtimeState, "STOPPED");
    const orders = await this.listOrders(botId);
    const now = new Date().toISOString();
    const nextVersion = current.version + 1;
    const previous = (await this.listEvents(botId)).at(-1);
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"), botId, eventType: "testnet.orders_cancelled", actorId,
      payload: { orderCount: orders.length, environment: "BINANCE_TESTNET" }, occurredAt: now,
    });
    await this.db.batch([
      ...orders.map((order) => this.db.prepare("UPDATE grid_bot_orders SET status=?,updated_at=? WHERE id=?")
        .bind(statuses.get(order.clientOrderId) ?? order.status, now, order.id)),
      this.db.prepare("UPDATE grid_bot_executions SET status='STOPPED',stopped_by=?,stopped_at=? WHERE bot_id=? AND status='ACTIVE'")
        .bind(actorId, now, botId),
      this.db.prepare("UPDATE grid_bots SET runtime_state=?,version=?,updated_at=? WHERE id=? AND runtime_state IN ('RUNNING','PAUSED') AND version=?")
        .bind(next, nextVersion, now, botId, current.version),
      this.auditInsert(event, nextVersion),
    ]);
    return { ...current, runtimeState: next, version: nextVersion, updatedAt: now };
  }

  async createDraft(
    input: Omit<
      BotRecord,
      "id" | "state" | "runtimeState" | "checkerId" | "version" | "createdAt" | "updatedAt"
    >,
    idempotencyKey: string,
  ) {
    if (!idempotencyKey.trim()) throw new Error("Idempotency key is required");
    const requestJson = JSON.stringify(input);
    const requestHash = await sha256(requestJson);
    const prior = await this.db
      .prepare("SELECT resource_id, request_hash FROM grid_bot_idempotency WHERE key = ?")
      .bind(idempotencyKey)
      .first<{ resource_id: string; request_hash: string }>();
    if (prior) {
      if (prior.request_hash !== requestHash)
        throw new Error("Idempotency key reused with different request");
      const existing = await this.getBot(prior.resource_id);
      if (!existing) throw new Error("Idempotency record is orphaned");
      return existing;
    }
    const now = new Date().toISOString();
    const bot: BotRecord = {
      ...input,
      id: id("BOT"),
      state: "DRAFT",
      runtimeState: "IDLE",
      version: 1,
      createdAt: now,
      updatedAt: now,
    };
    const event = await appendGovernanceEvent([], {
      eventId: id("EVT"),
      botId: bot.id,
      eventType: "bot.created",
      actorId: bot.makerId,
      payload: { state: bot.state },
      occurredAt: now,
    });
    await this.db.batch([
      this.db
        .prepare(
          "INSERT INTO grid_bots (id,name,environment,pair,configuration_json,state,maker_id,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        )
        .bind(
          bot.id,
          bot.name,
          bot.environment,
          bot.pair,
          JSON.stringify(bot.configuration),
          bot.state,
          bot.makerId,
          bot.version,
          now,
          now,
        ),
      this.db
        .prepare(
          "INSERT INTO grid_bot_idempotency (key,operation,resource_id,request_hash,created_at) VALUES (?,?,?,?,?)",
        )
        .bind(idempotencyKey, "bot.create", bot.id, requestHash, now),
      this.auditInsert(event, bot.version),
    ]);
    return bot;
  }

  async submit(botId: string, makerId: string) {
    const current = await this.requireBot(botId);
    const next = submitForApproval(current, makerId);
    const now = new Date().toISOString();
    const previous = (await this.listEvents(botId)).at(-1);
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"),
      botId,
      eventType: "approval.requested",
      actorId: makerId,
      payload: { from: current.state, to: next.state },
      occurredAt: now,
    });
    await this.db.batch([
      this.db
        .prepare(
          "UPDATE grid_bots SET state=?,version=?,updated_at=? WHERE id=? AND state='DRAFT' AND version=?",
        )
        .bind(next.state, next.version, now, botId, current.version),
      this.db
        .prepare(
          "INSERT INTO grid_bot_approvals (id,bot_id,maker_id,decision,created_at) SELECT ?,?,?,?,? FROM grid_bots WHERE id=? AND version=?",
        )
        .bind(id("APR"), botId, makerId, "PENDING", now, botId, next.version),
      this.auditInsert(event, next.version),
    ]);
    return { ...current, ...next, updatedAt: now };
  }

  /**
   * The one-click path is deliberately restricted to the Binance Spot Testnet
   * environment. It records a distinct system decision so it cannot be
   * mistaken for a four-eyes approval or used for any other environment.
   */
  async autoApproveTestnet(botId: string) {
    const current = await this.requireBot(botId);
    if (current.environment !== "BINANCE_TESTNET")
      throw new Error("Automatic approval is restricted to Binance Spot Testnet");
    if (current.state !== "DRAFT") throw new Error("Only a new Testnet draft can be auto-approved");
    const now = new Date().toISOString();
    const checkerId = "system:testnet-autostart";
    const nextVersion = current.version + 1;
    const previous = (await this.listEvents(botId)).at(-1);
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"), botId, eventType: "approval.auto_approved_testnet", actorId: checkerId,
      payload: { decision: "APPROVED", policy: "BINANCE_TESTNET_ONE_CLICK" }, occurredAt: now,
    });
    await this.db.batch([
      this.db
        .prepare("UPDATE grid_bots SET state='APPROVED',checker_id=?,version=?,updated_at=? WHERE id=? AND environment='BINANCE_TESTNET' AND state='DRAFT' AND version=?")
        .bind(checkerId, nextVersion, now, botId, current.version),
      this.db
        .prepare("INSERT INTO grid_bot_approvals (id,bot_id,maker_id,checker_id,decision,reason,created_at,decided_at) VALUES (?,?,?,?,?,?,?,?)")
        .bind(id("APR"), botId, current.makerId, checkerId, "APPROVED", "Automatic Binance Spot Testnet one-click policy", now, now),
      this.auditInsert(event, nextVersion),
    ]);
    return {
      ...current,
      state: "APPROVED" as const,
      checkerId,
      version: nextVersion,
      updatedAt: now,
    };
  }

  async decide(
    botId: string,
    checkerId: string,
    decision: "APPROVED" | "REJECTED",
    reason: string,
  ) {
    const current = await this.requireBot(botId);
    const next = decideApproval(current, checkerId, decision);
    const now = new Date().toISOString();
    const previous = (await this.listEvents(botId)).at(-1);
    const eventType = decision === "APPROVED" ? "approval.approved" : "approval.rejected";
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"),
      botId,
      eventType,
      actorId: checkerId,
      payload: { decision, reason },
      occurredAt: now,
    });
    await this.db.batch([
      this.db
        .prepare(
          "UPDATE grid_bots SET state=?,checker_id=?,version=?,updated_at=? WHERE id=? AND state='PENDING_APPROVAL' AND version=?",
        )
        .bind(decision, checkerId, next.version, now, botId, current.version),
      this.db
        .prepare(
          "UPDATE grid_bot_approvals SET checker_id=?,decision=?,reason=?,decided_at=? WHERE bot_id=? AND decision='PENDING'",
        )
        .bind(checkerId, decision, reason, now, botId),
      this.auditInsert(event, next.version),
    ]);
    return { ...current, ...next, updatedAt: now };
  }

  async transitionRuntime(botId: string, actorId: string, nextState: RuntimeState) {
    const current = await this.requireBot(botId);
    const next = transitionRuntime(current.state, current.runtimeState, nextState);
    const nextVersion = current.version + 1;
    const now = new Date().toISOString();
    const previous = (await this.listEvents(botId)).at(-1);
    const eventType =
      next === "PAUSED"
        ? "runtime.paused"
        : next === "STOPPED"
          ? "runtime.stopped"
          : current.runtimeState === "PAUSED"
            ? "runtime.resumed"
            : "runtime.started";
    const event = await appendGovernanceEvent(previous ? [previous] : [], {
      eventId: id("EVT"),
      botId,
      eventType,
      actorId,
      payload: { from: current.runtimeState, to: next },
      occurredAt: now,
    });
    await this.db.batch([
      this.db
        .prepare(
          "UPDATE grid_bots SET runtime_state=?,version=?,updated_at=? WHERE id=? AND runtime_state=? AND version=?",
        )
        .bind(next, nextVersion, now, botId, current.runtimeState, current.version),
      this.auditInsert(event, nextVersion),
    ]);
    return { ...current, runtimeState: next, version: nextVersion, updatedAt: now };
  }

  private async requireBot(botId: string) {
    const bot = await this.getBot(botId);
    if (!bot) throw new Error("Bot not found");
    return bot;
  }

  private auditInsert(event: GovernanceEvent, version: number) {
    return this.db
      .prepare(
        "INSERT INTO grid_bot_audit (event_id,bot_id,event_type,actor_id,bot_version,payload_json,previous_hash,event_hash,occurred_at) VALUES (?,?,?,?,?,?,?,?,?)",
      )
      .bind(
        event.eventId,
        event.botId,
        event.eventType,
        event.actorId,
        version,
        JSON.stringify(event.payload),
        event.previousHash,
        event.eventHash,
        event.occurredAt,
      );
  }
}
