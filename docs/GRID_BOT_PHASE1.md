# Grid Bot Phase 1

## Architecture assessment

- React 19, TanStack Router/Start, Vite/Nitro and Cloudflare Workers.
- File routes use the shared Aegis shell and design tokens.
- Server reads use `createServerFn`; Binance credentials remain server-only.
- No D1, Durable Object, Queue or Workflow binding exists yet.
- Risk, approvals, audit and parts of reconciliation are currently page-local demo projections.

## Phase 1 impact

Retained: all existing modules, shell, navigation, controls and Binance signing/read-only probe.

Modified: `/bots`, package dependency/lockfile and generated route tree.

Created: exact-decimal bot domain engine, status components, five-step creator, bot detail,
active-order and event routes, and focused tests.

## Delivered routes

- `/bots`
- `/bots/new`
- `/bots/$botId`
- `/bots/$botId/orders`
- `/bots/$botId/events`

## Control boundary

Demo and Paper are explicit simulations. Binance Testnet is read-only in this phase. No
exchange order transport, browser timer, secret exposure or live-trading capability was added.
Material UI commands state that they are Phase-1 local commands; approval and reconciliation
actions route users toward the existing governance model without claiming durable execution.

## Remaining phases

Durable state, shared approval/risk/audit services, adapter abstraction, paper fills, idempotent
cycles, Testnet order transport, user data stream, reconciliation recovery and Durable Object or
Workflow orchestration remain Phase 2–5 work and require separate acceptance gates.
