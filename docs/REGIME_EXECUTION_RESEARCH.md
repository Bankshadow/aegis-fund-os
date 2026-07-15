# Regime Switching and Execution Realism Research (v4)

## Research basis

- Hamilton's Markov-switching framework treats regime changes as latent,
  persistent states inferred probabilistically rather than directly observed:
  https://doi.org/10.2307/1912559
- Jump-model research adds a transition penalty to improve state persistence
  and evaluates with trading delay and transaction costs:
  https://arxiv.org/abs/2402.05272
- Recent regime-aware volatility work finds that practical value is often in
  volatility scaling, gating, and turnover control rather than unconditional
  return prediction:
  https://arxiv.org/abs/2606.09478
- LEAN's official reality-model documentation separates fill, slippage, and
  partial-fill models. It also notes that complete immediate fills are an
  assumption and that realistic fills require spread/slippage/volume logic:
  https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts
  https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models
- Binance documents funding intervals and rate constraints separately from
  price bars, so funding must be modeled as an explicit cash flow:
  https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/rest-api/Get-Funding-Info

## Implemented changes

1. `PersistentRegimeDetector`
   - independent `direction` and `volatility` states;
   - confirmation bars, minimum dwell, and entry/exit hysteresis;
   - preserves the legacy `regime` label for compatibility.
2. Realistic execution options in `DynamicGridConfig`
   - conservative same-bar TP/stop resolution;
   - gap-through-stop pricing and adverse stop slippage;
   - entry fees booked when inventory opens;
   - explicit funding cash flow per bar;
   - terminal liquidation with exit fee/slippage.
3. `RegimeSwitchingOrchestrator`
   - long sleeve in confirmed uptrends;
   - short sleeve in confirmed downtrends;
   - balanced, configurable allocation in ranges;
   - volatility-scaled risk budget;
   - disabled sleeves manage existing inventory but cannot add/recenter.

All new behavior is opt-in so legacy experiments remain reproducible.

## Pre-declared validation result

Criterion: `robust score = return - 2 × max drawdown`. Router parameters were
selected on synthetic seeds 1/2 only. Evaluation used held-out seeds 7/11/13,
the unseen 2022 bear, and the later 2023-2026 bull. Every compared strategy
used conservative execution, 5 bps stop slippage, immediate entry fees, and
terminal liquidation.

| Evaluation | Fixed 75/25 | Regime switch | Verdict |
|---|---:|---:|---|
| Synthetic held-out mean robust | -0.0337 | -0.0465 | switch is worse |
| Real bear 2022 robust | -0.1444 | -0.1064 | defensive improvement |
| Real bull 2023-2026 return | +0.82% | +3.75% | switch is better |
| Real bull 2023-2026 max DD | 15.00% | 11.26% | switch is better |
| Real bull 2023-2026 robust | -0.2917 | -0.1876 | defensive improvement |

## Honest conclusion

The implementation exposes a **candidate defensive edge on the available real
BTC samples**, but it is not a transferable production edge because it fails
the held-out synthetic panel and every aggregate robust score remains negative.
Do not deploy it live. The next acceptance gate is cross-asset, lower-timeframe
validation with actual volume/spread/funding history and a benchmark that
includes buy-and-hold, cash, and a simple momentum-volatility rule.

## Update log

### 2026-07-11 - v4 research implementation record

User request: research regime switching and execution realism, then use the
findings to improve the system and look for edge.

What was added:

- `dynamic_grid/regime.py`: added `PersistentRegimeDetector` with separate
  direction and volatility states, confirmation, dwell time, and hysteresis.
- `dynamic_grid/grid_engine.py` and `dynamic_grid/short_engine.py`: added
  opt-in realistic execution controls for same-bar ambiguity, gap stop fills,
  adverse stop slippage, entry-fee booking, funding cash flow, and terminal
  liquidation.
- `dynamic_grid/backtest.py`: added optional end-of-test liquidation so final
  equity can include open inventory exit cost.
- `dynamic_grid/regime_switch.py`: added `RegimeSwitchingOrchestrator` to route
  long/short/range allocation by persistent 2D regime state.
- `dynamic_grid/orchestrator.py`, `dynamic_grid/orchestrator_agent.py`, and
  `dynamic_grid/rl_agent.py`: added liquidation pass-through support.
- `tests/test_regime_execution.py`: added regression tests for independent
  regime states, conservative intrabar behavior, and terminal liquidation.
- `regime_execution_demo.py`: added legacy-vs-realistic regime execution
  comparison.
- `regime_switch_edge_demo.py`: added train/test router validation with
  synthetic holdout plus real bear/bull BTC samples.

Validation completed:

- `python -m compileall -q dynamic_grid tests regime_execution_demo.py regime_switch_edge_demo.py`
- `python -m unittest discover -s tests -v`
- `python compare_versions.py`

Important result:

- Legacy defaults remained backward-compatible in `compare_versions.py`.
- The new regime router improved defense on the available real BTC bear and
  bull samples under realistic execution assumptions.
- It did not improve the held-out synthetic panel, so this is a research
  candidate, not a production-ready trading edge.

Open limitations:

