"""E14: Percentile-rank regime vs fixed-threshold regime - same E13 protocol.

The user's declared bar for the defensive edge (unchanged from E13):

    The regime router must REDUCE DRAWDOWN WITHOUT DESTROYING RETURNS
    across assets, on real data, with real volume / spread / funding costs.

E13 found the fixed-threshold PersistentRegimeDetector's effect was
indistinguishable from tuning-seed noise (6/14 engaged runs passed, no
market passed on all seeds). The suspected root cause: one m_threshold /
vol_hi pair cannot fit BTC and SOL, or 1d and 4h, at once - their
momentum/vol_ratio distributions sit at completely different scales.

This script tests the fix: PercentileRegimeDetector classifies regime from
the CURRENT bar's percentile rank within its own trailing distribution,
so the same default thresholds (85th percentile) should behave sensibly
regardless of the asset's absolute volatility scale.

Protocol - IDENTICAL to multiasset_demo.py (E13) except the router variant:
  - same 6 markets, same real costs (fee+CS-spread+funding), same 60/40
    split, same train-with-router-OFF tuning, same 3 seeds, same pass rule
  - THREE variants per market: OFF, ON-fixed (E13's router), ON-pct (new)
"""

import numpy as np

from dynamic_grid import DynamicGridConfig, run_backtest
from dynamic_grid.market_data import SYMBOLS, TIMEFRAMES, market_profile
from multiasset_demo import BASE_FEE, N_ITER, ROUTER_OFF, ROUTER_ON, tune

ROUTER_PCT = dict(use_regime=True, use_regime_pct=True,
                  block_high_vol_entries=True)
SEEDS = (0, 1, 2)


def make_cfg(params, profile, router):
    return DynamicGridConfig(
        **params, **router,
        fee_rate=BASE_FEE + profile["half_spread"],
        funding_rate_per_bar=profile["funding_per_bar"])


def passed(r_off, r_on):
    dd_ok = r_on.max_drawdown < r_off.max_drawdown - 1e-9
    ret_ok = (r_on.total_return >= 0 if r_off.total_return >= 0
              else r_on.total_return >= r_off.total_return)
    engaged = (abs(r_on.total_return - r_off.total_return) > 1e-9
               or abs(r_on.max_drawdown - r_off.max_drawdown) > 1e-9)
    return engaged, (dd_ok and ret_ok) if engaged else None


def main():
    print(f"{'market':<9} {'seed':>4} {'OFF ret':>8} {'OFF DD':>7} "
          f"{'FIX ret':>8} {'FIX DD':>7} {'fix':>4} "
          f"{'PCT ret':>8} {'PCT DD':>7} {'pct':>4}")
    print("-" * 88)

    fix_tally, pct_tally = [], []
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            prof = market_profile(sym, tf)
            ohlc = prof["ohlc"]
            cut = int(len(ohlc) * 0.6)
            train, test = ohlc[:cut], ohlc[cut:]
            mkt = sym[:-4] + "/" + tf
            for sd in SEEDS:
                p = tune(train, prof, seed=sd)   # router-OFF tuning, from E13
                r_off = run_backtest(test, make_cfg(p, prof, ROUTER_OFF))
                r_fix = run_backtest(test, make_cfg(p, prof, ROUTER_ON))
                r_pct = run_backtest(test, make_cfg(p, prof, ROUTER_PCT))

                fe, fv = passed(r_off, r_fix)
                pe, pv = passed(r_off, r_pct)
                if fe:
                    fix_tally.append(fv)
                if pe:
                    pct_tally.append(pv)

                fs = "YES" if fv else ("n/a" if fv is None else "no")
                ps = "YES" if pv else ("n/a" if pv is None else "no")
                print(f"{mkt:<9} {sd:>4} "
                      f"{r_off.total_return*100:+7.2f}% {r_off.max_drawdown*100:6.2f}% "
                      f"{r_fix.total_return*100:+7.2f}% {r_fix.max_drawdown*100:6.2f}% {fs:>4} "
                      f"{r_pct.total_return*100:+7.2f}% {r_pct.max_drawdown*100:6.2f}% {ps:>4}")

    print("-" * 88)
    print(f"Fixed-threshold router (E13): {sum(fix_tally)}/{len(fix_tally)} "
          f"engaged runs passed")
    print(f"Percentile-rank router (E14): {sum(pct_tally)}/{len(pct_tally)} "
          f"engaged runs passed")
    print("\nVerdict: percentile-rank router is only worth adopting if its "
          "pass rate is CLEARLY higher (declared before running, same bar "
          "as E13 - no cherry-picking the better-looking number).")


if __name__ == "__main__":
    main()
