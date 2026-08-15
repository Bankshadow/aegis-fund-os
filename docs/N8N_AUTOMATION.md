# n8n automation: Aegis runtime watchdog

## Why this workflow

The course emphasizes Schedule Trigger, Webhook/HTTP, Edit Fields, If gates,
Aggregate, and sub-workflows. In Aegis, these patterns belong **outside** the
order path: n8n observes, normalizes, routes, and notifies; the Worker remains
the only governed runtime and no n8n node has exchange credentials.

## Implemented first workflow

Import `automations/n8n/aegis-runtime-watchdog.json`. It is disabled by default
and executes this safe path:

`Schedule (15m) -> authenticated GET status -> If attention -> disabled alert payload`

The Worker endpoint is `GET /api/automation/runtime-status`. It requires
`X-Aegis-Automation-Token` and exposes only aggregate bot/run safety data. It
cannot start, stop, sync, place, cancel, transfer, or withdraw anything.

Set these n8n environment variables (not workflow literals):

```text
AEGIS_RUNTIME_STATUS_URL=https://aegis-fund-os.bankshadow30.workers.dev/api/automation/runtime-status
AEGIS_AUTOMATION_STATUS_TOKEN=<same random value stored as the Worker secret>
```

Set the Worker secret `AEGIS_AUTOMATION_STATUS_TOKEN` separately. Keep
`GRID_TESTNET_KILL_SWITCH=true` and `GRID_CRON_ENABLED` unset during rollout.

## Acceptance checks before activating

1. GET without token returns 401; POST returns 405.
2. Manual n8n execution returns `schema: aegis.automation-status.v1` and
   `mode: SAFE_HOLD` while the kill switch is on.
3. The alert node is connected to a human notification channel only after the
   manual run is reviewed; it must never call `/api/cron/grid-sync`.
4. n8n has no Binance, broker, wallet, transfer, or withdrawal credentials.

## Next safe automations

- Daily-close report delivery: schedule -> snapshot export -> validation gate ->
  human notification. Never mutate a sealed period.
- CI failure triage: GitHub webhook -> normalize -> dedupe -> human alert.
- Reconciliation exception digest: schedule -> read-only status -> Aggregate by
  severity -> notify assigned operator.

## Native alternative (no n8n dependency)

`.github/workflows/runtime-watchdog.yml` implements the same Schedule + HTTP +
If + human-notification pattern using GitHub Actions. It polls the same
read-only endpoint every 15 minutes and deduplicates an open issue labeled
`aegis-runtime-alert`; it never calls `/api/cron/grid-sync`.

Configure these repository secrets after the Worker endpoint is deployed:

```text
AEGIS_AUTOMATION_STATUS_URL
AEGIS_AUTOMATION_STATUS_TOKEN
```

It skips safely until both exist. This is the preferred production route where
GitHub Actions is already the scheduler, because it avoids an additional n8n
service and keeps alert history with the codebase.
