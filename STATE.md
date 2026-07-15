# STATE.md — Session Memory

> Write before walking away. Read at session start.
> Stages: Fail → Investigate → Verify → Distill → Consult (next session).

## Verified facts

- Recommended research config: Dual 75/25 rule-based + percentile-rank regime (see HANDOFF).
- E20 RL walk-forward failed (3/6 = 50%) — RL not production-ready on BTC/4h.
- E23 dual tune: best Line-B attempt so far (mean robust −0.0078, delta +0.0301) — still not > 0 / not promoted.
- E24 separate short_cfg: FAIL (−0.0205) — worse than E23, especially ETH.
- E25 conservative geometry: FAIL (−0.0154) — better DD but still < cash; C2 miss.
- Live trading and third-party capital: forbidden until Phase 3 gates clear.
- Agent stack gate green (`gate/verify.ps1` SHIP); `run_demo.py --fast` OK (2026-07-15).

## Verified since previous handoff

- Derivatives fund-ops slice verified (2026-07-15): USDⓈ-M read-only sync maps
  funding, collateral transfers, fills, balances and remote positions; ledger
  reconciliation is idempotent and marks mismatches provisional.
- Added fixture coverage for USDⓈ-M `userTrades` → `DERIVATIVE_FILL` and clean
  internal-vs-remote position reconciliation.
- Verified 28 Python fund-ops tests, strategy gate `SHIP`, Binance signing test,
  daily-close tests, and local production build. FX/multi-currency valuation
  and persisted exception review remain next; execution remains forbidden.

## General rules

- FX valuation slice verified (2026-07-15): `ApprovedFxValuation` converts
  balances only from positive approved pair rates and fails closed when a rate
  is missing; `FundV2Store` persists deduplicated reconciliation exceptions,
  requires a different reviewer for resolution, and daily-close can persist
  open exceptions without permitting a clean close.
- Local dashboard read-only snapshot added (2026-07-15): Portfolio shows
  approved FX rates/as-of/base value; Reconciliation shows persisted exception
  records with owner/status/checker. Frontend signing tests, daily-close tests,
  production build, and strategy gate all pass.
- Added server-side `getOperationsSnapshot` read path (2026-07-15): it accepts
  only `AEGIS_OPERATIONS_SNAPSHOT_JSON` on the server, returns a typed persisted
  snapshot, and falls back explicitly to demo data when unconfigured. Portfolio
  and Reconciliation now consume this path without exposing credentials or
  execution methods to the browser bundle. Frontend tests/build and gate pass.
- Added versioned `operations_snapshot` exporter (2026-07-15): it reads the
  persisted daily report and `FundV2Store`, emits atomic JSON with FX rates,
  P/L base value, exception records, quality counts and `ready/provisional`
  status. Server function now supports `AEGIS_OPERATIONS_SNAPSHOT_PATH`.
  32 Python tests, frontend tests/build and gate pass.
- Git/Cloudflare preparation started (2026-07-16): added root `.gitignore`
  for secrets, local stores, logs, generated snapshots, Q tables and frontend
  artifacts; secret scan found no credential assignments and `gate/verify.ps1`
  remains SHIP. Git discovery shows this folder is inside a parent repository
  rooted at `C:\Users\User`, so do not stage or push until the user confirms
  whether to create a standalone repository for this project.
- Standalone repository initialized and initial commit created (2026-07-16):
  `dc2272c chore: initial dynamic grid and fund operations baseline`; active
  branch is `codex/cloudflare-release`. GitHub CLI is installed but not logged
  in, so private remote creation/push awaits `gh auth login` by the user.
- Cloudflare Workers deployment prepared and verified (2026-07-16):
  `fund-command-center-local/wrangler.jsonc` pins the `aegis-fund-os` Worker
  with `nodejs_compat`; Wrangler 4.110.0 is locked and its dry-run bundles 89
  modules successfully. The dashboard stays read-only/demo on Workers until a
  future R2-backed snapshot reader replaces the local filesystem path.
- Added GitHub Actions deployment path (2026-07-16): pushing `main` runs the
  frontend tests, builds the Worker, then deploys via `wrangler-action` with
  GitHub secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. This avoids
  the currently failing Cloudflare Git-clone integration; it remains blocked
  until a user-owned GitHub remote is created and the branch is pushed.

- Criteria before experiment; ≥3 seeds; held-out; log negatives.
- ValidationGate thresholds are not negotiable downward.
- Synthetic ≠ real evidence; no cross-scale/TF transfer without re-validation.
- Agent stack: cheap driver + Fable advisor grams; gate is final vote (`ROUTING.md`).

## Open failures

- Dual under real costs still loses to cash on robust mean (E22–E25). E23 remains best.
  Next candidates (not yet run): funding/relative only as declared A/B; or accept cash
  as Line-B default and pivot effort to fund-ops ledger.
