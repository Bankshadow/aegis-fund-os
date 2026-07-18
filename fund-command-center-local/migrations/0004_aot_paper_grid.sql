PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS paper_strategies (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, symbol TEXT NOT NULL CHECK(symbol='AOT'), status TEXT NOT NULL,
  configuration_json TEXT NOT NULL, validation_json TEXT NOT NULL, initial_cash TEXT NOT NULL, initial_inventory TEXT NOT NULL,
  available_cash TEXT NOT NULL, available_inventory TEXT NOT NULL, created_by TEXT NOT NULL, approved_by TEXT,
  version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, approved_at TEXT, started_at TEXT, stopped_at TEXT
);
CREATE TABLE IF NOT EXISTS paper_grid_levels (
  id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES paper_strategies(id), grid_index INTEGER NOT NULL, side TEXT NOT NULL,
  price TEXT NOT NULL, quantity TEXT NOT NULL, paired_price TEXT, status TEXT NOT NULL DEFAULT 'PREVIEW', UNIQUE(strategy_id, grid_index)
);
CREATE TABLE IF NOT EXISTS paper_orders (
  id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES paper_strategies(id), grid_level_id TEXT, symbol TEXT NOT NULL, side TEXT NOT NULL,
  limit_price TEXT NOT NULL, original_quantity TEXT NOT NULL, filled_quantity TEXT NOT NULL DEFAULT '0', remaining_quantity TEXT NOT NULL,
  average_fill_price TEXT NOT NULL DEFAULT '0', status TEXT NOT NULL, reserved_amount TEXT NOT NULL DEFAULT '0', simulation_source TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, filled_at TEXT, cancellation_reason TEXT, UNIQUE(strategy_id, grid_level_id, status)
);
CREATE TABLE IF NOT EXISTS paper_fills (
  id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES paper_strategies(id), order_id TEXT NOT NULL REFERENCES paper_orders(id), event_id TEXT NOT NULL UNIQUE,
  side TEXT NOT NULL, quantity TEXT NOT NULL, price TEXT NOT NULL, gross_amount TEXT NOT NULL, cost TEXT NOT NULL, slippage TEXT NOT NULL, source TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_account_snapshots (
  id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES paper_strategies(id), cash TEXT NOT NULL, inventory TEXT NOT NULL, average_cost TEXT NOT NULL,
  realized_grid_profit TEXT NOT NULL, realized_asset_pnl TEXT NOT NULL, costs TEXT NOT NULL, current_price TEXT NOT NULL, snapshot_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_price_events (
  id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES paper_strategies(id), event_id TEXT NOT NULL UNIQUE, price TEXT NOT NULL, volume TEXT NOT NULL,
  source TEXT NOT NULL, occurred_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_approvals (
  id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL UNIQUE REFERENCES paper_strategies(id), requester_id TEXT NOT NULL, approver_id TEXT, decision TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS paper_audit_events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, strategy_id TEXT NOT NULL, event_type TEXT NOT NULL, actor_id TEXT NOT NULL,
  previous_state TEXT, new_state TEXT, related_entity_id TEXT, reason TEXT, metadata_json TEXT NOT NULL, correlation_id TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS paper_audit_no_update BEFORE UPDATE ON paper_audit_events BEGIN SELECT RAISE(ABORT, 'paper audit events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS paper_audit_no_delete BEFORE DELETE ON paper_audit_events BEGIN SELECT RAISE(ABORT, 'paper audit events are immutable'); END;
CREATE INDEX IF NOT EXISTS idx_paper_orders_strategy_status ON paper_orders(strategy_id, status);
CREATE INDEX IF NOT EXISTS idx_paper_audit_strategy ON paper_audit_events(strategy_id, sequence);
