# Aegis Fund OS — Local Development

This directory is a local snapshot of the Lovable project **Aegis Operations
Studio** (`fund-command-center`) at published commit
`af200db1b2f50788d1dc4c4f791c81a78619eab7`.

## Purpose

- Continue product development without Lovable credits.
- Keep the Python/grid-trading research code isolated from the React app.
- Preserve the safety boundary: demo, paper, testnet, sandbox, and live
  read-only only. There is no live-order execution path.

## Local commands

```powershell
pnpm install
pnpm run build
pnpm run dev -- --host 127.0.0.1 --port 8940
```

The first development start can take longer while Vite optimizes dependencies.

## Cloudflare Workers deployment

This app uses SSR and TanStack server functions, so deploy it as a Cloudflare
Worker rather than a static Pages project. The committed `wrangler.jsonc`
deploys the Nitro-generated Worker (`.output/server/index.mjs`) and public
assets (`.output/public`).

1. Authenticate locally: `pnpm exec wrangler login`.
2. Confirm the target account: `pnpm run cf:whoami`.
3. Build and validate the upload without publishing: `pnpm run cf:dry-run`.
4. Publish only after the checks pass: `pnpm run deploy`.

The initial Worker intentionally has no durable data binding. On Cloudflare,
`AEGIS_OPERATIONS_SNAPSHOT_PATH` is not available because Workers have no local
filesystem. Until an R2-backed snapshot reader is added, configure a small
read-only `AEGIS_OPERATIONS_SNAPSHOT_JSON` value as a Worker secret or allow
the dashboard's explicit demo fallback. Never store exchange credentials in
`wrangler.jsonc`, Git, or a browser-exposed `VITE_*` variable.

### Automated deploys with GitHub Actions

`.github/workflows/deploy-cloudflare.yml` is deliberately independent of
Cloudflare's Git integration. After a push to `main`, it runs frontend checks,
builds the Worker, and deploys it with Wrangler. Add these repository secrets
in GitHub before merging to `main`:

- `CLOUDFLARE_API_TOKEN`: a narrowly scoped token with **Edit Cloudflare
  Workers** permission for the target account.
- `CLOUDFLARE_ACCOUNT_ID`: the target Cloudflare account ID.

Never add either value to source files, GitHub Actions workflow text, or a
`VITE_*` variable. The workflow can also be triggered manually from GitHub's
**Actions** tab.

## Verified baseline

- Production build succeeds with Vite 8 / TanStack Start.
- Original nine routes previously passed local HTTP smoke checks.
- The text source/config tree was imported from Lovable. The original binary
  favicon was not required for the build and was not copied.

## P1-P3 local implementation

- Navigation is grouped into Command Center, Trading & Research, Fund
  Operations, Governance & Reporting, and Administration.
- Added Strategy Lab, Bots & Orders, Signals, Integrations, Approvals, and
  Access & Roles as dedicated routes.
- Added interactive local-demo controls for research review, paper bot state,
  signal acknowledgement, adapter tests, four-eyes decisions, and security
  policy posture.
- All routes enforce research, paper, testnet, sandbox, or read-only copy; no
  live-order or withdrawal transport exists.
- Production build and targeted ESLint checks pass for all changed files.

## Next work

Bind the local demo screens to authenticated APIs and durable storage, beginning
with read-only adapter status, approval/audit persistence, and paper execution
events. Live execution remains out of scope.

## Binance Spot Testnet

The Integrations page now includes a real, server-side Spot Testnet connection
probe. It uses only `GET /api/v3/time` and the signed `GET /api/v3/account`
USER_DATA endpoint. Account balances are never returned to the browser; the UI
receives only sanitized connection metadata and a non-zero asset count.

1. Create Spot Testnet credentials at `https://testnet.binance.vision/`.
2. Put them in `.env.local` on this machine:

```dotenv
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_API_SECRET=your_testnet_secret
BINANCE_TESTNET_BASE_URL=https://testnet.binance.vision
```

3. Restart the local development server.
4. Open **Administration → Integrations → Binance → Test**.

Never paste API credentials into chat, browser forms, screenshots, source code,
or committed files. Aegis contains no order or withdrawal endpoint, even when a
remote Testnet key reports trade permission.
