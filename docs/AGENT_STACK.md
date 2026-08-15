# Agent Stack — adapted from Avid (Fable 5 + GPT-5.6)

Source: [Av1dlive status/2076705482904101136](https://x.com/Av1dlive/status/2076705482904101136)
Article: *AI Agent Stack everyone must use with GPT 5.6 + Fable 5 (Builder's Guide)*

Mapped onto this Grid Trading repo. We adopt the **doctrine and early builds**;
fan-outs / factory / swarm install only when their trigger conditions appear
(see `ROUTING.md`).

## Three principles

1. Route at boundaries; **effort before model**
2. Nothing grades its own homework (writer ≠ advisor ≠ reviewer; gate is a script)
3. Done is an **environment fact** (tests / gate / ValidationGate) — never model opinion

## Evidence Ladder ↔ this system

| Rung | Avid idea | Here |
|---|---|---|
| 0–1 | Engines + constitution | `AGENTS.md`, `CLAUDE.md`, model-bench skill |
| 2 | Deterministic gate | `gate/verify.ps1`, `gate/eval_gate.py`, `ValidationGate` |
| 3 | Heartbeat loop | `loop/ralph.ps1`, `loop/TASKS.md` |
| 3 | Advisor inversion | `agent/executor_advisor.py` (Sonnet/Sol driver, Fable grams) |
| 3 | Router | `ROUTING.md`, `agent/router.py` |
| 4 | Standing goals / compost | `STATE.md` + weekly review (manual for now) |
| 5 | Human signature | You — last commit before merge; compost proposals |

## Build checklist (repo status)

| Build | Status | Path |
|---|---|---|
| 0 Engines / bench | done | `.claude/skills/model-bench/` |
| 1 Constitutions | done | `AGENTS.md`, `CLAUDE.md` |
| 2 Gate | done | `gate/` |
| 3 Heartbeat | done | `loop/` |
| 4 Router | done | `ROUTING.md`, `agent/router.py` |
| 5 Advisor inversion | done | `agent/executor_advisor.py` + stuck-protocol skill |
| 6 Two-lane review | optional | use `/codex:review` when available |
| 7 Fan-outs | deferred | install only on trigger |
| 7.5 Graph contracts | done (scaffold) | `agent/graph_contracts.py`, `agent/graph_ops.py` — L2 only; never imports runtime |
| 7.5a First diamond | done | `python -m agent.diamonds.runtime_safety_review` — correctness/concurrency/fail-closed lenses |
| 7.6 Quant research pipeline skill | done | `.claude/skills/quant-research-pipeline/` — Tatara filtration mapped to ExperimentContract/ValidationGate |
| 7.7 Quant portfolio allocation skill | done | `.claude/skills/quant-portfolio-allocation/` — Ruuj diversification/HRP/cut-vs-trim mapped to allocator + D1 cash |
| 7.8 Agent build loop skill | done | `.claude/skills/agent-build-loop/` — mikenevermiss prompt/plan/execute/check/fix + compress→execute; human owns plan+check |
| 7.9 LLM app pattern router | done | `.claude/skills/llm-app-pattern-router/` — awesome-llm-apps catalog filtration; adopt scope-creep/archaeology doctrine only |
| 7.10 Code graph context skill | done | `.claude/skills/code-graph-context/` — CodeGraphContext opt-in call-graph; ≠ L2/L3/Cognee |
| 7.11 Point-in-time universe | done | `dynamic_grid/universe_snapshot.py` — tvscreener endpoint contract, append-only, `load_as_of` refuses future universes; `docs/TVSCREENER_ADOPTION.md` |
| 7.11a Daily snapshot task | done (operator must register) | `automations/universe-snapshot/` — `--all` + user-level Scheduled Task, 18:00 local, read-only, no commit |
| 7.12 Egress policy + trifecta guard | done | `gate/egress_scan.py` + `integrations/egress-allowlist.json` — 21 hosts declared, no live venue, news path pinned LLM-free; `docs/ARCHESTRA_ADOPTION.md` |
| 7.13 Lab slice 5 | done | `/compared-to-what` — "เทียบกับอะไร นับกี่ครั้ง"; numbers generated from E33/RVOL/E35 outputs at build time, never hand-typed |
| 8 Factory SQLite | deferred | solo research pace — BUILD 3 enough |
| 9 Swarm | deferred | only if goals split & mechanical |
| 10 Standing goals | light | `STATE.md` |
| 11 Human seat | you | HANDOFF duties |
| 12 Ops | light | watch cheap-tier share + gate |

## Commands

```powershell
powershell -File gate/verify.ps1
python agent/router.py "should we promote dual after E23?"
python agent/executor_advisor.py
python -m unittest tests.test_agent_graph
python -m dynamic_grid.universe_snapshot --list
python -m dynamic_grid.universe_snapshot --all
powershell -File automations/universe-snapshot/install-task.ps1
python gate/egress_scan.py
python -m agent.diamonds.runtime_safety_review
powershell -File loop/ralph.ps1 -BudgetUsd 2 -MaxIters 2
```

## L2 / L3 firewall

- **L2 (agent graph)** may define review diamonds, severity routers, and
  loop-until-dry discovery. It must never import Fund OS / exchange modules.
- **L3 (runtime graph)** may classify reconcile severity and plan dry loops in
  code (`fund-command-center-local/src/lib/grid-runtime-graph.ts`). It must never
  call models. Placement remains behind `grid-runtime-safety.ts`.
- BUILD 7 fan-outs / swarm stay deferred until ROUTING triggers fire.

## Trading-specific never list

Unchanged from research doctrine: no live orders, no RL default, no lowering
ValidationGate, synthetic ≠ real, log negatives in `docs/VALIDATION_LOG.md`.
