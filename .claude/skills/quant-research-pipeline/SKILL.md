---
name: quant-research-pipeline
description: >-
  Run strategy work as a quant filtration pipeline (mechanism → data → universe →
  feature → signal → ValidationGate → costs/execution → sizing → paper feedback).
  Use when designing experiments, promoting/killing candidates, writing
  ExperimentContract, interpreting ValidationGate/VALIDATION_LOG, or when the
  user mentions quant research pipeline, alpha pipeline, research stages,
  false discovery, or 0xTatara-style research process.
---

# Quant research pipeline (repo-mapped)

Source idea: filtration, not prediction theater ([0xTatara](https://x.com/0xTatara/status/2078828967407026452)).
This skill maps that pipeline onto **this** Grid Trading repo. Do not invent a
parallel research OS.

## Core reframe

- Start with a **market mechanism** hypothesis, not a model.
- Most ideas must **die cheaply**. Done = environment fact (`gate/verify`,
  `ValidationGate.passes`, declared check) — never model self-report.
- Moat = pipeline speed + rejection quality, not a secret indicator.

## Never (constitution)

- Never live-order or third-party capital
- Never lower `ValidationGate` thresholds to pass a candidate
- Never treat synthetic as real-market evidence
- Never promote RL / synthetic Q tables as default
- Never transfer a tuned config across scale/timeframe without a new held-out run
- Never edit tests to pass; never skip `gate/verify.*`

## Always (numbers)

- Criteria **before** run; ≥ **3** seeds; held-out split
- Robust score = `return - 2*maxDD` (engaged periods) unless a demo declares otherwise
- Log negatives in `docs/VALIDATION_LOG.md`
- Line-B dual tuning is **closed (D1)** until a new mechanism-level hypothesis

## Ten stages → this repo

Work top-down. Stop at the first failed stage; do not jump to model/backtest polish.

| # | Stage | Question | Repo anchors |
|---|---|---|---|
| 1 | Data truth | What did the market look like *then*? | `dynamic_grid/real_data.py`, `market_data.py`; no lookahead; revisions ≠ as-of |
| 2 | Universe | Where could this be traded at our size? | Declared pairs/TF in contract; engaged-only; no survivors-only history |
| 3 | Features | What measurable footprint does the mechanism leave? | Regime/percentile/ATR/grid geometry — feature must name the mechanism |
| 4 | Decompose | What common risk must we remove? | Regime router, cash default, dual long/short split — residual > raw move |
| 5 | Signal | Exact trade rule from the feature | Dual 75/25, grid engine builders in `core_engine.py` `_ALLOWED` only |
| 6 | Validate | Survives held-out + gate? | `ExperimentContract` + `ValidationGate` + combinatorial purged screen |
| 7 | Multiple testing | Did search invent the edge? | Cap trials in contract; log kills; automation ⇒ *more* skepticism |
| 8 | Execution realism | Costs/fills kill it? | Fees, AOT execution modes, paper/testnet only — signal ≠ fill |
| 9 | Size | How much capital vs other edges? | `risk_per_zone`, layer weights, allocator caps — edge competes for capital |
| 10 | Paper feedback | Sim vs paper/testnet drift? | Testnet reconcile, realized cycles, ops snapshot — **not** live capital |

Stages 8–10 on this repo stop at **paper / Binance Spot Testnet**. Live is forbidden.

## Experiment intake (run this first)

Before writing code or sweeping params, fill an `ExperimentContract`-shaped brief:

1. **Mechanism** (1–2 sentences): who/what creates the inefficiency?
2. **Footprint**: what observable feature should appear if the mechanism is real?
3. **Universe**: pairs, timeframe, engaged filter, liquidity assumption
4. **Rejectors**: what result kills the idea (gate thresholds, cost floor, correlation to cash/existing)
5. **Seeds / held-out / max_trials**: declared up front
6. **Target**: `research` or `paper` only — never imply live

Then implement via `dynamic_grid/loop_engineering.py` (`ExperimentContract`, runner,
memory). Do not hand-wave past the contract.

## Kill ladder (healthy pipeline)

Expect most candidates to die. Prefer early cheap kills:

1. No mechanism / no footprint → kill before backtest
2. Contaminated data / lookahead → kill
3. Fail `ValidationGate` / held-out → kill + log
4. Dies after costs / execution realism → kill + log
5. Too correlated with cash or existing book → kill (D1: dual already lost to cash)
6. Insufficient capacity / not tradable in universe → kill
7. Paper/testnet diverges badly from sim → revise or kill — do not loosen gate

One survivor with modest robust score is success. Spectacular in-sample alone is not.

## Agent workflow checklist

Copy and tick:

```
- [ ] Mechanism named (not "try XGBoost on prices")
- [ ] ExperimentContract fields declared before run
- [ ] Universe + engaged filter stated
- [ ] ≥3 seeds + held-out
- [ ] ValidationGate criteria unchanged
- [ ] Negatives appended to docs/VALIDATION_LOG.md
- [ ] Costs/execution realism considered before promote talk
- [ ] Promote target ≤ paper/testnet
- [ ] gate/verify.ps1 or declared check exit 0
```

## When stuck

Use `.claude/skills/stuck-protocol/SKILL.md` (≤3 Fable consults). Promotion /
overfit / gate judgment qualifies; routine coding does not.

## Related

- `docs/VALIDATION_LOG.md` — evidence ledger
- `docs/AGENT_STACK.md` + `ROUTING.md` — seats and fan-out triggers
- `docs/HANDOFF_CURSOR.md` — current ops/graph status
- L2 diamond (code review filtration): `python -m agent.diamonds.runtime_safety_review`
- Done gate: `.claude/skills/ship-gate/SKILL.md`
