-- Durable safety state for the Testnet-only reconciliation loop. These tables
-- intentionally contain no exchange credentials or mainnet concepts.
CREATE TABLE IF NOT EXISTS grid_runtime_controls (
  scope TEXT PRIMARY KEY, -- GLOBAL or BOT:<bot id>
  placement_disabled INTEGER NOT NULL DEFAULT 0 CHECK (placement_disabled IN (0,1)),
  consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
  reason TEXT,
  updated_by TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_runtime_leases (
  bot_id TEXT PRIMARY KEY REFERENCES grid_bots(id),
  holder TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_runtime_runs (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL REFERENCES grid_bots(id),
  actor_id TEXT NOT NULL,
  holder TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('STARTED','SUCCEEDED','FAILED','SKIPPED')),
  reason TEXT,
  placements INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_grid_runtime_runs_bot_started
  ON grid_runtime_runs(bot_id, started_at DESC);
