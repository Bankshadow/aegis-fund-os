-- Additive route classification on durable runtime runs (L3 graph).
-- Does not change placement authority; columns are nullable for pre-migration rows.
ALTER TABLE grid_runtime_runs ADD COLUMN route_severity TEXT
  CHECK (route_severity IS NULL OR route_severity IN ('ok','deferred','mismatch','error'));
ALTER TABLE grid_runtime_runs ADD COLUMN route_action TEXT
  CHECK (route_action IS NULL OR route_action IN ('continue','retry_next','operator_review'));
ALTER TABLE grid_runtime_runs ADD COLUMN work_remaining INTEGER
  CHECK (work_remaining IS NULL OR work_remaining IN (0,1));
ALTER TABLE grid_runtime_runs ADD COLUMN deferred INTEGER NOT NULL DEFAULT 0
  CHECK (deferred >= 0);

CREATE INDEX IF NOT EXISTS idx_grid_runtime_runs_severity
  ON grid_runtime_runs(route_severity, started_at DESC);
