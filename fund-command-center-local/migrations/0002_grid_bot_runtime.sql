ALTER TABLE grid_bots ADD COLUMN runtime_state TEXT NOT NULL DEFAULT 'IDLE'
  CHECK (runtime_state IN ('IDLE','RUNNING','PAUSED','STOPPED'));

CREATE INDEX IF NOT EXISTS idx_grid_bots_runtime_state
  ON grid_bots(runtime_state, updated_at);
