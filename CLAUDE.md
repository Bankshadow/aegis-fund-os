# CLAUDE.md — Grid Trading (Claude Code)

Same laws as `AGENTS.md`. Keep under 60 lines. Numbers, nevers, checkable commands only.

## Project

Dynamic Grid Trading research → multi-platform ops readiness.
Recommended: Dual 75/25 rule-based + percentile regime. **No live trading.**

## Never

- Never live-order or manage others' money
- Never promote RL default / synthetic Q tables for live
- Never lower ValidationGate criteria
- Never treat synthetic as real evidence
- Never edit tests to pass; never skip the gate
- Never spawn subagents unless asked

## Always

- Criteria before run; ≥3 seeds; held-out; log negatives in `docs/VALIDATION_LOG.md`
- Robust = `return - 2*maxDD`; engaged only
- Advisor consults ≤3/task; Fable for judgment grams, Sonnet/Sol for bulk
- Effort before model swap; read/write `STATE.md`
- Done = `gate/verify.ps1` exit 0 or declared check exit 0 — never model opinion

## Routing

See `ROUTING.md`. Fable plans/advises; Sol/Sonnet execute; gate votes last.

## Smoke

```
python -m unittest tests.test_strategy_framework
gate/verify.ps1
```
