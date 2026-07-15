"""Ablation: v1 (no regime adaptation) vs v2 (regime-adaptive) dynamic grid.

Same base parameters (best set from the v1 optimization run), multiple
seeds per scenario, so the only difference measured is the regime module.
"""

import numpy as np

from dynamic_grid import DynamicGridConfig, SCENARIOS, generate_scenario, run_backtest

# best params from the v1 optimization run (2026-07-06)
V1_BEST = dict(levels=10, atr_mult=2.642, risk_per_zone=0.027, stop_mult=0.59,
               shift_trigger=2.587, anomaly_z=2.389, consolidation_scale=1.174,
               cooldown_bars=73, tp_mult=1.765, trend_k=2.383)

SEEDS = (7, 11, 13)
N_BARS = 2000


def evaluate(cfg):
    """Mean return / max DD per scenario across seeds."""
    out = {}
    for name in SCENARIOS:
        rets, dds = [], []
        for sd in SEEDS:
            r = run_backtest(generate_scenario(name, n_bars=N_BARS, seed=sd), cfg)
            rets.append(r.total_return)
            dds.append(r.max_drawdown)
        out[name] = (np.mean(rets), max(dds))
    return out


def main():
    v1 = evaluate(DynamicGridConfig(**V1_BEST, use_regime=False))
    v2 = evaluate(DynamicGridConfig(**V1_BEST, use_regime=True))

    print(f"{'scenario':<15} {'v1 ret':>8} {'v1 wDD':>8}   {'v2 ret':>8} {'v2 wDD':>8}")
    print("-" * 55)
    tot1 = tot2 = 0.0
    for name in SCENARIOS:
        r1, d1 = v1[name]
        r2, d2 = v2[name]
        tot1 += r1
        tot2 += r2
        print(f"{name:<15} {r1*100:+7.2f}% {d1*100:7.2f}%   "
              f"{r2*100:+7.2f}% {d2*100:7.2f}%")
    print("-" * 55)
    print(f"{'mean return':<15} {tot1/len(SCENARIOS)*100:+7.2f}%"
          f"{'':>10} {tot2/len(SCENARIOS)*100:+7.2f}%")
    print("\n(ret = mean total return over seeds, wDD = worst max drawdown)")


if __name__ == "__main__":
    main()
