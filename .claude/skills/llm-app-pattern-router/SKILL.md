---
name: llm-app-pattern-router
description: >-
  Route requests against the awesome-llm-apps catalog patterns onto this Grid
  Trading / Fund OS stack. Use when the user mentions awesome-llm-apps,
  Shubhamsaboo templates, scope creep detector, commit archaeologist, project
  graveyard, RAG agent demos, always-on agents, multi-agent teams, or asks
  whether to adopt an LLM app template. Do not clone the catalog into the repo
  or treat finance demo agents as a trading stack.
---

# LLM app pattern router (repo-mapped)

Source catalog: [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps)
(100+ Apache-2.0 agent / RAG / MCP templates + a few installable agent skills).

This skill is a **filtration map**, not a vendored copy of the catalog.
Most templates are demos. Adopt doctrine and offline hygiene skills only when
they tighten our existing stack.

## Core reframe

- Catalog ≠ constitution. Our seats, gate, and trading nevers win.
- Prefer **one** mapped pattern over installing a Swarm/Crew demo.
- Done stays an environment fact (`gate/verify.*`, declared check,
  `ValidationGate`) — never a Streamlit demo that “looks smart.”

## Never

- Never live-order or promote catalog finance/investment/VC agents as Fund OS
- Never lower `ValidationGate` / skip `gate/verify.*` because a template “has evals”
- Never install self-improving skill loops that rewrite `AGENTS.md` / skills unattended
- Never spawn multi-agent teams / fan-outs unless `ROUTING.md` triggers fire
  (BUILD 7 / 9 deferred)
- Never treat RAG over PDFs as a substitute for `docs/VALIDATION_LOG.md` evidence

## Adopt vs defer vs reject

| Catalog bucket | Verdict | Map here |
|---|---|---|
| **Agent Skills → scope-creep-detector** | Adopt (doctrine + optional install) | Pre-PR / pre-commit scope check; keep / split / justify |
| **Agent Skills → commit-archaeologist** | Adopt (doctrine + optional install) | Before risky rewrite of grid/runtime/governance code |
| **Agent Skills → project-graveyard** | Optional (personal ops) | Outside this monorepo; necromancer check before new side projects |
| **Agent Skills → advisor-orchestrator-worker** | Reject as duplicate | Already: `ROUTING.md`, `agent/executor_advisor.py`, `model-router` |
| **Agent Skills → self-improving-agent-skills** | Defer / reject default | Skills change only with human + gate; no auto-mutate constitution |
| **Always-on agents** (HN brief, release radar) | Pattern only | Prefer existing read-only watchdog: `/api/automation/runtime-status` + `.github/workflows/runtime-watchdog.yml` — no order path |
| **Trust-gated multi-agent research** | Pattern only | Human approve before live mutate; audit via D1 / logs — not a new agent framework |
| **Starter / Advanced finance & investment agents** | Reject for trading | Research stays Dual 75/25 + ValidationGate; Yahoo/Grok stock demos ≠ evidence |
| **Multi-agent teams / swarms** | Defer | BUILD 7/9; solo research pace |
| **RAG tutorials** | Defer | Use repo docs + code search; add RAG only if doc retrieval becomes a measured bottleneck |
| **MCP demo agents** | Defer | Use Cursor MCP already wired; don’t add travel/Notion toy servers |
| **Voice / generative UI / game agents** | Reject | Out of mission |
| **Fine-tune / token-opt toys** | Defer | Cost control via `model-bench` + effort-before-model |

## Pattern A — Scope creep (pre-ship)

When a change may have grown past its intent (especially mixed Fund OS + research
+ docs + migrations):

1. State intent in one line (user’s words, or ask).
2. Classify touched paths: in-scope vs likely creep (deps, API renames, CI/config,
   oversized hunks, formatting-only).
3. Disposition every creep candidate: **keep** / **split** / **justify**.
4. Prefer **split** when ambiguous. Ask before staging/committing splits.
5. Then `ship-gate` / `gate/verify.ps1`.

Optional upstream install (scripts stay outside this repo unless you ask to vendor):

```bash
npx skills add https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/scope-creep-detector
```

Without the script: same keep/split/justify table from `git status` + `git diff`,
still grounded in stated intent.

## Pattern B — Commit archaeology (pre-rewrite)

Before deleting or “simplifying” surprising grid/runtime/governance code:

1. Find introducing commit + later behavior-changing edits for the region.
2. Note co-changed companions (coupling clues, not proven deps).
3. Separate blame ownership from original authorship.
4. Label confidence; quote message signals (workaround / temporary / revert).
5. Only then propose an edit plan; human confirms.

Optional:

```bash
npx skills add https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/commit-archaeologist
```

## Pattern C — Always-on = read-only scout

Catalog always-on agents schedule briefs and actions. Here the allowed shape is:

- Poll **read-only** status
- Open an issue / notify on halt or failed run
- Fail closed without secrets
- **No** cron that places, cancels, transfers, or withdraws

If a template wants write-side automation, stop and use `agent-build-loop`
approval rules + constitution.

## Pattern D — Necromancer (before new toys)

If the user proposes a new LLM app / agent framework / parallel research OS:

1. Check this repo’s existing stack (`docs/AGENT_STACK.md`, skills, Fund OS).
2. Ask whether we already have ≥60% of it (router, gate, watchdog, graph L2/L3).
3. Prefer resurrect/extend over scaffolding a CrewAI/AG2/Streamlit twin.

## How this sits with sibling skills

| Need | Skill |
|---|---|
| Which model/seat | `model-router` / `ROUTING.md` |
| Build loop + human check | `agent-build-loop` |
| Promote/kill research | `quant-research-pipeline` |
| Capital / layers | `quant-portfolio-allocation` |
| Stuck | `stuck-protocol` |
| Done? | `ship-gate` |
| Catalog adopt/reject | **this skill** |

## Invoke

```
Use llm-app-pattern-router: should we adopt <template or idea>?
```

```
Use llm-app-pattern-router scope-creep on this diff; intent: "<one line>"
```

```
Use llm-app-pattern-router archaeology on <path>[:lines] before rewrite
```
