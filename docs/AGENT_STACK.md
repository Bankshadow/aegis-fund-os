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
powershell -File loop/ralph.ps1 -BudgetUsd 2 -MaxIters 2
```

## Trading-specific never list

Unchanged from research doctrine: no live orders, no RL default, no lowering
ValidationGate, synthetic ≠ real, log negatives in `docs/VALIDATION_LOG.md`.