- Fund ops: Spot fee conversion + TRANSFER sync done (2026-07-15). Still missing
  futures/Spot income → `EventType.FUNDING`; multi-currency capital FX policy.

## Lessons learned

- Memory-orchestrator stop_threshold=2 in 50-bar windows was dead-on-arrival; fixed to 1.
- Advisor inversion beats Fable-as-driver for cost; consult only on stuck signals.
- Separate short_cfg (E24) and conservative subspace (E25) both failed to clear C1 —
  geometry tweaks alone are not enough under ExecutionProfile on this 4h set.
- A verdict without a passing test row is an opinion — factory/gate doctrine.
- Approved marks (not live tickers) keep fee conversion auditable and fail-closed.

## Local Lovable migration (2026-07-15)

- Migrated the published Aegis Fund OS source from Lovable project
  `a1b62369-da01-4dda-834d-5daab87d33b3`, commit
  `af200db1b2f50788d1dc4c4f791c81a78619eab7`, into
  `fund-command-center-local/` without changing the legacy static fund-ops pages.
- Imported 86 text source/config files; binary favicon was omitted and is not
  required for compilation.
- Installed the local Node dependencies and generated `pnpm-lock.yaml`.
- Verified a production Vite/TanStack Start build and HTTP 200 smoke checks for
  all nine baseline routes.
- Completed frontend P1–P3 locally: grouped navigation plus Strategy Lab, Bots
  & Orders, Signals, Integrations, Approvals, and Access & Roles.
- New controls are interactive local-demo state only; live order submission,
  withdrawals, and third-party capital remain unavailable.
- Production build and targeted ESLint checks pass. Generated TanStack route
  manifest contains all 15 application routes.
- Next frontend cursor: authenticated API and durable persistence for read-only
  adapters, approval/audit records, and paper execution events.
- Added a local-only Binance Spot Testnet connector (2026-07-15): public time
  reachability plus HMAC-signed `GET /api/v3/account`, with sanitized metadata
  only and no order/withdrawal endpoint.
- Official HMAC vector test, ESLint, TypeScript and production build pass;
  public Testnet `/api/v3/time` responded successfully from this machine.
- Authenticated Binance status remains pending until the user adds Testnet-only
  credentials to ignored `fund-command-center-local/.env.local` and restarts
  the local server. Credentials must never be pasted into chat or source.
- Retested after credentials were added (2026-07-15): signed read-only
  `/api/v3/account` returned HTTP 401 / Binance `-2015` (invalid API key, IP,
  or permission). Verify that the key was generated in Spot Testnet, has
  `USER_DATA` access, and permits the request source IP before retrying.
- Added Hyperliquid mainnet public Info API adapter (2026-07-15): fixed
  official endpoint, localhost-only server function, and optional public
  wallet address for sanitized position/open-order counts. The adapter has no
  wallet signing, exchange, order, transfer, or withdrawal call path.
- Verified `metaAndAssetCtxs` against `https://api.hyperliquid.xyz/info`
  (232 markets), TypeScript, production build, and `gate/verify.ps1` (SHIP).
- Removed credential-like values from `fund-command-center-local/.env.example`;
  examples contain placeholders only.
- Converted the Hyperliquid adapter to Testnet-only (2026-07-15): it now
  accepts only `https://api.hyperliquid-testnet.xyz/info` and reads optional
  `HYPERLIQUID_TESTNET_WALLET_ADDRESS`. The Testnet public Info API responded
  with 210 markets; TypeScript, production build, and `gate/verify.ps1` passed.
- Read-only review of sibling `btc-short-premium-agent` (2026-07-15): its
  Binance USD-M Futures Demo connector uses `demo-fapi.binance.com`, while its
  setup verifier is stale Bybit-only. Its local/deployment envs configure a
  proxy URL but omit `BINANCE_PROXY_ENABLED`, so the client bypasses the proxy;
  this is a likely source of regional/IP failures. Do not reuse its Futures
  credentials in the Aegis Spot Testnet connector.
- Added Bybit Testnet read-only adapter (2026-07-15): fixed Testnet base URL,
  server-time check and signed Unified wallet summary only, with no order,
  transfer or withdrawal endpoint. TypeScript, production build and
  `gate/verify.ps1` passed. Direct endpoint verification from this environment
  failed DNS resolution for `api-testnet.bybit.com`; authenticate only after
  confirming DNS/network access from the actual host.

## Last session

- Added deterministic daily-close control (2026-07-15): NAV can lock only
  after data, prices, reconciliation, FX and fee checks pass and an independent
  reviewer differs from the maker. The Portfolio page now derives approval
  rather than allowing a manual approval bypass. Three unit tests, TypeScript,
  production build, and `gate/verify.ps1` pass.
- Implemented fund-ops post-MVP #1 partial: `ApprovedMarksFeeConverter` + Spot
  deposit/withdraw → TRANSFER; wired CLI `--mark`; tests green.
- Next fund-ops: income/funding API → `FUNDING` events.
