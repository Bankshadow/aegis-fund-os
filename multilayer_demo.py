"""Single-layer vs Multi-Layer Grid comparison across all synthetic scenarios.

Multi-layer stacks 3 DynamicGridEngine instances at different price scales
(fast/core/wide) sharing one equity/risk budget via MultiLayerOrchestrator.
Base config is the best-known, held-out-validated v2 config from
compare_versions.py / validate_v2.py.
"""

import numpy as np

from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          run_backtest, run_backtest_engine,
                          MultiLayerOrchestrator, make_layers)

N_BARS = 2000
SEEDS = (7, 11, 13)

# best known single-layer config (held-out validated, see docs/SYSTEM_SPEC.md)
BASE = dict(levels=10, atr_mult=2.642, risk_per_zone=0.027, stop_mult=0.59,
           shift_trigger=2.587, anomaly_z=2.389, consolidation_scale=1.174,
           cooldown_bars=73, tp_mult=1.765, trend_k=2.383, use_regime=True)

HEADER = f"{'scenario':<15} {'single ret':>10} {'single wDD':>11}   {'multi ret':>10} {'multi wDD':>10}"


def evaluate_single(cfg):
    out = {}
    for name in SCENARIOS:
        rets, dds = [], []
        for sd in SEEDS:
            r = run_backtest(generate_scenario(name, n_bars=N_BARS, seed=sd), cfg)
            rets.append(r.total_return)
            dds.append(r.max_drawdown)
        out[name] = (float(np.mean(rets)), max(dds))
    return out


def evaluate_multilayer(base_cfg, **layer_kwargs):
    out = {}
    for name in SCENARIOS:
        rets, dds = [], []
        for sd in SEEDS:
            ohlc = generate_scenario(name, n_bars=N_BARS, seed=sd)
            layers = make_layers(base_cfg, **layer_kwargs)
            orch = MultiLayerOrchestrator(layers)
            r = run_backtest_engine(ohlc, orch)
            rets.append(r.total_return)
            dds.append(r.max_drawdown)
        out[name] = (float(np.mean(rets)), max(dds))
    return out


def main():
    base_cfg = DynamicGridConfig(**BASE)
    single = evaluate_single(base_cfg)
    multi = evaluate_multilayer(base_cfg)

    print(HEADER)
    print("-" * len(HEADER))
    m1 = m2 = 0.0
    for name in SCENARIOS:
        r1, d1 = single[name]
        r2, d2 = multi[name]
        m1 += r1
        m2 += r2
        print(f"{name:<15} {r1*100:+9.2f}% {d1*100:10.2f}%   "
              f"{r2*100:+9.2f}% {d2*100:9.2f}%")
    print("-" * len(HEADER))
    print(f"{'mean return':<15} {m1/len(SCENARIOS)*100:+9.2f}% {'':>11}   "
          f"{m2/len(SCENARIOS)*100:+9.2f}%")

    # one detailed run with layer breakdown (sideways, seed 7)
    print("\n=== Layer breakdown (sideways, seed 7) ===")
    ohlc = generate_scenario("sideways", n_bars=N_BARS, seed=7)
    layers = make_layers(base_cfg)
    orch = MultiLayerOrchestrator(layers)
    run_backtest_engine(ohlc, orch)
    print(f"{'layer':<8} {'weight':>7} {'TPs':>5} {'stops':>6} {'rebld':>6} {'cons':>5}")
    for ls in orch.layer_stats():
        print(f"{ls.name:<8} {ls.weight*100:6.1f}% {ls.n_tp:5d} "
              f"{ls.n_stopouts:6d} {ls.n_rebuilds:6d} {ls.n_consolidations:5d}")


if __name__ == "__main__":
    main()
