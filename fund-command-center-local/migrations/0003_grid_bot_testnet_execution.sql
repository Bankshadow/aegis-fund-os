CREATE TABLE IF NOT EXISTS grid_bot_executions (
  id TEXT PRIMARY KEY,
  bot_id TEXT NOT NULL UNIQUE REFERENCES grid_bots(id),
  environment TEXT NOT NULL CHECK (environment = 'BINANCE_TESTNET'),
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','STOPPED','ROLLBACK_REQUIRED')),
  order_count INTEGER NOT NULL,
  started_by TEXT NOT NULL,
  started_at TEXT NOT NULL,
  stopped_by TEXT,
  stopped_at TEXT
);

CREATE TABLE IF NOT EXISTS grid_bot_orders (
  id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL REFERENCES grid_bot_executions(id),
  bot_id TEXT NOT NULL REFERENCES grid_bots(id),
  symbol TEXT NOT NULL,
  exchange_order_id TEXT NOT NULL,
  client_order_id TEXT NOT NULL UNIQUE,
  grid_index INTEGER NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  price TEXT NOT NULL,
  quantity TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(bot_id, exchange_order_id)
);

CREATE INDEX IF NOT EXISTS idx_grid_bot_orders_bot_status
  ON grid_bot_orders(bot_id, status, created_at);

