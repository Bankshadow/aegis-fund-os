"""Dual-side portfolio (long 75% + short 25%) vs long-only — declared tests.

Judging criteria DECLARED BEFORE running (project standard):
  metric  : robust score = return - 2*maxDD
  A) synthetic: 6 scenarios x held-out seeds (7,11,13), MemoryOrchestrator
     governance on both variants (only difference = the short layer)
  B) real bear (2022, -74%, unseen): configs tuned per-side on 2021 only
  C) real bull (Oct 2023 - Jul 2026): same 2021-tuned configs, also unseen.
     The short side must NOT wreck bull performance - that's the test.
"""

import numpy as np

from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          run_backtest, run_backtest_engine, make_layers,
                          load_binance_klines)
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.grid_engine import DynamicGridEngine
from dynamic_grid.short_engine import ShortGridEngine
from dynamic_grid.real_data import load_bear_market
from bear_short_demo import tune, TRAIN_END, TEST_END
from multilayer_demo import BASE

SEEDS = (7, 11, 13)
N_BARS = 2000


def robust(r):
    return r.total_return - 2.0 * r.max_drawdown


def part_a_synthetic():
    base = DynamicGridConfig(**BASE)
    variants = {
        "long-only": lambda: MemoryOrchestrator(make_layers(base)),
        "dual 75/25": lambda: MemoryOrchestrator(make_dual_layers(base)),
    }
    print("=== A) Synthetic, held-out seeds 7/11/13 (robust score) ===")
    print(f"{'scenario':<15} {'long-only':>12} {'dual 75/25':>12}")
    means = {k: [] for k in variants}
    for name in SCENARIOS:
        row = f"{name:<15}"
        for k, mk in variants.items():
            s = np.mean([robust(run_backtest_engine(
                generate_scenario(name, n_bars=N_BARS, seed=sd), mk()))
                for sd in SEEDS])
            means[k].append(s)
            row += f"{s:>+12.4f}"
        print(row)
    print(f"{'MEAN':<15}" + "".join(f"{np.mean(means[k]):>+12.4f}"
                                    for k in variants))


def run_real(ohlc, long_p, short_p, label):
    base_l = DynamicGridConfig(**long_p)
    base_s = DynamicGridConfig(**short_p)
    variants = {
        "long-only": MemoryOrchestrator(make_layers(base_l)),
        "dual 75/25": MemoryOrchestrator(
            make_dual_layers(base_l, short_cfg=base_s)),
    }
    print(f"\n=== {label} ===")
    for k, eng in variants.items():
        r = run_backtest_engine(ohlc, eng)
        print(f"  {k:<11} ret {r.total_return*100:+7.2f}%  "
              f"maxDD {r.max_drawdown*100:5.2f}%  robust {robust(r):+.4f}")


def main():
    part_a_synthetic()

    # per-side tuning on 2021 ONLY (seed 0; bear_short_demo showed all three
    # seeds agree on direction), then two unseen real periods
    bear_all = load_bear_market()
    train = bear_all[:TRAIN_END]
    long_p = tune(train, DynamicGridEngine, 0)
    short_p = tune(train, ShortGridEngine, 0)

    run_real(bear_all[TRAIN_END:TEST_END], long_p, short_p,
             "B) Real bear 2022 (-74%, unseen; tuned on 2021)")
    run_real(load_binance_klines(), long_p, short_p,
             "C) Real bull Oct 2023 - Jul 2026 (unseen; same 2021 configs)")


if __name__ == "__main__":
    main()
