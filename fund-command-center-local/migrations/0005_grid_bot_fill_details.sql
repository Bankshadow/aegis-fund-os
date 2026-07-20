-- Actual execution detail per grid order, captured at reconciliation time so
-- realized P/L is computed from what the exchange really filled rather than from
-- the LIMIT price and a flat fee estimate. All columns are nullable: rows placed
-- before this migration keep working and fall back to the estimate.
ALTER TABLE grid_bot_orders ADD COLUMN filled_quantity TEXT;
ALTER TABLE grid_bot_orders ADD COLUMN avg_fill_price TEXT;
ALTER TABLE grid_bot_orders ADD COLUMN commission TEXT;
ALTER TABLE grid_bot_orders ADD COLUMN commission_asset TEXT;
