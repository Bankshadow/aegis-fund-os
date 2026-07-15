"""Train the RL risk governor, then judge it honestly on held-out seeds.

Protocol (declared in rl_agent.py BEFORE evaluation):
  train : synthetic scenarios x seeds (1,2), 8 epochs of Q-learning
  judge : greedy policy on held-out seeds (7,11,13) - never seen in training
  metric: robust score = return - 2*maxDD (the project standard)
  vs    : OFF  = fixed weights (MultiLayerOrchestrator)
          RULE = MemoryOrchestrator's hand-written rules (v3.5)
          RL   = learned Q-table policy
"""

import os

import numpy as np

from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          run_backtest_engine, MultiLayerOrchestrator,
                          make_layers)
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.rl_agent import RLGovernor, train_q, policy_table, save_q
from multilayer_demo import BASE

SEEDS_EVAL = (7, 11, 13)
N_BARS = 2000


def evaluate(make_engine):
    per_scen = {}
    for name in SCENARIOS:
        scores, rets, dds = [], [], []
        for sd in SEEDS_EVAL:
            ohlc = generate_scenario(name, n_bars=N_BARS, seed=sd)
            r = run_backtest_engine(ohlc, make_engine())
            rets.append(r.total_return)
            dds.append(r.max_drawdown)
            scores.append(r.total_return - 2.0 * r.max_drawdown)
        per_scen[name] = (np.mean(rets), max(dds), np.mean(scores))
    return per_scen


def main():
    base_cfg = DynamicGridConfig(**BASE)
    layers = lambda: make_layers(base_cfg)

    print("=== Training Q-table (synthetic scenarios, seeds 1-2 only) ===")
    q = train_q(layers, SCENARIOS, seeds=(1, 2), epochs=8, n_bars=N_BARS)
    os.makedirs("results", exist_ok=True)
    save_q(q, os.path.join("results", "q_table.json"))
    print("\n=== Learned policy (fully auditable) ===")
    print(policy_table(q))

    print("\n=== Held-out evaluation (seeds 7/11/13, greedy policy) ===")
    variants = {
        "OFF (fixed)": lambda: MultiLayerOrchestrator(layers()),
        "RULE (v3.5)": lambda: MemoryOrchestrator(layers()),
        "RL (learned)": lambda: RLGovernor(layers(), q=q, learn=False),
    }
    results = {k: evaluate(v) for k, v in variants.items()}

    hdr = f"{'scenario':<15}" + "".join(f"{k:>22}" for k in variants)
    print("\n" + hdr + "   (robust score)")
    print("-" * len(hdr))
    means = {k: [] for k in variants}
    for name in SCENARIOS:
        row = f"{name:<15}"
        for k in variants:
            s = results[k][name][2]
            means[k].append(s)
            row += f"{s:>+22.4f}"
        print(row)
    print("-" * len(hdr))
    print(f"{'MEAN':<15}" + "".join(f"{np.mean(means[k]):>+22.4f}"
                                    for k in variants))
    print(f"\nDetail (mean ret / worst DD per variant):")
    for k in variants:
        mret = np.mean([results[k][n][0] for n in SCENARIOS])
        wdd = max(results[k][n][1] for n in SCENARIOS)
        print(f"  {k:<14} ret {mret*100:+6.2f}%  worstDD {wdd*100:5.2f}%")


if __name__ == "__main__":
    main()
