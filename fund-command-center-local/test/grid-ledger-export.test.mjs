import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  GRID_LEDGER_EXPORT_VERSION,
  buildGridLedgerExport,
} from "../src/lib/grid-ledger-export.ts";

const options = {
  platform: "binance-spot-testnet",
  accountId: "ACC-TESTNET-1",
  portfolioId: "PF-GRID",
  reportingCurrency: "USDT",
  symbolAssets: { BTCUSDT: { base: "BTC", quote: "USDT" } },
  generatedAt: "2026-07-23T00:00:00Z",
};

const order = (overrides = {}) => ({
  id: "ORD-1",
  executionId: "EXE-1",
  botId: "BOT-abc",
  symbol: "BTCUSDT",
  exchangeOrderId: "111",
  clientOrderId: "aegis-BOT-abc-EXE-1-0",
  gridIndex: 0,
  side: "BUY",
  price: "63000.00",
  quantity: "0.001",
  status: "FILLED",
  createdAt: "2026-07-20T10:00:00Z",
  updatedAt: "2026-07-20T10:05:00Z",
  filledQuantity: "0.001",
  avgFillPrice: "62950.10",
  commission: "0.0629",
  commissionAsset: "USDT",
  ...overrides,
});

test("only FILLED orders reach the ledger", () => {
  const result = buildGridLedgerExport(
    [order(), order({ id: "ORD-2", clientOrderId: "c2", status: "OPEN" })],
    options,
  );
  assert.equal(result.version, GRID_LEDGER_EXPORT_VERSION);
  assert.equal(result.sourceRowCount, 1);
  assert.equal(result.fills.length, 1);
  assert.equal(result.rejected.length, 0);
});

test("a fill carries the real execution price, not the limit price", () => {
  const [fill] = buildGridLedgerExport([order()], options).fills;
  assert.equal(fill.price, "62950.10", "must use avg_fill_price");
  assert.notEqual(fill.price, "63000.00");
  assert.equal(fill.quantity, "0.001");
  assert.equal(fill.fee, "0.0629");
  assert.equal(fill.side, "buy");
});

test("the bot id becomes the strategy id so attribution works", () => {
  const [fill] = buildGridLedgerExport([order()], options).fills;
  assert.equal(fill.strategyId, "BOT-abc");
});

test("the idempotency key is the deterministic clientOrderId", () => {
  const once = buildGridLedgerExport([order()], options);
  const twice = buildGridLedgerExport([order(), order()], options);
  assert.equal(once.fills[0].externalId, "aegis-BOT-abc-EXE-1-0");
  // Re-exporting the same window yields the same key, so the ledger's own
  // idempotency check collapses the duplicate rather than double-counting.
  assert.deepEqual(
    twice.fills.map((fill) => fill.externalId),
    [once.fills[0].externalId, once.fills[0].externalId],
  );
});

test("a FILLED row with no execution detail is rejected, never estimated", () => {
  // This is the state of production today: migration 0005 is not applied, so
  // the columns are absent. Exporting the LIMIT price with a flat fee estimate
  // would silently poison the track record.
  const result = buildGridLedgerExport(
    [order({ filledQuantity: undefined, avgFillPrice: undefined })],
    options,
  );
  assert.equal(result.fills.length, 0);
  assert.equal(result.rejected[0].reason, "MISSING_FILL_DETAIL");
  assert.match(result.rejected[0].detail, /migration 0005/);
});

test("a commission in a non-reporting asset is rejected pending an approved mark", () => {
  for (const asset of ["BNB", "BTC", "MIXED"]) {
    const result = buildGridLedgerExport([order({ commissionAsset: asset })], options);
    assert.equal(result.fills.length, 0, `${asset} must not pass through`);
    assert.equal(result.rejected[0].reason, "UNVALUABLE_COMMISSION_ASSET");
  }
});

test("a zero commission in another asset is still valuable", () => {
  // Nothing to convert, so there is nothing to fail closed on.
  const result = buildGridLedgerExport(
    [order({ commission: "0", commissionAsset: "BNB" })],
    options,
  );
  assert.equal(result.fills.length, 1);
  assert.equal(result.fills[0].fee, "0");
});

test("non-numeric or non-positive execution detail is rejected", () => {
  for (const bad of [{ avgFillPrice: "0" }, { filledQuantity: "-1" }, { avgFillPrice: "abc" }, { commission: "x" }]) {
    const result = buildGridLedgerExport([order(bad)], options);
    assert.equal(result.fills.length, 0, JSON.stringify(bad));
    assert.equal(result.rejected[0].reason, "INVALID_NUMERIC");
  }
});

test("an unmapped symbol is rejected rather than guessed", () => {
  const result = buildGridLedgerExport([order({ symbol: "ETHUSDT" })], options);
  assert.equal(result.fills.length, 0);
  assert.equal(result.rejected[0].reason, "MISSING_SYMBOL_MAPPING");
});

test("fills are ordered deterministically", () => {
  const result = buildGridLedgerExport(
    [
      order({ id: "ORD-2", clientOrderId: "b", updatedAt: "2026-07-20T12:00:00Z" }),
      order({ id: "ORD-1", clientOrderId: "a", updatedAt: "2026-07-20T09:00:00Z" }),
    ],
    options,
  );
  assert.deepEqual(
    result.fills.map((fill) => fill.externalId),
    ["a", "b"],
  );
});

// The golden file is the contract with the Python importer
// (tests/test_fund_grid_ledger_import.py reads this exact file). Guarding it
// from both sides means a schema change breaks a test here AND there, instead
// of silently breaking the track record at the seam between two languages.
test("the exported shape still matches the cross-language golden file", () => {
  const golden = JSON.parse(
    fs.readFileSync(
      path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "grid-ledger-export.golden.json"),
      "utf8",
    ),
  );
  const sell = order({
    id: "ORD-2",
    clientOrderId: "aegis-BOT-abc-EXE-1-1",
    gridIndex: 1,
    side: "SELL",
    exchangeOrderId: "112",
    price: "63500.00",
    avgFillPrice: "63510.25",
    commission: "0.0635",
    updatedAt: "2026-07-20T11:30:00Z",
  });
  const produced = buildGridLedgerExport([order(), sell], options);
  assert.deepEqual(produced, golden);
});
