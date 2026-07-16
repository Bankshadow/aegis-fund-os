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
  the currently failing Cloudflare Git-clone integration. Remote GitHub push
  succeeded to `Bankshadow/aegis-fund-os` branch `codex/cloudflare-release`;
  the workflow now reports a skipped deployment instead of failing while those
  user-created GitHub secrets are absent. `main` is being established as the
  production branch. `main` is now the GitHub default branch and its first
  automation run passed (2026-07-16); it will deploy only after both secrets
  are configured. Both secrets were configured and production deployment
  succeeded at `https://aegis-fund-os.bankshadow30.workers.dev` (2026-07-16).
- Binance Spot Testnet cloud connection prepared (2026-07-16): the deployed
  probe now accepts only same-origin HTTPS requests, remains read-only, and
  GitHub Actions can set the two Binance Testnet credentials as Worker secrets.
  It awaits user-created `BINANCE_TESTNET_API_KEY` and
  `BINANCE_TESTNET_API_SECRET` GitHub secrets; no mainnet credential is allowed.

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

- Added verified Loop snapshot CLI (2026-07-16):
  `python -m dynamic_grid.loop_cli` accepts only explicit memory, drift queue,
  paper-review ledger and output paths. It verifies all three evidence sources
  before atomic output replacement, preserves an existing snapshot when source
  integrity fails, and exposes no strategy mutation, approval or order command.
  Four focused CLI tests pass.

- Projected independent paper reviews into Loop snapshots and Aegis
  (2026-07-16): snapshots now verify the review ledger, expose review-chain
  integrity/hash/counts, maker, reviewer, rationale and paper-only decision,
  and count approved/rejected/pending reviews. The Aegis validator rejects
  self-review and review-to-experiment hash mismatches; Strategy Lab displays
  review evidence read-only. Snapshot/review tests, frontend tests (9/9),
  TypeScript, production build and full gate pass. Next Loop task: CLI for
  verified snapshot export.

- Added independent paper-review decision ledger (2026-07-16): each experiment
  contract now declares a maker; only deterministic `paper_review` verdicts are
  eligible, maker/reviewer equality is rejected case-insensitively, rationale
  is required, and one final `approved_for_paper` or `rejected` decision is
  bound to the experiment record hash in a separate append-only SHA-256 chain.
  Reviews are revalidated against experiment memory on every read and there is
  no live decision. Six review tests, all Loop tests and the full gate pass.
  Next Loop task: project review status into the snapshot and Aegis UI.

- Bound verified Loop lineage to Aegis Strategy Lab (2026-07-16): the page now
  reads only through the server function and renders integrity source,
  experiment/verdict counts, newest-first hypotheses, robust scores, failure
  reasons, record hashes and drift research tasks. Unconfigured and invalid
  snapshots are explicit, static registry evidence remains demo-labelled, and
  prior demo create/compare actions were removed. Frontend tests (8/8),
  TypeScript, production build and the full gate pass. Next Loop task: an
  independent paper-review decision ledger.

- Added server-only Aegis Loop-lineage reader (2026-07-16): a serializable,
  typed schema validator accepts only version-1 verified read-only snapshots
  whose mutation, approval and order capabilities are all false. The server
  function reads only `AEGIS_LOOP_SNAPSHOT_PATH`/`_JSON`, returns an explicit
  unconfigured fallback, and exposes no write operation or filesystem path to
  browser code. Frontend tests (8/8), TypeScript and production build pass;
  full strategy gate passes. Next Loop task: bind lineage to Strategy Lab UI.

- Added read-only Loop lineage snapshot exporter (2026-07-16): verified
  experiment memory and drift queue are projected to versioned, newest-first
  Aegis JSON with verdict counts, failure reasons, validation summaries, source
  hashes and explicit no-mutation/no-approval/no-order capabilities. Tampered
  memory fails closed and output replacement is atomic. Twenty-one focused
  Loop tests and the full gate pass. Next Loop task: server-only Aegis reader
  for the lineage snapshot.

- Added research-only drift monitoring (2026-07-16): declared thresholds cover
  robust-score decay, drawdown increase, execution-cost increase and data gaps;
  minimum sample size and same-dataset comparison are enforced. Alerts are
  immutable `open_research_task` drafts written to an idempotent append-only
  queue; the API contains no parameter mutation or execution operation.
  Seventeen focused Loop tests and the full gate pass. Next Loop task: export a
  read-only experiment-lineage snapshot for Aegis.

- Added one-contract Loop research runner (2026-07-16): it validates the
  preregistered contract and exact dataset mapping before evaluation, hashes
  code/data before and after the run, calls one evaluator, enforces the declared
  trial cap, and stores summarized validation evidence plus deterministic
  verdict in the hash-chained memory. Input mutation and budget overrun fail
  closed without recording a misleading result. Twelve focused Loop tests and
  the full gate pass. Next Loop task: drift monitor that may open research tasks
  but cannot change strategy parameters.

- Added append-only Loop experiment memory (2026-07-16):
  `ExperimentMemory` persists canonical JSONL records chained by SHA-256,
  requires code and named dataset hashes, rejects duplicate experiment IDs,
  and verifies the full chain before reads or appends. Tampering with prior
  hypotheses/results fails closed. Eight focused Loop tests and the full gate
  pass. Next Loop task: one-contract research runner with immutable output.

- Added fail-closed Loop Engineering foundation (2026-07-16): studied the
  referenced cwayinvestment video and Thai summary, then translated Memory +
  Agent Harness + Learning Loop into a research-only contract. Experiments now
  require a preregistered hypothesis, cash benchmark, named real datasets,
  held-out split, >=3 distinct seeds, fixed robust-score formula and bounded
  trials. Deterministic verdicts stop at independent paper review and reject
  live targets. Four focused tests and `gate/verify.ps1` pass. Next loop task:
  append-only JSONL experiment memory with code/data hashes.

- Improved Aegis external-team readiness (2026-07-16): audit fixture events
  now remain newest-first, degraded/disconnected adapter status deep-links to
  Integrations, and Access shows time-bound expiry plus a demo renewal draft.
  Sidebar already covered all 15 existing routes. Documented Cloudflare Access
  Email OTP as the required hostname-level session gate before external use;
  dashboard policy configuration remains an administrator action.
- Sanitized `fund-command-center-local/.env.example` (2026-07-16): it now
  contains placeholders only. The local `.env.local` remains ignored and was
  not inspected.

- Cloud Worker Binance Spot Testnet probe was deployed and tested through the
  hosted Integrations page (2026-07-16). Worker-secret synchronization from
  GitHub Actions succeeded, but Binance rejected the signed read-only request.
  Replace the GitHub secrets with a newly generated **Spot Testnet** key pair
  (never a mainnet key) and check any Testnet IP restriction before retrying.

- Added deterministic daily-close control (2026-07-15): NAV can lock only
  after data, prices, reconciliation, FX and fee checks pass and an independent
  reviewer differs from the maker. The Portfolio page now derives approval
  rather than allowing a manual approval bypass. Three unit tests, TypeScript,
  production build, and `gate/verify.ps1` pass.
- Implemented fund-ops post-MVP #1 partial: `ApprovedMarksFeeConverter` + Spot
  deposit/withdraw → TRANSFER; wired CLI `--mark`; tests green.
- Next fund-ops: income/funding API → `FUNDING` events.
