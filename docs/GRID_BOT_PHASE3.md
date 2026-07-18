# Grid Bot Phase 3 — Runtime Loop (Fill Tracking + Replenishment)

> Builds on Phase 2 governance and the Binance Spot Testnet execution slice.
> Testnet only. No mainnet, transfer, or withdrawal path exists.

## What it does

One iteration of the grid runtime loop polls the exchange, records fills against
the durable order ledger, and places the paired replenishment order that keeps
the grid cycling:

- a filled **BUY** places a **SELL** one grid line up (sell what was just bought),
- a filled **SELL** places a **BUY** one grid line down (buy it back cheaper),
- both at the same base quantity as the filled order.

## Acceptance criteria

1. A ledger order still open on the exchange is left unchanged (only its status
   is synced, e.g. `NEW` → `PARTIALLY_FILLED`).
2. A fully filled order (absent from open orders **and** backed by a trade) is
   marked `FILLED` and triggers exactly one replenishment.
3. A replenishment price is always an existing grid line (a member of the ladder
   derived from the ledger), so grid geometry can never drift.
4. A fill at the extreme edge of the grid has no adjacent line and places nothing.
5. An order absent from the exchange with **no** matching trade is marked
   `RECONCILIATION_REQUIRED` and never triggers a replenishment (fail closed).
6. Replenishment client-order ids are deterministic, so a replayed poll places no
   duplicate order.
7. A poll that found no change writes nothing (no empty audit event, no version
   churn).
8. A replenishment placement that fails leaves its source fill un-terminal so the
   next poll retries it; the error is surfaced only after the ledger is made
   consistent — no orphaned position, no lost replenishment.
9. Only a `RUNNING`, `APPROVED`, `BTCUSDT`, `BINANCE_TESTNET` bot can reconcile,
   and only with a verified Cloudflare Access identity (fail-closed).

## Components

| Layer | Location |
|---|---|
| Pure planner | `src/lib/grid-runtime.ts` — `planGridReconciliation`, `replenishmentClientOrderId` |
| Single-order placement | `src/lib/binance-testnet-execution.ts` — `placeSingleTestnetOrder` |
| Atomic persistence | `src/lib/grid-bot-repository.ts` — `recordGridSync` (marks fills/reconciliation/status, inserts paired orders under the active execution, appends one `testnet.grid_synced` hash-chained event, bumps version) |
| Governed server fn | `src/lib/grid-bot-governance.functions.ts` — `syncBinanceTestnetGridBot` |
| UI trigger | `src/routes/bots_.$botId_.profit.tsx` — "Reconcile fills" (shown only for a RUNNING testnet bot) |

## Design notes

- **Human-triggered per iteration.** No automatic cron or Durable Object is wired.
  An always-on autonomous scheduler is an unmade governance decision; the loop is
  driven one step at a time from the Grid Profit page (or by calling the server
  function directly).
- **Ladder from the ledger.** Replenishment targets are chosen from the sorted
  distinct order prices, so no exchange-info refetch or geometry recomputation is
  needed and the ladder stays stable across cycles.
- **Idempotency.** Deterministic `aegis-r-<hash>` client ids plus the D1 unique
  constraints on `client_order_id` and `(bot_id, exchange_order_id)` make a
  replayed sync safe.

## Tests

- `test/grid-runtime.test.mjs` — 8 planner tests (no-change, buy→sell up,
  sell→buy down, boundary, reconciliation, idempotent replay, partial fill,
  terminal rows never reprocessed).
- `test/grid-runtime-repository.test.mjs` — 4 persistence tests (fill+placement
  batch composition, no-change no-op, non-RUNNING guard, no-active-execution
  fail-closed).

## Not in Phase 3

- Automatic scheduling (cron / Durable Object).
- Realized-cycle P/L accounting (still projection-only via `grid-profit.ts`).
- Full fill→replenish end-to-end verification, which needs a live testnet bot
  with real fills behind a second Cloudflare Access identity.
