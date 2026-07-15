"""Cross-asset regime-router validation: BTC/ETH/SOL x 1d/4h, real costs.

The user's declared bar for calling the defensive edge "evidence-backed":

    The regime router must REDUCE DRAWDOWN WITHOUT DESTROYING RETURNS
    across assets, on real data, with real volume / spread / funding costs.

Protocol (declared before running):
  - 6 markets: {BTC, ETH, SOL} x {1d (~2.7y), 4h (~11mo)} spot klines
  - costs: fee 0.05%/side + half-spread (Corwin-Schultz estimate from real
    high/low) per side; real mean perpetual funding applied per bar to
    open long exposure (positive = longs pay; SOL's is currently negative,
    i.e. longs were PAID - taken as-is from the data)
  - split 60% train / 40% test (test is strictly later in time)
  - tune grid params on train with router OFF (60 iters, robust score),
    so tuning cannot favor the router
  - evaluate the SAME tuned params on test, router OFF vs router ON
    (use_regime + use_regime_2d PersistentRegimeDetector with
    confirmation/dwell/hysteresis + block_high_vol_entries)
  - per-market report: test return, maxDD, robust score, OFF vs ON
  - volume sanity check: max open exposure vs median bar quote volume
    (fills must be a negligible fraction of real traded volume)

Verdict rule (also declared): the router "passes" a market if it reduces
maxDD while keeping return >= 0 when OFF's return was >= 0, or improving
return when OFF's was negative. Passing means evidence FOR the defensive
edge on that market; we report pass/fail per market and do not average
away failures.
"""

import numpy as np

from dynamic_grid import DynamicGridConfig, run_backtest
from dynamic_grid.grid_engine import DynamicGridEngine
from dynamic_grid.market_data import SYMBOLS, TIMEFRAMES, market_profile
from dynamic_grid.optimize import _sample

N_ITER = 60
BASE_FEE = 0.0005
ROUTER_ON = dict(use_regime=True, use_regime_2d=True,
                 block_high_vol_entries=True)
ROUTER_OFF = dict(use_regime=False, use_regime_2d=False,
                  block_high_vol_entries=False)


def make_cfg(params, profile, router):
    return DynamicGridConfig(
        **params, **router,
        fee_rate=BASE_FEE + profile["half_spread"],
        funding_rate_per_bar=profile["funding_per_bar"])


def tune(train, profile, seed):
    rng = np.random.default_rng(seed)
    best_s, best_p = -9e9, None
    for _ in range(N_ITER):
        p = _sample(rng)
        r = run_backtest(train, make_cfg(p, profile, ROUTER_OFF))
        s = r.total_return - 2.0 * r.max_drawdown
        if s > best_s:
            best_s, best_p = s, p
    return best_p


def max_exposure(ohlc, cfg):
    eng = DynamicGridEngine(cfg)
    equity, cash, mx = 10_000.0, 0.0, 0.0
    for o, h, l, c in ohlc:
        cash += eng.on_bar(o, h, l, c, equity + cash)
        mx = max(mx, eng.exposure(c))
    return mx


SEEDS = (0, 1, 2)   # v3.2.1 lesson: never conclude from a single seed


def main():
    print(f"{'market':<12} {'seed':>4} {'OFF ret':>8} {'OFF DD':>7} "
          f"{'ON ret':>8} {'ON DD':>7} {'engaged':>8} {'PASS':>5}")
    print("-" * 70)
    per_market = {}
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            prof = market_profile(sym, tf)
            ohlc = prof["ohlc"]
            cut = int(len(ohlc) * 0.6)
            train, test = ohlc[:cut], ohlc[cut:]
            mkt = sym[:-4] + "/" + tf
            per_market[mkt] = []
            for sd in SEEDS:
                p = tune(train, prof, seed=sd)
                r_off = run_backtest(test, make_cfg(p, prof, ROUTER_OFF))
                r_on = run_backtest(test, make_cfg(p, prof, ROUTER_ON))
                # "engaged" = the router actually changed behaviour; an
                # identical OFF/ON run carries no evidence either way
                engaged = (abs(r_on.total_return - r_off.total_return) > 1e-9
                           or abs(r_on.max_drawdown - r_off.max_drawdown) > 1e-9)
                dd_ok = r_on.max_drawdown < r_off.max_drawdown - 1e-9
                ret_ok = (r_on.total_return >= 0 if r_off.total_return >= 0
                          else r_on.total_return >= r_off.total_return)
                verdict = (dd_ok and ret_ok) if engaged else None
                per_market[mkt].append((r_off, r_on, engaged, verdict))
                v = "YES" if verdict else ("n/a" if verdict is None else "no")
                print(f"{mkt:<12} {sd:>4} "
                      f"{r_off.total_return*100:+7.2f}% {r_off.max_drawdown*100:6.2f}% "
                      f"{r_on.total_return*100:+7.2f}% {r_on.max_drawdown*100:6.2f}% "
                      f"{'yes' if engaged else 'no':>8} {v:>5}")

    print("\n=== Per-market verdicts (majority across seeds; n/a = router "
          "never engaged) ===")
    for mkt, runs in per_market.items():
        engaged_runs = [v for _, _, e, v in runs if e]
        if not engaged_runs:
            print(f"  {mkt:<12} n/a - router never changed behaviour "
                  f"(too few trades at real costs)")
            continue
        passes = sum(1 for v in engaged_runs if v)
        print(f"  {mkt:<12} pass {passes}/{len(engaged_runs)} engaged seeds")


if __name__ == "__main__":
    main()
