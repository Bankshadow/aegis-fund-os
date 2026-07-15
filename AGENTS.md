# AGENTS.md — Grid Trading Agent Constitution

> Laws only: a number, a never, or a command that checks it.
> Mirrors `CLAUDE.md`. Keep under 100 lines. Both harnesses must share this doctrine.

## Mission

Research and harden the Dynamic Grid system toward multi-platform ops / private-fund readiness.
Default config: **Dual 75/25 rule-based + percentile-rank regime**. Not live-trading ready.

## Never

1. Never send live orders or handle third-party capital.
2. Never promote RL as default (`results/q_table.json` and synthetic Q tables are banned for live).
3. Never lower `ValidationGate` thresholds to pass a candidate.
4. Never treat synthetic results as real-market evidence.
5. Never transfer a tuned config across scale/timeframe without a new held-out run.
6. Never edit a test to make it pass.
7. Never merge past a BLOCKED gate or skip `./gate/verify` (or `gate/verify.ps1`).
8. Never let a model grade its own homework as the final vote — the gate is a script.

## Always (numbers)

1. Declare pass/fail criteria **before** running an experiment.
2. Use ≥ **3 seeds** and a held-out split; report negative results in `docs/VALIDATION_LOG.md`.
3. Robust score = `return - 2*maxDD` (engaged periods only) unless a demo declares otherwise.
4. Cap advisor consults at **3** per task (`agent/executor_advisor.py`).
5. Cap loop ticks at **$BUDGET_USD** and **MAX_ITERS** (see `loop/ralph.ps1`).
6. Subagents: do not spawn unless asked; pin lower effort than the parent.
7. Read `STATE.md` at session start; write it before walking away.
8. Route at boundaries; raise **effort** before swapping **model** (cache stays warm).

## Done = environment fact

A task is done only when one of these is true:

- `gate/verify.ps1` (or `gate/verify.sh`) exits **0**
- A declared check command in `loop/TASKS.md` exits **0**
- `ValidationGate.passes(report)` is **True** with criteria declared up front

Model self-report is never sufficient.

## Default seats (see ROUTING.md)

| Role | Default | Fallback |
|---|---|---|
| Driver / bulk execution | Sonnet 5 or GPT-5.6 Sol | Terra / Opus 4.8 |
| Advisor / judgment | Fable 5 | Opus 4.8 |
| Cross-vendor review | Sol in Codex, or Fable in Claude | — |
| Final vote | `gate/verify.*` | — |

## Smoke

```
python -m unittest tests.test_strategy_framework
python run_demo.py --fast
gate/verify.ps1
```

## Read next

`docs/HANDOFF_CURSOR.md` → `docs/VALIDATION_LOG.md` → `docs/PRIVATE_FUND_ROADMAP.md` → `ROUTING.md`
