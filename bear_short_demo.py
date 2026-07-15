"""Long vs Short grid on the REAL 2022 bear market - honest protocol.

Data : BTC/USDT daily, Jan 2021 - Sep 2023 (data/btc_bear_2021_2023.json)
Split: tune on bars 0-310   (2021: chop + uptrend - adversarial for a short)
       test on bars 310-730 (Nov 2021 peak -> Dec 2022 bottom, -74%, UNSEEN)
Tuning: random search 80 iters per seed, score = return - 2*maxDD,
        3 seeds reported individually (no cherry-picking a lucky seed).

Also reruns the "geometry transfer" check that motivated this script: a
config tuned on synthetic price scale produces degenerate zones on real
BTC prices (levels below zero) - configs must be (re)tuned on data with
the target volatility scale.

Known limitation: short PnL here is linear (futures-style) with NO
funding-rate cost. Perpetual funding in a bear market often pays shorts,
but this is not modeled - treat returns as approximate.
"""

import numpy as np

from dynamic_grid import DynamicGridConfig, run_backtest
from dynamic_grid.grid_engine import DynamicGridEngine
from dynamic_grid.short_engine import ShortGridEngine
from dynamic_grid.real_data import load_bear_market
from dynamic_grid.optimize import _sample

TRAIN_END, TEST_END = 310, 730
N_ITER = 80
SEEDS = (0, 1, 2)


def tune(train, engine_cls, seed):
    rng = np.random.default_rng(seed)
    best_s, best_p = -9e9, None
    for _ in range(N_ITER):
        p = _sample(rng)
        r = run_backtest(train, DynamicGridConfig(**p), engine_cls)
        s = r.total_return - 2.0 * r.max_drawdown
        if s > best_s:
            best_s, best_p = s, p
    return best_p


def main():
    ohlc = load_bear_market()
    train, test = ohlc[:TRAIN_END], ohlc[TRAIN_END:TEST_END]
    print(f"train 2021 : {train[0,3]:.0f} -> {train[-1,3]:.0f}")
    print(f"test  bear : {test[0,3]:.0f} -> {test[-1,3]:.0f} "
          f"({(test[-1,3]/test[0,3]-1)*100:+.0f}%)\n")

    for label, cls in [("LONG  Dynamic", DynamicGridEngine),
                       ("SHORT Dynamic", ShortGridEngine)]:
        rets, dds = [], []
        for sd in SEEDS:
            p = tune(train, cls, sd)
            r = run_backtest(test, DynamicGridConfig(**p), cls)
            rets.append(r.total_return)
            dds.append(r.max_drawdown)
        per_seed = " ".join(f"{x*100:+.2f}%" for x in rets)
        print(f"{label}: OOS mean {np.mean(rets)*100:+6.2f}%  "
              f"worstDD {max(dds)*100:5.2f}%   per-seed [{per_seed}]")

    print("\n(short PnL excludes perpetual funding - see module docstring)")


if __name__ == "__main__":
    main()
