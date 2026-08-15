# Archestra adoption boundary

Reviewed source: [`archestra-ai/archestra`](https://github.com/archestra-ai/archestra)
@ `fc88f7c0` (2026-08-08), 4.1k stars, TypeScript/Rust, Postgres + Kubernetes.
Revision pinned in [`archestra-source.lock.json`](../integrations/archestra-source.lock.json).

## What it is

An enterprise AI platform: an LLM gateway that proxies Anthropic / OpenAI /
Azure / Bedrock / DeepSeek with cost limits and routing, an MCP gateway and
registry with OAuth on-behalf-of token handling, an agent runtime with sandboxed
code execution and sub-agent delegation, Slack/Teams/email chat surfaces, a RAG
knowledge base, SSO (OIDC, SAML, Okta, Entra) with RBAC, OpenTelemetry traces
and Prometheus metrics. Docker/Helm/Terraform deployment.

## Two independent reasons the code cannot be adopted

**1. The licence forbids it here, specifically.** `LICENSE.md` is
**AGPL-3.0-only by default**, with a proprietary Enterprise licence layered over
`ee/` directories and `.ee.*` files. There is no MIT/Apache carve-out anywhere
in the repository.

AGPL matters more for us than it would for most readers, because of §13: making
a modified work available to users **over a network** is treated as
distribution. We run `aegis-fund-os.bankshadow30.workers.dev` as a public,
unauthenticated Worker (Cloudflare Access was deleted at the user's request on
2026-07-16). Linking any AGPL code into that Worker would oblige us to offer the
complete corresponding source of the combined work to every visitor. That is a
decision about the whole repository, not about one module — so the answer to
"should we copy it in as a module?" is **no, not any of it**, and not because
the code is bad.

Contrast [`docs/TVSCREENER_ADOPTION.md`](TVSCREENER_ADOPTION.md): that source
was Apache-2.0, and the reason we still did not vendor it was engineering, not
licensing. Here licensing decides it before engineering gets a turn.

**2. The scale is wrong by two orders of magnitude.** Postgres, Kubernetes,
Helm, SSO/RBAC, OpenTelemetry, a multi-provider LLM proxy and an MCP registry
are the right answer for an organisation running many agents for many people
with an audit obligation. This is one researcher, one machine, one Worker, and
a `ROUTING.md`. Standing that platform up would be more infrastructure than the
thing it guards.

**Doctrine, however, is not copyrightable and costs nothing to adopt.** That is
what was taken.

## Adopted — the doctrine, reimplemented at our scale

Archestra's stated security position is: enforce **deterministic, context-aware
allowlists outside the guarded thing**, rather than relying on "fuzzy,
probabilistic LLM prompts" that jailbreaks defeat. Their examples are filesystem
allowlists (`~/coding/project/src/**` allowed, `**/.env` and `**/.ssh/**`
blocked) and recipient allowlists (`send_email` only to `*@yourdomain.com`),
enforced at the proxy before a request reaches a model.

We already had the mechanism and were missing the policy. `gate/eval_gate.py`
opens with *"Deterministic checks only — never calls a model"* — that is the
same idea, and it runs in `gate/verify.ps1`. So the adoption is three new cases
there, not a new subsystem.

### 1. A declared egress allowlist

Before this, hosts were pinned as string constants in eight separate files with
nothing to stop a ninth appearing — `grep allowlist` matched only prose.
[`integrations/egress-allowlist.json`](../integrations/egress-allowlist.json)
now declares all **21** hosts the source can reach, each with a purpose, an
access class (`read` / `sandbox-write` / `asset` / `reference` / `fixture`), and
an `untrusted_content` flag. `gate/egress_scan.py` walks the tree and fails the
gate on any host that is not declared.

Two things the scan found while being written, both now regression-tested:

* **It missed scheme-less hosts.** `webull-sandbox.server.ts` pins
  `WEBULL_SANDBOX_HOST = "api.sandbox.webull.com"` with no `https://`, which a
  URL pattern walks straight past. A second pattern now matches
  `*HOST|URL|ENDPOINT|ORIGIN|DOMAIN*` constants; matching our naming convention
  rather than guessing at TLDs keeps it precise enough to stay unmuted.
* **It read `.pnpm-store/`**, which mirrors our own sources back, so every
  finding named a path nobody could fix. Pruned, along with the other vendored
  and generated trees.

A line-level `# egress-scan: fixture` pragma exists because the scan's own tests
must plant realistic hosts to prove detection works. Suppressions are counted
and printed, so a silent opt-out cannot accumulate.

### 2. No live-trading host may be declared

`live_trading: false` is required on every entry, and a case fails the gate if
any entry sets it true. This restates the constitution as **data**: the moment
someone declares a real venue, the gate stops them — not the deploy afterwards.

### 3. The lethal-trifecta guard on the untrusted-content path

The trifecta (Simon Willison): private data + untrusted content + external
communication. Audited honestly, we have two exposures and they are very
different.

**The Worker holds all three capabilities.** Private data — Binance Testnet
credentials and the D1 governance database. Untrusted content — nine RSS and
Statuspage feeds, now flagged `untrusted_content: true` in the policy. External
communication — the Testnet placement path in `grid-runtime-safety.ts`.

**But it is not vulnerable, and the reason is worth naming precisely.** The
trifecta is a *prompt-injection* threat model: it needs a model in the path that
attacker-controlled text can instruct. News scoring is deterministic keyword
rules in 855 lines of `news-risk.ts`, with no model anywhere — verified, zero
provider markers. Keyword rules cannot be argued with by their input.

That protection was a **side effect**: the board was built LLM-free to avoid
per-item cost. An accidental protection is one refactor from gone, so
`untrusted_content_path_has_no_model` now pins it. Adding LLM summarisation to
the news board is exactly the change that would complete the trifecta, and it
will now fail the gate rather than ship quietly.

**The agent — Claude Code in this repository — genuinely has all three, and no
code fixes that.** It reads untrusted content (this session alone fetched GitHub
APIs, a TradingView endpoint and web search results), holds private data (the
repo, `.env.local`), and can communicate externally (Bash, network, `git push`).
The mitigations are the harness permission classifier — which blocked the
scheduled-task registration in this same session — the project laws, and human
review. Stated here rather than papered over: it is a real residual risk, and
the honest control is that no unattended agent loop has write access to money.

## Feature-by-feature verdict

| Archestra feature | Verdict | Reason |
| --- | --- | --- |
| Deterministic allowlist doctrine | **adopted** | Three cases in the existing gate; policy in `egress-allowlist.json`. |
| Lethal-trifecta threat model | **adopted** | Audited both exposures; pinned the news path as LLM-free. |
| Live-venue prohibition as data | **adopted** | `live_trading` flag, gate-enforced. |
| Any Archestra source code | **rejected** | AGPL-3.0 + public Worker = §13 source-disclosure on the whole combined work. |
| LLM gateway / multi-provider proxy | rejected | We route by doctrine (`ROUTING.md`) and cap advisor consults at 3, already gate-checked. One user, one seat. |
| MCP gateway + registry, OAuth on-behalf-of | rejected | MCP servers here are per-session and user-authorised; there is no fleet to broker for. |
| Agent runtime, scheduled + webhook triggers | rejected | Covered: a Scheduled Task for snapshots, a read-only GitHub watchdog, and the Worker cron. Adding a runtime adds an execution path the constitution forbids. |
| Sandboxed code execution | not applicable | Nothing here executes model-generated code. |
| SSO / RBAC | rejected | Cloudflare Access was deliberately deleted; a single operator has no roles to separate. |
| RAG knowledge base | rejected | Cognee already holds trading event memory; a second store would split it. |
| Dual-LLM (privileged + quarantined) | rejected, but recorded | The correct answer *if* an LLM ever reads the news feeds. Cheaper today: keep the model out of that path entirely, which the gate now enforces. Revisit only if a model must read untrusted text. |
| OpenTelemetry / Prometheus | rejected | `gate/verify.ps1` and the run ledger are the observability at this scale. |
| Helm / Terraform / k8s | rejected | One Cloudflare Worker. |

## Commands

```bash
python gate/egress_scan.py
```

```bash
python -m unittest tests.test_egress_policy
```

## Reopening conditions

Adopting Archestra code — not doctrine — requires either an Enterprise licence
or accepting AGPL §13 for the entire deployed Worker. Adopting the dual-LLM
pattern requires first proposing a reason for a model to read the feeds, since
the current control is that none does.
