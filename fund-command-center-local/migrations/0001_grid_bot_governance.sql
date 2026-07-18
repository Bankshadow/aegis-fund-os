PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS grid_bots (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  environment TEXT NOT NULL CHECK (environment IN ('DEMO','PAPER','BINANCE_TESTNET')),
  pair TEXT NOT NULL,
  configuration_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED')),
  maker_id TEXT NOT NULL,
  checker_id TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_bot_approvals (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL UNIQUE REFERENCES grid_bots(id),
  maker_id TEXT NOT NULL,
  checker_id TEXT,
  decision TEXT NOT NULL CHECK (decision IN ('PENDING','APPROVED','REJECTED')),
  reason TEXT,
  created_at TEXT NOT NULL,
  decided_at TEXT
);

CREATE TABLE IF NOT EXISTS grid_bot_idempotency (
  key TEXT PRIMARY KEY,
  operation TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_bot_audit (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  bot_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  bot_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  occurred_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_grid_bot_audit_bot_version
  ON grid_bot_audit(bot_id, bot_version);

CREATE INDEX IF NOT EXISTS idx_grid_bot_audit_bot_sequence
  ON grid_bot_audit(bot_id, sequence);

CREATE TRIGGER IF NOT EXISTS grid_bot_audit_no_update
BEFORE UPDATE ON grid_bot_audit BEGIN SELECT RAISE(ABORT, 'audit events are immutable'); END;

CREATE TRIGGER IF NOT EXISTS grid_bot_audit_no_delete
BEFORE DELETE ON grid_bot_audit BEGIN SELECT RAISE(ABORT, 'audit events are immutable'); END;
