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

## Realized-cycle P/L (2026-07-19)

`src/lib/grid-realized.ts::computeRealizedCycles` books realized profit only from
*completed* round trips: it pairs `FILLED` buys with `FILLED` sells one grid line
apart (arithmetic `buy + step`; geometric `buy × ratio`), FIFO, each sell used
once. A single filled leg is reported as open, never as profit. Fees use the same
0.10%/side estimate as the projection. Surfaced on the Grid Profit page as a
"Realized P/L (completed cycles)" tile plus a per-cycle table. Tests:
`test/grid-realized.test.mjs` (round trip, single open leg, NEW excluded,
non-adjacent no-pair, multiple cycles, geometric).

## Batch driver + scheduler (2026-07-19)

`src/lib/grid-reconcile.ts` holds the transport/identity-independent core:
`reconcileOneTestnetGrid` (one bot) and `reconcileAllRunningTestnetGrids` (every
RUNNING BTCUSDT testnet bot; one bot failing is isolated, never aborts the
batch). Exchange access and actor identity are injected, so both the server
functions and any scheduler share one tested path. Exposed as:

- `syncBinanceTestnetGridBot` — one bot, human-triggered ("Reconcile fills").
- `syncAllRunningTestnetGrids` — all running bots, human-triggered ("Sync all
  running" on the cockpit).
- `runScheduledGridReconciliation(env)` — fail-closed behind `GRID_CRON_ENABLED`
  (returns a no-op unless the operator sets it to `"true"`), runs under system
  actor `system:grid-cron`. Ready for a scheduler to call.

Tests: `test/grid-reconcile.test.mjs` (replenishment placed + recorded,
non-RUNNING refused, only-running-testnet filter, failure isolation).

### Automatic scheduler: external cron (2026-07-19)

Nitro's Cloudflare preset dispatches cron to the `cloudflare:scheduled` **hook**
(a Nitro plugin). This build's Nitro is abstracted by
`@lovable.dev/vite-tanstack-config`, whose `nitro` passthrough exposes only
`preset`/`output`/`cloudflare` — not `plugins`/`scanDirs` — and neither
`plugins/` nor `server/plugins/` is scanned (verified empirically). So instead of
an in-Worker cron, the loop is driven by an **external scheduler over HTTP**:

- **Endpoint** `POST /api/cron/grid-sync` — intercepted in `src/server.ts` before
  the app router (a path we fully control), reading Cloudflare bindings from
  `globalThis.__env__`. Handler `src/lib/grid-cron-endpoint.ts` is fail-closed
  twice: a 200 no-op unless `GRID_CRON_ENABLED === "true"`, and a constant-time
  `X-Grid-Cron-Secret` check against the `GRID_CRON_SECRET` Worker secret (an
  app-layer factor on top of the edge Cloudflare Access service token). Runs
  `reconcileAllRunningTestnetGrids` under `system:grid-cron`. Verified live on
  `wrangler dev`: POST → `{enabled:false}` no-op, GET → 405, `/bots` unaffected.
- **Workflow** `.github/workflows/grid-cron.yml` — `*/15 * * * *` schedule (plus
  manual dispatch) that curls the endpoint with the Access service-token headers
  and the shared secret; skips cleanly until its secrets are configured.

**Operator setup to activate:** (1) set Worker secrets `GRID_CRON_ENABLED=true`
and `GRID_CRON_SECRET=<random>`; (2) create a Cloudflare Access service token and
add a policy allowing it on the app; (3) set repo secrets `GRID_CRON_URL`,
`GRID_CRON_SECRET` (same value), `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`.
Until (1) is done the endpoint is a safe no-op. `runScheduledGridReconciliation`
(fail-closed) remains available for the in-Worker hook path if the build is ever
de-abstracted.

## Not in Phase 3

- Full fill→replenish end-to-end verification, which needs a live testnet bot
  with real fills behind a second Cloudflare Access identity.
## Execution Safety Control Plane (2026-07-23)

Every production reconciliation entrypoint now routes through
`grid-runtime-safety.ts`; the pure planner remains transport-independent for
unit tests. This is **Binance Spot Testnet only** and does not widen the
project's execution authority.

- A D1 compare-and-set lease per bot prevents a manual sync, external cron, or
  retry from placing concurrently. The holder is released in `finally`; an
  abandoned holder expires after 60 seconds by default.
- Each attempt writes a durable `grid_runtime_runs` row (`STARTED`, then
  `SUCCEEDED`/`FAILED`) with actor, holder, reason and placement count.
- `GRID_MAX_REPLENISHMENTS_PER_RUN` caps newly placed orders before the first
  placement. `0` is a valid emergency setting that permits read/reconciliation
  but no replenishment.
- `GRID_TESTNET_KILL_SWITCH=true` blocks all reconciliation placement before a
  lease or exchange call. Per-bot controls count failures; at
  `GRID_MAX_CONSECUTIVE_FAILURES` (default 3), the bot is paused and gets a
  hash-chained `runtime.safety_halted` audit event.
- Migration `0006_grid_runtime_safety.sql` is required before activating the
  updated runtime. Apply it to the same D1 database as migrations 0001-0005;
  keep `GRID_CRON_ENABLED` unset until it is applied and the new tests/build
  have passed.

Relevant tests: `test/grid-runtime-safety.test.mjs` covers global kill switch,
concurrent lease denial, durable success/failure records, and the per-run
placement budget.

### Hardening follow-up (2026-07-23, five-pass review)

1. The lease is now renewed before **each** replenishment and defaults to 120
   seconds, preventing a long multi-order run from silently outliving its lock.
2. An automatic breaker can be cleared only through the governed server
   function with a non-empty recovery reason. Clearing it appends
   `runtime.safety_resumed`; it deliberately does not restart the paused bot.
3. Status evidence must carry a valid, non-future `checkedAt` within
   `GRID_MAX_STATUS_AGE_SECONDS` (30 by default), otherwise placement is
   blocked and the failed run is recorded.
4. The open-order cap (`AEGIS_MAX_OPEN_ORDERS`, default 250) is checked again
   immediately before each placement, accounting for orders already placed in
   the same run. The cockpit exposes failure count/halt reason and recent run
   records are returned by its governed read API.
5. Adversarial coverage now includes stale/future evidence and lease-renewal
   loss, in addition to the original kill-switch, concurrent-lease and budget
   cases.

## Runtime graph classification (2026-07-23, L3 additive)

Pure helpers in `src/lib/grid-runtime-graph.ts` classify reconcile summaries
into `ok | deferred | mismatch | error` and expose `shouldContinueReconcileLoop`
for optional loop-until-dry planners. Cron / sync-all attach an additive
`fleet` summary; they still run **one pass per bot** by default.

### Persist route (migration 0007)

`grid_runtime_runs` stores `route_severity`, `route_action`, `work_remaining`,
and `deferred` when a run finishes (success or failure). The cockpit reads these
via `listRecentRuntimeRuns`. Apply `0007_grid_runtime_route.sql` to the same D1
database as 0001–0006 before relying on the new columns in production.

### Opt-in dry-loop

Set `GRID_RECONCILE_DRY_LOOP=true` to allow additional safe passes per bot while
deferred work remains. Caps: `GRID_RECONCILE_DRY_ROUNDS` (default 1) and
`GRID_RECONCILE_MAX_ROUNDS` (default 3, hard max 5). Each pass still goes through
`reconcileTestnetGridSafely` (lease + durable run). Mismatch/error stops the
loop and demands operator review. Unset keeps the historical one-pass behavior.

Fleet responses include additive `telemetry` (`avgPassesPerBot`, `stopReasons`,
`backlogStillDeferred`). Measurement playbook: `docs/DRY_LOOP_MEASUREMENT.md`.

Agent harness modules are never imported here.

### Migration status (2026-07-23)

Remote D1 `GOVERNANCE_DB` has migrations **0004–0007** applied (including route
columns and runtime safety tables that were previously pending). Local D1 also
has `0007`. Confirm with `npx wrangler d1 migrations list GOVERNANCE_DB --remote`.
