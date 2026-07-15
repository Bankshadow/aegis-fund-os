"""Pre-declared A/B test for persistent regimes under realistic execution.

The comparison deliberately separates two questions:
  1) how much performance disappears when ambiguous daily bars, gap stops,
     fees on open inventory, slippage, and terminal liquidation are modeled;
  2) under those same costs, does a persistent two-dimensional regime gate
     improve robust score versus the legacy mutually-exclusive detector?

No parameters are optimized on the evaluation sets below.
"""

from dataclasses import replace

import numpy as np

from compare_versions import V1_BEST
from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          load_bear_market, load_binance_klines, run_backtest)
from validate_v2 import V2_REGIME


SEEDS = (7, 11, 13)
REALISTIC = dict(
    conservative_intrabar=True,
    stop_slippage_bps=5.0,
    book_entry_fees_immediately=True,
)


def robust(result):
    return result.total_return - 2.0 * result.max_drawdown


def variants():
    base = DynamicGridConfig(**V1_BEST, **V2_REGIME, use_regime=True)
    return {
        "legacy/optimistic": base,
        "legacy/realistic": replace(base, **REALISTIC),
        "2d-persistent": replace(
            base, **REALISTIC, use_regime_2d=True,
            regime_confirm_bars=3, regime_min_dwell_bars=5,
            regime_hysteresis=0.7),
        "2d-persistent+HVgate": replace(
            base, **REALISTIC, use_regime_2d=True,
            regime_confirm_bars=3, regime_min_dwell_bars=5,
            regime_hysteresis=0.7, block_high_vol_entries=True),
    }


def evaluate(data, cfg):
    return run_backtest(data, cfg, liquidate_at_end=True)


def main():
    configs = variants()
    print("=== Synthetic held-out: mean robust score across seeds ===")
    print(f"{'scenario':<16}" + "".join(f"{name:>23}" for name in configs))
    aggregate = {name: [] for name in configs}
    for scenario in SCENARIOS:
        row = f"{scenario:<16}"
        for name, cfg in configs.items():
            scores = [robust(evaluate(generate_scenario(
                scenario, n_bars=2000, seed=seed), cfg)) for seed in SEEDS]
            score = float(np.mean(scores))
            aggregate[name].append(score)
            row += f"{score:>+23.4f}"
        print(row)
    print(f"{'MEAN':<16}" + "".join(
        f"{np.mean(aggregate[name]):>+23.4f}" for name in configs))

    bear = load_bear_market()[310:730]
    bull = load_binance_klines()
    for label, data in (("Real bear 2022", bear),
                        ("Real bull 2023-2026", bull)):
        print(f"\n=== {label} ===")
        for name, cfg in configs.items():
            r = evaluate(data, cfg)
            print(f"{name:<23} ret {r.total_return*100:+7.2f}%  "
                  f"DD {r.max_drawdown*100:6.2f}%  robust {robust(r):+.4f}")


if __name__ == "__main__":
    main()
