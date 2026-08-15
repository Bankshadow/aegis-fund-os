---
name: quant-portfolio-allocation
description: >-
  Allocate capital across multiple approved return sources using diversification
  math, covariance hygiene, HRP-style risk budgets, view tilts, and cut-vs-trim
  discipline. Use when combining strategies/sleeves/bots, sizing layers, deciding
  whether a new edge diversifies the book, rebalancing weights, cutting a sleeve,
  or when the user mentions diversification ratio, Ledoit-Wolf, HRP, Black-Litterman,
  risk parity, covariance shrinkage, or Ruuj-style portfolio construction.
---

# Quant portfolio allocation (repo-mapped)

Source idea: capital allocation engineering, not “diversify” folklore
([RuujSs](https://x.com/RuujSs/status/2077040860735349183)).

This skill is **downstream** of `.claude/skills/quant-research-pipeline/`.
Only sleeves that already survived ValidationGate / paper eligibility compete
for capital here. Do not use allocation math to rescue a failed alpha.

## Core reframe

- Diversification is a **covariance identity**, not advice.
- Raw sample covariance is hostile to optimizers — shrink (or avoid inversion) first.
- Prefer **risk-budget / hierarchical** allocation over naive mean-variance.
- Separate **losing money** (trim/rebalance) from **mechanism dead** (cut/kill).

## Never

- Never allocate live / third-party capital
- Never lower `ValidationGate` or promote dual against D1 to “fill” a portfolio
- Never feed an optimizer a raw sample Σ when N is large vs history
- Never treat temporary drawdown alone as a cut signal
- Never invent expected-return forecasts with fake confidence (ω → 0)

## Always

- Only allocate among **pre-approved** sleeves (`CoreTradingEngine._ALLOWED`,
  cash, paper/testnet bots with governance APPROVED)
- Cap any single sleeve (`RiskBudgetAllocator.max_weight` pattern, default ≤ 0.75)
- Robust score / engaged periods remain research truth; allocation does not override
- Paper / Binance Spot Testnet only until Phase-3 live gates clear

## Five layers → this repo

| # | Layer | Question | Repo anchors |
|---|---|---|---|
| 1 | Diversification math | Does adding X raise true diversification? | Track correlation / diversification ratio across sleeves; flat DR ⇒ not diversifying |
| 2 | Covariance hygiene | Is Σ trustworthy? | Prefer shrinkage (Ledoit–Wolf style) or methods that skip Σ⁻¹; never raw sample for N≫T |
| 3 | Allocation method | How to set weights? | Baseline: fixed layer weights (`make_dual_layers` 10/70/20, dual 75/25) or `RiskBudgetAllocator`; prefer HRP-like risk budgets over Markowitz MVO |
| 4 | Views (optional) | How to tilt without breaking the book? | Black–Litterman-style: baseline from risk weights, tilt only with calibrated confidence; hunches get high ω |
| 5 | Rebalance vs cut | Trim drift or kill sleeve? | Threshold rebalance for weight drift; **cut** only when mechanism fails (gate kill, D1, decay) — not because PnL is temporarily red |

## Decision rules (practical)

### Adding a sleeve

1. Research pipeline must have already passed or explicitly be `cash`/benchmark.
2. Estimate pairwise correlation / diversification benefit vs current book.
3. If diversification ratio (or equivalent) does **not** improve → reject as
   “more of the same risk,” even if standalone backtest looks fine.
4. Size under `max_weight`; leftover stays cash (fail-closed default on Line-B).

### Choosing a method

| Method | Use when | Avoid when |
|---|---|---|
| Fixed / rule weights | Few sleeves, known mechanism (current dual/layers) | Pretending it’s optimized |
| `RiskBudgetAllocator` | Need performance tilt inside hard caps | Using it to revive killed alphas |
| Risk parity / HRP | Many sleeves, noisy return forecasts | Need live deploy today without tests |
| Mean-variance (naive) | Teaching / toy only | Production sizing on this repo |

Default call for this codebase today: **keep deterministic weights + allocator caps**;
only introduce HRP/shrinkage as a **new researched module** with its own contract
and tests — do not silently swap production defaults.

### Cut vs trim

| Symptom | Action |
|---|---|
| Weight drifted past band (e.g. 5–10%) | **Trim** / rebalance toward target |
| Temporary DD inside expected profile | Hold / trim only if risk budget breached |
| Mechanism invalidated / gate kill / D1 closed | **Cut** sleeve to zero; do not “average down” |
| Paper/testnet vs sim persistent divergence | Cut or revise research — do not loosen gate |

Aligns with kill ladder in `quant-research-pipeline`: cut = research kill reaching capital.

## Agent workflow checklist

```
- [ ] Sleeves listed are pre-approved (or cash)
- [ ] Stated whether adding X improves diversification vs existing book
- [ ] Covariance plan: shrinkage / HRP / or explicit fixed weights (no raw Σ optimizer)
- [ ] max_weight / cash residual declared
- [ ] View tilts have confidence (or none)
- [ ] Cut vs trim criteria named before looking at recent PnL
- [ ] Target ≤ paper/testnet capital simulation
- [ ] If proposing new allocator code: ExperimentContract + tests + gate/verify
```

## Anti-overlap

| Skill | Job |
|---|---|
| `quant-research-pipeline` | Filtrate alpha / promote-kill a **single** edge |
| `quant-portfolio-allocation` | Size **surviving** edges relative to each other |
| `ship-gate` | Environment done check |
| `stuck-protocol` | Advisor consult on promote/kill/size judgment |

## Related

- `dynamic_grid/allocator.py` — current capped risk-budget tilts
- `dynamic_grid/orchestrator.py` — layer weights
- `docs/VALIDATION_LOG.md` § D1 — Line-B cash default
- `docs/PRIVATE_FUND_ROADMAP.md` — portfolio & risk pillar (future multi-platform)
