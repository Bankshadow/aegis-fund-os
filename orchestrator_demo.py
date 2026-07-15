"""A/B evaluation: MemoryOrchestrator (memory loop ON) vs fixed weights (OFF).

Judging criterion DECLARED BEFORE running (same standard as every prior
ablation in this project): robust score = total_return - 2*max_drawdown,
averaged across 6 synthetic scenarios x 3 seeds. Whichever way it comes
out, the number gets reported as-is.

OFF = MultiLayerOrchestrator (v3 fixed weights, no memory loop)
ON  = MemoryOrchestrator    (reads shared DecisionLog every 200 bars,
                             cuts/restores layer budgets by rule)
"""

import numpy as np

from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          run_backtest_engine, MultiLayerOrchestrator,
                          make_layers)
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from multilayer_demo import BASE

SEEDS = (7, 11, 13)
N_BARS = 2000


def evaluate(make_engine):
    rows = {}
    for name in SCENARIOS:
        rets, dds, scores = [], [], []
        for sd in SEEDS:
            ohlc = generate_scenario(name, n_bars=N_BARS, seed=sd)
            r = run_backtest_engine(ohlc, make_engine())
            rets.append(r.total_return)
            dds.append(r.max_drawdown)
            scores.append(r.total_return - 2.0 * r.max_drawdown)
        rows[name] = (float(np.mean(rets)), max(dds), float(np.mean(scores)))
    return rows


def main():
    base_cfg = DynamicGridConfig(**BASE)
    off = evaluate(lambda: MultiLayerOrchestrator(make_layers(base_cfg)))
    on = evaluate(lambda: MemoryOrchestrator(make_layers(base_cfg)))

    hdr = (f"{'scenario':<15} {'OFF ret':>8} {'OFF wDD':>8} {'OFF score':>10}"
           f"   {'ON ret':>8} {'ON wDD':>8} {'ON score':>10}")
    print(hdr)
    print("-" * len(hdr))
    off_s, on_s = [], []
    for name in SCENARIOS:
        r0, d0, s0 = off[name]
        r1, d1, s1 = on[name]
        off_s.append(s0)
        on_s.append(s1)
        print(f"{name:<15} {r0*100:+7.2f}% {d0*100:7.2f}% {s0:+10.4f}"
              f"   {r1*100:+7.2f}% {d1*100:7.2f}% {s1:+10.4f}")
    print("-" * len(hdr))
    print(f"{'MEAN robust score':<15} {'':>8} {'':>8} {np.mean(off_s):+10.4f}"
          f"   {'':>8} {'':>8} {np.mean(on_s):+10.4f}")

    # show the loop actually firing (one run's audit trail)
    print("\n=== Sample orchestrator interventions (downtrend, seed 7) ===")
    orch = MemoryOrchestrator(make_layers(base_cfg))
    run_backtest_engine(generate_scenario("downtrend", n_bars=N_BARS, seed=7),
                        orch)
    acts = [e for e in orch.log.events if e.agent_id == "orchestrator"]
    print(f"reviews={orch.n_reviews}, interventions={orch.n_interventions}")
    for e in acts[:8]:
        print(" -", e.to_knowledge())
    if not acts:
        print(" (no interventions fired in this run)")


if __name__ == "__main__":
    main()
