"""E20: Walk-forward RL on real BTC/4h — does E19 survive rolling time?

Criterion (declared BEFORE run):
  Per fold WIN if: dual RL robust (return - 2*maxDD) > dual rule robust
  AND n_scale_changes > 0 (engaged). Non-engaged folds are n/a (excluded).

  Overall PASS if engaged win rate > 50% AND engaged folds >= 3.
  Otherwise FAIL. Report every fold including losses. Not a live recommendation.

Protocol (locked):
  BTCUSDT 4h, real costs (fee + CS half-spread + mean funding).
  Rolling: train=800, test=200, step=200 -> 6 folds.
  Each fold: tune on train -> train_q_on_ohlc (epochs=6, seeds 0/1/2)
  -> dual rule vs dual RL on test. Fresh Q every fold; never load old tables.
  use_regime_pct=True; funding/relative off.
"""

from dynamic_grid import DynamicGridConfig, run_backtest_engine
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.market_data import market_profile
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.rl_agent import RLGovernor, train_q_on_ohlc
from multiasset_demo import BASE_FEE, tune

TRAIN_BARS = 800
TEST_BARS = 200
STEP_BARS = 200
EPOCHS = 6
TRAIN_SEEDS = (0, 1, 2)
PCT = dict(use_regime=True, use_regime_pct=True, use_funding_bias=False,
           use_relative_value=False)


def iter_walkforward_folds(n: int, train_bars: int, test_bars: int,
                           step_bars: int) -> list[tuple[int, int, int, int]]:
    """Return (train_start, train_end, test_start, test_end) for each fold."""
    if train_bars < 1 or test_bars < 1 or step_bars < 1:
        raise ValueError("train/test/step must be positive")
    folds = []
    train_start = 0
    while True:
        train_end = train_start + train_bars
        test_start = train_end
        test_end = test_start + test_bars
        if test_end > n:
            break
        folds.append((train_start, train_end, test_start, test_end))
        train_start += step_bars
    return folds


def robust(r):
    return r.total_return - 2.0 * r.max_drawdown


def make_cfg(params, profile) -> DynamicGridConfig:
    return DynamicGridConfig(
        **params, **PCT,
        fee_rate=BASE_FEE + profile["half_spread"],
        funding_rate_per_bar=profile["funding_per_bar"],
        half_spread=0.0,
    )


def main():
    print("E20 criterion: engaged fold win rate > 50% (need >= 3 engaged folds)")
    print(f"rolling train={TRAIN_BARS} test={TEST_BARS} step={STEP_BARS}; "
          f"epochs={EPOCHS} seeds={TRAIN_SEEDS}\n")

    prof = market_profile("BTCUSDT", "4h")
    ohlc = prof["ohlc"]
    folds = iter_walkforward_folds(len(ohlc), TRAIN_BARS, TEST_BARS, STEP_BARS)
    print(f"BTC/4h n={len(ohlc)} folds={len(folds)}")
    print(f"{'fold':>4} {'tr':>11} {'te':>11} {'rule_r':>8} {'rl_r':>8} "
          f"{'rule_s':>8} {'rl_s':>8} {'chg':>4} {'eng':>3} {'win':>4}")
    print("-" * 86)

    engaged_wins = []
    for i, (ts, te, vs, ve) in enumerate(folds):
        train, test = ohlc[ts:te], ohlc[vs:ve]
        params = tune(train, prof, seed=i)
        cfg = make_cfg(params, prof)
        layers_fn = lambda c=cfg: make_dual_layers(c)
        q = train_q_on_ohlc(layers_fn, train, epochs=EPOCHS, seeds=TRAIN_SEEDS,
                            verbose=False)
        rule = MemoryOrchestrator(make_dual_layers(cfg))
        rl = RLGovernor(make_dual_layers(cfg), q=q, learn=False)
        r_rule = run_backtest_engine(test, rule, liquidate_at_end=True)
        r_rl = run_backtest_engine(test, rl, liquidate_at_end=True)
        s_rule, s_rl = robust(r_rule), robust(r_rl)
        engaged = rl.n_scale_changes > 0
        win = bool(engaged and s_rl > s_rule)
        if engaged:
            engaged_wins.append(win)
        tag = "YES" if win else ("n/a" if not engaged else "no")
        print(f"{i:>4} {ts:>4}-{te:<5} {vs:>4}-{ve:<5} "
              f"{r_rule.total_return*100:>+7.2f}% {r_rl.total_return*100:>+7.2f}% "
              f"{s_rule:>+8.4f} {s_rl:>+8.4f} "
              f"{rl.n_scale_changes:>4d} {'Y' if engaged else 'N':>3} {tag:>4}")

    n = len(engaged_wins)
    wins = sum(engaged_wins)
    rate = (wins / n) if n else 0.0
    print()
    print(f"Engaged win rate: {wins}/{n} ({rate:.0%})")
    enough = n >= 3
    passed = enough and rate > 0.5
    if not enough:
        print("FAIL: fewer than 3 engaged folds (insufficient evidence)")
    elif passed:
        print("PASS: engaged win rate > 50%")
    else:
        print("FAIL: engaged win rate <= 50%")
    print("Not a live-trading recommendation.")


if __name__ == "__main__":
    main()
