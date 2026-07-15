"""End-to-end demo: Static grid vs Dynamic grid + parameter optimization.

Usage:
    python run_demo.py            # quick comparison + 80-iter optimization
    python run_demo.py --fast     # comparison only, skip optimization
"""

import csv
import os
import sys

from dynamic_grid import (DynamicGridConfig, SCENARIOS, generate_scenario,
                          optimize, run_backtest)
from dynamic_grid.backtest import compare_engines

N_BARS = 2000
SEED = 7
HEADER = (f"{'scenario':<15} {'engine':<8} {'return':>9}  {'maxDD':>8}  "
          f"{'MAR':>7}  {'TPs':>5}  {'stops':>5}  {'rebld':>4}  {'cons':>4}")


def comparison(cfg: DynamicGridConfig, tag: str):
    print(f"\n=== Static vs Dynamic grid ({tag}) | {N_BARS} bars/scenario ===")
    print(HEADER)
    print("-" * len(HEADER))
    rows = []
    for name in SCENARIOS:
        ohlc = generate_scenario(name, n_bars=N_BARS, seed=SEED)
        st, dy = compare_engines(ohlc, cfg)
        print(f"{name:<15} {'static':<8} {st.row()}")
        print(f"{'':<15} {'dynamic':<8} {dy.row()}")
        rows.append((name, "static", st))
        rows.append((name, "dynamic", dy))
    return rows


def save_rows(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "engine", "total_return", "max_drawdown",
                    "mar", "n_tp", "n_stopouts", "n_rebuilds",
                    "n_consolidations", "final_equity"])
        for name, eng, r in rows:
            w.writerow([name, eng, f"{r.total_return:.6f}",
                        f"{r.max_drawdown:.6f}", f"{r.mar:.4f}", r.n_tp,
                        r.n_stopouts, r.n_rebuilds, r.n_consolidations,
                        f"{r.final_equity:.2f}"])
    print(f"\nsaved: {path}")


def main():
    base_cfg = DynamicGridConfig()
    rows = comparison(base_cfg, "default params")
    save_rows(rows, os.path.join("results", "baseline_comparison.csv"))

    if "--fast" in sys.argv:
        return

    print("\n=== Optimizing dynamic grid across all scenarios ===")
    board = optimize(n_iter=150, n_bars=N_BARS)
    best_score, best_params, _ = board[0]
    print(f"\nbest robust score: {best_score:+.4f}")
    print("best params:")
    for k, v in best_params.items():
        print(f"  {k:<22} {v}")

    best_cfg = DynamicGridConfig(**best_params)
    rows = comparison(best_cfg, "optimized params")
    save_rows(rows, os.path.join("results", "optimized_comparison.csv"))

    with open(os.path.join("results", "best_params.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["param", "value"])
        for k, v in best_params.items():
            w.writerow([k, v])
        w.writerow(["robust_score", f"{best_score:.4f}"])


if __name__ == "__main__":
    main()
