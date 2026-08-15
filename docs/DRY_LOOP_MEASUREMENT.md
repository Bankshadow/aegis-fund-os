# Dry-loop measurement (opt-in)

Measure before leaving `GRID_RECONCILE_DRY_LOOP=true` on. Default stays **off**.

## Prerequisites

- Migrations **0004–0007** applied on remote D1 `GOVERNANCE_DB`
  (verified 2026-07-23: remote list shows no pending migrations).
- Testnet bots can reconcile; placement still behind kill switch / lease / budget.

## Arm a measurement window

Worker secrets / `.dev.vars` (local):

```text
GRID_RECONCILE_DRY_LOOP=true
GRID_RECONCILE_DRY_ROUNDS=1
GRID_RECONCILE_MAX_ROUNDS=3
```

Keep `GRID_MAX_REPLENISHMENTS_PER_RUN` at the current production value (default 8).
Do **not** raise maxRounds first if deferred backlog is the problem — raise the
per-run placement budget instead.

## What to read

Sync-all / cron JSON now includes additive `telemetry`:

| Field | Meaning |
|---|---|
| `avgPassesPerBot` | Cost multiplier vs single-pass |
| `maxPasses` | Worst bot in the batch |
| `stopReasons` | `dry` / `max_rounds` / `operator_review` / `error` / `single_pass` |
| `deferredEnds` | Bots that still ended deferred |
| `backlogStillDeferred` | Hit round cap while deferred → budget too low |

Also check cockpit **Recent runtime routes** (`route_severity`, `deferred` columns
from migration 0007).

## Decision rule

| Observation | Action |
|---|---|
| `avgPassesPerBot` ≈ 1 and rare deferred | Keep dry-loop off (no gain) |
| Deferred drains within 2–3 passes, no rate-limit errors | Leave dry-loop on with current caps |
| `backlogStillDeferred=true` often | Raise `GRID_MAX_REPLENISHMENTS_PER_RUN`, not maxRounds |
| Mismatch/error climbs | Turn dry-loop off; investigate ledger vs exchange |

## Disarm

Unset `GRID_RECONCILE_DRY_LOOP` or set it to any value other than `true`.

## Apply migrations (operator)

```powershell
cd fund-command-center-local
npx wrangler d1 migrations apply GOVERNANCE_DB --local
npx wrangler d1 migrations apply GOVERNANCE_DB --remote
npx wrangler d1 migrations list GOVERNANCE_DB --remote
```
