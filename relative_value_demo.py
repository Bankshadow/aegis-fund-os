"""E18: Cross-asset relative-value (alt/BTC momentum) replaces own-price direction.

Criterion (declared BEFORE run):
  Protocol: ETH/SOL x 4h only (BTC is numeraire, not traded here), real costs
  (fee + CS half-spread + mean funding cost), tune train 60% with relative
  OFF, test 40%, 3 seeds. OFF = percentile own-price regime; ON = relative
  vs BTC replaces direction. Funding bias OFF both sides.

  Pass per seed (E13 spirit): ON reduces maxDD and does not destroy return.
  Count only ENGAGED runs (n_relative_tilts > 0 OR results differ from OFF).

  Overall: PASS if engaged pass rate > 50%. Report failures equally.
  Do not claim live readiness; default stays off regardless until HANDOFF update.
"""

from dynamic_grid import DynamicGridConfig, RegimeSwitchingOrchestrator, run_backtest_engine
from dynamic_grid.market_data import market_profile, pair_ratio_series
from multiasset_demo import BASE_FEE, N_ITER, tune

SEEDS = (0, 1, 2)
ALTS = ("ETHUSDT", "SOLUSDT")
ROUTER_BASE = dict(
    use_regime=True, use_regime_pct=True, block_high_vol_entries=True,
    use_funding_bias=False,
)


def make_cfg(params, profile, use_relative: bool) -> DynamicGridConfig:
    return DynamicGridConfig(
        **params, **ROUTER_BASE,
        use_relative_value=use_relative,
        fee_rate=BASE_FEE + profile["half_spread"],
        funding_rate_per_bar=profile["funding_per_bar"],
        half_spread=0.0,
    )


def passed(r_off, r_on):
    dd_ok = r_on.max_drawdown < r_off.max_drawdown - 1e-9
    ret_ok = (r_on.total_return >= 0 if r_off.total_return >= 0
              else r_on.total_return >= r_off.total_return)
    return dd_ok and ret_ok


def run_one(ohlc, cfg, relative_mom):
    eng = RegimeSwitchingOrchestrator(
        cfg, range_long_weight=0.75, high_vol_risk_scale=0.5,
        relative_series=relative_mom)
    result = run_backtest_engine(ohlc, eng, liquidate_at_end=True)
    return result, eng.n_relative_tilts


def main():
    print("E18 criterion: engaged pass rate > 50%")
    print(f"tune iters={N_ITER}; ETH/SOL 4h vs BTC; relative replaces direction\n")
    print(f"{'market':<9} {'seed':>4} {'OFF ret':>8} {'OFF DD':>7} "
          f"{'ON ret':>8} {'ON DD':>7} {'tilts':>6} {'eng':>4} {'pass':>5}")
    print("-" * 78)

    tally = []
    for sym in ALTS:
        lookback = 20
        prof = market_profile(sym, "4h")
        pair = pair_ratio_series(sym, "BTCUSDT", "4h", lookback=lookback)
        ohlc = prof["ohlc"]
        mom = pair["momentum"]
        cut = int(len(ohlc) * 0.6)
        train, test = ohlc[:cut], ohlc[cut:]
        mom_test = mom[cut:]
        label = sym[:-4] + "/4h"
        for seed in SEEDS:
            params = tune(train, prof, seed=seed)
            cfg_off = make_cfg(params, prof, False)
            cfg_on = make_cfg(params, prof, True)
            r_off, _ = run_one(test, cfg_off, mom_test)
            r_on, tilts = run_one(test, cfg_on, mom_test)
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
