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
