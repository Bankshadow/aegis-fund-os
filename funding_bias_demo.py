"""E17: Funding-rate directional bias (percentile-rank) on real 4h data.

Criterion (declared BEFORE run):
  Protocol: BTC/ETH/SOL x 4h only (funding coverage overlaps test window),
  real costs (fee + CS half-spread baked into fee_rate + mean funding cost),
  tune grid params on train 60% with funding bias OFF, evaluate test 40%,
  3 seeds, variants OFF vs ON (same percentile regime router; only
  use_funding_bias differs). Funding tilt applies only in sideways.

  Pass per market/seed (E13 spirit): ON reduces maxDD and does not destroy
  return (ret >= 0 if OFF ret >= 0, else ret >= OFF ret). Count only
  ENGAGED runs (n_funding_tilts > 0 OR results differ from OFF).

  Overall: PASS if engaged pass rate > 50%. Report failures equally.
  Do not claim live readiness.
"""

import numpy as np

from dynamic_grid import DynamicGridConfig, RegimeSwitchingOrchestrator, run_backtest_engine
from dynamic_grid.market_data import SYMBOLS, market_profile
from multiasset_demo import BASE_FEE, N_ITER, tune

SEEDS = (0, 1, 2)
ROUTER_BASE = dict(
    use_regime=True, use_regime_pct=True, block_high_vol_entries=True,
)


def make_cfg(params, profile, use_funding_bias: bool) -> DynamicGridConfig:
    return DynamicGridConfig(
        **params, **ROUTER_BASE,
        use_funding_bias=use_funding_bias,
        fee_rate=BASE_FEE + profile["half_spread"],
        funding_rate_per_bar=profile["funding_per_bar"],
        half_spread=0.0,
    )


def passed(r_off, r_on):
    dd_ok = r_on.max_drawdown < r_off.max_drawdown - 1e-9
    ret_ok = (r_on.total_return >= 0 if r_off.total_return >= 0
              else r_on.total_return >= r_off.total_return)
    return dd_ok and ret_ok


def run_one(ohlc, cfg, funding_series):
    # Slice funding to the same window as ohlc when caller passes a slice.
    eng = RegimeSwitchingOrchestrator(
        cfg, range_long_weight=0.75, high_vol_risk_scale=0.5,
        funding_series=funding_series)
    result = run_backtest_engine(ohlc, eng, liquidate_at_end=True)
    return result, eng.n_funding_tilts


def main():
    print("E17 criterion: engaged pass rate > 50%")
    print(f"tune iters={N_ITER}; 4h only; funding bias sideways-only\n")
    print(f"{'market':<9} {'seed':>4} {'OFF ret':>8} {'OFF DD':>7} "
          f"{'ON ret':>8} {'ON DD':>7} {'tilts':>6} {'eng':>4} {'pass':>5}")
    print("-" * 78)

    tally = []  # engaged pass bools
    for sym in SYMBOLS:
        prof = market_profile(sym, "4h")
        ohlc = prof["ohlc"]
        funding = prof["funding_series"]
        cut = int(len(ohlc) * 0.6)
        train, test = ohlc[:cut], ohlc[cut:]
        fund_train, fund_test = funding[:cut], funding[cut:]
        label = sym[:-4] + "/4h"
        for seed in SEEDS:
            params = tune(train, prof, seed=seed)
            cfg_off = make_cfg(params, prof, False)
            cfg_on = make_cfg(params, prof, True)
            r_off, _ = run_one(test, cfg_off, fund_test)
            r_on, tilts = run_one(test, cfg_on, fund_test)
            engaged = (tilts > 0
                       or abs(r_on.total_return - r_off.total_return) > 1e-9
                       or abs(r_on.max_drawdown - r_off.max_drawdown) > 1e-9)
            ok = passed(r_off, r_on) if engaged else None
            if engaged:
                tally.append(bool(ok))
            tag = "YES" if ok else ("n/a" if ok is None else "no")
            print(f"{label:<9} {seed:>4} "
                  f"{r_off.total_return*100:>+7.2f}% {r_off.max_drawdown*100:>6.2f}% "
                  f"{r_on.total_return*100:>+7.2f}% {r_on.max_drawdown*100:>6.2f}% "
                  f"{tilts:>6d} {'Y' if engaged else 'N':>4} {tag:>5}")

    n = len(tally)
    wins = sum(tally)
    rate = (wins / n) if n else 0.0
    print()
    print(f"Engaged pass rate: {wins}/{n} ({rate:.0%})")
    if n == 0:
        print("FAIL: no engaged runs")
    elif rate > 0.5:
        print("PASS: engaged pass rate > 50%")
    else:
        print("FAIL: engaged pass rate <= 50%")


if __name__ == "__main__":
    main()
