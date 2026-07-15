"""RL Governor + Dual-side portfolio - searching for the real edge.

Two prior results, combined for the first time here:
  - RL Governor (v3.6): best robust score on synthetic, but SYNTHETIC ONLY -
    never tested on real data.
  - Dual-side 75/25 (v3.7): proven on real bear (2022) AND real bull
    (2023-26), but governed by hand-written rules, not learned.

This script trains RL on the DUAL layer stack and then runs the same
three-arena protocol dual_demo.py used - the first time RL faces real data.

Judging criterion DECLARED BEFORE running (unchanged project standard):
  robust score = return - 2*maxDD
  A) synthetic, held-out seeds (7,11,13), never used in training
  B) real bear 2022 (-74%, unseen)
  C) real bull 2023-2026 (unseen)

Four variants compared throughout: long-only x {rule, RL}, dual x {rule, RL}.
"""

import numpy as np

from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          run_backtest, run_backtest_engine, make_layers,
                          load_binance_klines)
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.rl_agent import RLGovernor, train_q, policy_table, save_q
from dynamic_grid.grid_engine import DynamicGridEngine
from dynamic_grid.short_engine import ShortGridEngine
from dynamic_grid.real_data import load_bear_market
from bear_short_demo import tune, TRAIN_END, TEST_END
from multilayer_demo import BASE

SEEDS_EVAL = (7, 11, 13)
N_BARS = 2000


def robust(r):
    return r.total_return - 2.0 * r.max_drawdown


def part_a(base_cfg, q_long, q_dual):
    variants = {
        "long rule": lambda: MemoryOrchestrator(make_layers(base_cfg)),
        "long RL  ": lambda: RLGovernor(make_layers(base_cfg), q=q_long),
        "dual rule": lambda: MemoryOrchestrator(make_dual_layers(base_cfg)),
        "dual RL  ": lambda: RLGovernor(make_dual_layers(base_cfg), q=q_dual),
    }
    print("=== A) Synthetic, held-out seeds 7/11/13 (robust score) ===")
    hdr = f"{'scenario':<15}" + "".join(f"{k:>12}" for k in variants)
    print(hdr)
    means = {k: [] for k in variants}
    for name in SCENARIOS:
        row = f"{name:<15}"
        for k, mk in variants.items():
            s = np.mean([robust(run_backtest_engine(
                generate_scenario(name, n_bars=N_BARS, seed=sd), mk()))
                for sd in SEEDS_EVAL])
            means[k].append(s)
            row += f"{s:>+12.4f}"
        print(row)
    print(f"{'MEAN':<15}" + "".join(f"{np.mean(means[k]):>+12.4f}"
                                    for k in variants))
    return {k: np.mean(v) for k, v in means.items()}


def part_bc(long_p, short_p, q_long, q_dual):
    bear_all = load_bear_market()
    tests = {
        "B) Real bear 2022 (-74%, unseen)": bear_all[TRAIN_END:TEST_END],
        "C) Real bull 2023-2026 (unseen)": load_binance_klines(),
    }
    for label, ohlc in tests.items():
        print(f"\n=== {label} ===")
        base_l = DynamicGridConfig(**long_p)
        base_s = DynamicGridConfig(**short_p)
        variants = {
            "long rule": MemoryOrchestrator(make_layers(base_l)),
            "long RL  ": RLGovernor(make_layers(base_l), q=q_long),
            "dual rule": MemoryOrchestrator(
                make_dual_layers(base_l, short_cfg=base_s)),
            "dual RL  ": RLGovernor(
                make_dual_layers(base_l, short_cfg=base_s), q=q_dual),
        }
        for k, eng in variants.items():
            r = run_backtest_engine(ohlc, eng)
            print(f"  {k}  ret {r.total_return*100:+7.2f}%  "
                  f"maxDD {r.max_drawdown*100:5.2f}%  robust {robust(r):+.4f}")


def main():
    base_cfg = DynamicGridConfig(**BASE)

    print("--- Training Q-tables (synthetic seeds 1-2 only) ---")
    print("training long-only Q-table...")
    q_long = train_q(lambda: make_layers(base_cfg), SCENARIOS, seeds=(1, 2),
                     epochs=8, n_bars=N_BARS, verbose=False)
    print("training dual (long+short) Q-table...")
    q_dual = train_q(lambda: make_dual_layers(base_cfg), SCENARIOS,
                     seeds=(1, 2), epochs=8, n_bars=N_BARS, verbose=False)
    save_q(q_long, "results/q_table_long.json")
    save_q(q_dual, "results/q_table_dual.json")

    print("\n=== Learned policy: DUAL portfolio ===")
    print(policy_table(q_dual))

    scores = part_a(base_cfg, q_long, q_dual)

    bear_all = load_bear_market()
    train = bear_all[:TRAIN_END]
    long_p = tune(train, DynamicGridEngine, 0)
    short_p = tune(train, ShortGridEngine, 0)
    part_bc(long_p, short_p, q_long, q_dual)

    print("\n=== Verdict (declared criterion: robust score) ===")
    best = max(scores, key=scores.get)
    print(f"Best on synthetic held-out: {best.strip()} ({scores[best]:+.4f})")
    print("See per-arena numbers above for B/C - a single 'winner' label")
    print("across all three arenas is exactly the kind of overclaim this")
    print("project's methodology tries to avoid. Report all three.")


if __name__ == "__main__":
    main()
