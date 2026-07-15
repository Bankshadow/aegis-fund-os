"""Walk-forward validation on REAL BTC/USDT daily data (Binance, public API).

This is the first test of the Dynamic Grid system on real market data,
closing the biggest known gap listed in every prior version's README:
"tested on synthetic data only".

Data: 1000 daily bars, BTC/USDT, Oct 2023 - Jul 2026 (data/btc_binance_1d.json).
Covers a full bull run, the 2024-2025 top, and the 2026 drawdown - real
regime variety, not cherry-picked.
"""

import csv
import os

import numpy as np

from dynamic_grid.real_data import load_binance_klines
from dynamic_grid.walk_forward import walk_forward

TRAIN_BARS = 250   # ~8-9 months in-sample
TEST_BARS = 60     # ~2 months out-of-sample
STEP_BARS = 60     # non-overlapping test windows
N_ITER = 60        # optimizer iterations per fold (kept modest - see caveats)


def main():
    ohlc = load_binance_klines()
    print(f"Loaded {len(ohlc)} real daily BTC/USDT bars "
          f"(price range {ohlc[:,3].min():.0f}-{ohlc[:,3].max():.0f})")

    folds = walk_forward(ohlc, TRAIN_BARS, TEST_BARS, STEP_BARS, N_ITER)
    print(f"\n{len(folds)} walk-forward folds "
          f"(train={TRAIN_BARS}d, test={TEST_BARS}d, step={STEP_BARS}d)\n")

    header = (f"{'fold':<5}{'bars':<15}{'dyn ret':>9}{'dyn maxDD':>11}"
             f"{'dyn CVaR5%':>12}{'static ret':>11}{'static maxDD':>13}")
    print(header)
    print("-" * len(header))

    rows = []
    for f in folds:
        print(f"{f.fold:<5}{f.test_start:>5}-{f.test_end:<9}"
              f"{f.dynamic_return*100:+8.2f}% {f.dynamic_maxdd*100:9.2f}% "
              f"{f.dynamic_cvar5*100:+10.3f}% {f.static_return*100:+9.2f}% "
              f"{f.static_maxdd*100:11.2f}%")
        rows.append(f)

    dyn_rets = [f.dynamic_return for f in folds]
    dyn_dds = [f.dynamic_maxdd for f in folds]
    stat_rets = [f.static_return for f in folds]
    stat_dds = [f.static_maxdd for f in folds]

    print("-" * len(header))
    print(f"{'MEAN':<20}{np.mean(dyn_rets)*100:+8.2f}% {np.mean(dyn_dds)*100:9.2f}%"
          f"{'':>13}{np.mean(stat_rets)*100:+9.2f}% {np.mean(stat_dds)*100:11.2f}%")
    print(f"{'WORST':<20}{min(dyn_rets)*100:+8.2f}% {max(dyn_dds)*100:9.2f}%"
          f"{'':>13}{min(stat_rets)*100:+9.2f}% {max(stat_dds)*100:11.2f}%")

    os.makedirs("results", exist_ok=True)
    out_path = os.path.join("results", "walk_forward_btc.csv")
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fold", "test_start", "test_end", "dynamic_return",
                    "dynamic_maxdd", "dynamic_cvar5", "static_return",
                    "static_maxdd", "best_params"])
        for f in rows:
            w.writerow([f.fold, f.test_start, f.test_end,
                        f"{f.dynamic_return:.6f}", f"{f.dynamic_maxdd:.6f}",
                        f"{f.dynamic_cvar5:.6f}", f"{f.static_return:.6f}",
                        f"{f.static_maxdd:.6f}", f.params])
    print(f"\nsaved: {out_path}")

    print("\n--- Known limitations of this run (read before trusting the numbers) ---")
    print("1. Single asset (BTC/USDT), single exchange feed - no cross-asset validation")
    print(f"2. {N_ITER} optimizer iterations/fold is modest (synthetic tests use 150) - "
          "in-sample fit is coarse")
    print("3. Only", len(folds), "OOS folds - too few to trust a Sharpe-like statistic; "
          "read this as a directional check, not a final verdict")
    print("4. No slippage model beyond the existing fee_rate; real fills would be worse")
    print("5. 1000 bars = one long bull market + one drawdown - no genuine bear market "
          "or multi-year sideways regime represented")


if __name__ == "__main__":
    main()