- Partial fills and volume-share fills are not implemented because the current
  engine data does not include order book, spread, or reliable traded volume.
- Funding is modeled as a configurable per-bar cash flow, not yet calibrated
  from historical funding records.
- The 5 bps stop-slippage scenario is an assumption, not an empirical estimate.
- Cross-asset and lower-timeframe validation is still required before any live
  use.

## Reproduce

```text
python -m unittest discover -s tests -v
python regime_execution_demo.py
python regime_switch_edge_demo.py
```

## Strategy framework integration (2026-07-11)

Architecture concepts adapted from `virattt/ai-hedge-fund` were integrated as
small, deterministic components; no external repository dependency or LLM
trade-control was added.

- `dynamic_grid/signals.py`: `StrategySignal` contract and
  `RegimeSignalModel`. A signal is a view (`[-1, +1]`) with confidence and
  audit context; it cannot place trades or size positions.
- `dynamic_grid/allocator.py`: `RiskBudgetAllocator`, an opt-in allocator for
  long/short sleeves. It only reallocates capital among sleeves permitted by
  the regime router, honours a per-sleeve maximum weight while both sleeves
  are enabled, and records realized PnL only.
- `dynamic_grid/validation.py`: combinatorial purged candidate screening plus
  `ValidationGate`. The selection-failure result is explicitly empirical, not
  a claim of formal PBO/CPCV.
- `dynamic_grid/regime_switch.py`: accepts the allocator optionally. Existing
  behavior is unchanged when `allocator=None`.

Initial realistic BTCUSDT 4h screening compared the existing fixed regime
router with the allocated router. It produced 14 validation folds, median OOS
score `-0.0539`, and empirical selection failure rate `57.1%`; the promotion
gate therefore **failed**. The allocator is a research candidate only and is
not approved for paper/live use.

Run the same check with:

```text
python strategy_gate_demo.py
```

## Multi-strategy research framework (2026-07-11)

`dynamic_grid/research.py` now provides a research layer that compares several
strategies on exactly the same data and execution assumptions. It keeps the
existing grid engines unchanged and does not allow an LLM to control sizing or
orders.

```text
ResearchDataset (BTC/ETH/SOL OHLC, funding, estimated spread)
        -> ExecutionProfile (fees, funding, spread-stressed stops, conservative bars)
        -> StrategySpec candidates (cash, buy-and-hold, regime router, allocator)
        -> common backtests and risk-adjusted leaderboard
        -> combinatorial purged validation per asset
        -> PromotionDecision (paper eligible only if a tradable candidate passes)
```

Built components:

- `dynamic_grid/benchmarks.py`: cash and buy-and-hold baselines. Cash is a
  valid winner when every trading candidate is worse; it is never deployable.
- `dynamic_grid/research.py`: dataset, execution profile, strategy registry,
  cross-asset scoring, and promotion decision.
- `multi_strategy_research_demo.py`: reproducible BTCUSDT/ETHUSDT/SOLUSDT 4h
  research run.

Initial cross-asset result under 5 bps additional stop slippage, estimated
half-spread stress, fees, funding, conservative intrabar ordering, and terminal
liquidation:

| Candidate | Mean score (`return - 2*maxDD`) | Decision |
|---|---:|---|
| Cash | `+0.0000` | selected benchmark; not tradable |
| Regime allocator | `-0.1379` | rejected |
| Regime router | `-0.1379` | rejected |
| Buy-and-hold | `-1.8532` | benchmark only |

The correct outcome is **no paper promotion**. This is evidence that the
framework is functioning as a guardrail, not evidence of a live trading edge.
Run it with:

```text
python multi_strategy_research_demo.py
```

## Consolidated core engine (2026-07-11)

The production-shaped core is `dynamic_grid/core_engine.py`. It combines the
research findings into one deliberately fail-closed decision path:

```text
Historical research -> cross-asset validation gate -> PromotionDecision
                                                    |
                              rejected/no decision -+-> CashBenchmark
                                                    |
                                      approved deterministic candidate
                                                    v
ExecutionProfile -> Persistent 2D regime -> long/short router -> grid lifecycle
                       (direction + volatility)       -> fees/funding/slippage
                                                    -> terminal liquidation
```

Core rules:

1. **Cash is the default.** No research decision, failed validation, or a
   benchmark winner produces no trades.
2. **Only `regime_router` and `regime_allocator` can be activated.** A new
   strategy must first exist in the research framework and then be explicitly
   allowed in the core builder.
3. **Regime controls permission; risk controls size.** Uptrend enables long,
   downtrend enables short, range splits sleeves, and high volatility reduces
   the risk budget. Open lots still obey TP/stop after a regime changes.
4. **Execution realism is inherited.** When a `ResearchDataset` is supplied,
   the core applies fees, historical mean funding, estimated-spread stop stress,
   conservative same-bar ordering, and final liquidation.
5. **No LLM can call the engine or override risk.** AI/research may propose a
   candidate, but only deterministic validation and code can activate it.

The current research result selects cash, so the core correctly remains in
cash mode. Reproduce the full hand-off with:

```text
python core_engine_demo.py
```
