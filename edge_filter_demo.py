"""E16: Edge filter before zone build.

Criterion (declared BEFORE run):
  1. Unit tests: require_edge skips when TP < round-trip; builds when TP covers
     costs; default require_edge=False preserves legacy builds.
  2. Mechanism on real costs: a deliberately thin-spacing SOL/4h config
     (atr_mult small vs fee+CS-spread) MUST produce n_edge_skips > 0.
  3. Diagnostic on E13-tuned SOL/4h + BTC/4h: report whether the historical
     'SOL/4h does not trade because spacing < costs' hypothesis holds for
     tuned params. Do NOT claim the filter creates profitability.

Note: E13/E14 marked SOL/4h as n/a because OFF==ON (router idle), not because
zero fills. This demo separates that fact from the edge-filter mechanism test.
"""

from dynamic_grid import DynamicGridConfig, DynamicGridEngine, run_backtest_engine
from dynamic_grid.grid_engine import has_positive_edge, round_trip_cost_frac
from dynamic_grid.market_data import market_profile
from multiasset_demo import BASE_FEE, N_ITER, tune


def bake_fee(profile) -> float:
    return BASE_FEE + profile["half_spread"]


def run_engine(ohlc, cfg: DynamicGridConfig):
    eng = DynamicGridEngine(cfg)
    result = run_backtest_engine(ohlc, eng, liquidate_at_end=True)
    mid = float(ohlc[len(ohlc) // 2, 3])
    tp_frac = (cfg.tp_mult * eng.spacing / mid) if mid and eng.spacing else 0.0
    return eng, result, round_trip_cost_frac(cfg), tp_frac


def main():
    print("E16 — edge filter before _build()")
    print(f"tune iters={N_ITER}; fee bake = BASE_FEE + CS half_spread\n")

    sol = market_profile("SOLUSDT", "4h")
    btc = market_profile("BTCUSDT", "4h")
    sol_ohlc, btc_ohlc = sol["ohlc"], btc["ohlc"]
    sol_cut = int(len(sol_ohlc) * 0.6)
    btc_cut = int(len(btc_ohlc) * 0.6)
    sol_train, sol_test = sol_ohlc[:sol_cut], sol_ohlc[sol_cut:]
    btc_train, btc_test = btc_ohlc[:btc_cut], btc_ohlc[btc_cut:]

    # --- Criterion 2: forced thin spacing must skip ---
    thin = DynamicGridConfig(
        atr_period=14, atr_mult=0.15, tp_mult=1.0, levels=4,
        use_regime=False, require_edge=True,
        fee_rate=bake_fee(sol), half_spread=0.0,
        funding_rate_per_bar=sol["funding_per_bar"],
        cooldown_bars=0, trend_k=100.0)
    thin_eng, thin_r, thin_rt, thin_tp = run_engine(sol_test, thin)
    c2 = thin_eng.n_edge_skips > 0
    print("=== Criterion 2: thin-spacing SOL/4h (forced atr_mult=0.15) ===")
    print(f"  rt={thin_rt*1e4:.2f}bps  last_tp~={thin_tp*1e4:.2f}bps  "
          f"rebuilds={thin_eng.n_rebuilds}  edge_skips={thin_eng.n_edge_skips}  "
          f"TPs={thin_eng.n_tp}  ret={thin_r.total_return*100:+.2f}%")
    print(f"  -> {'PASS' if c2 else 'FAIL'}: edge_skips > 0\n")

    # --- Criterion 3: E13-tuned diagnostic (hypothesis check) ---
    print("=== Criterion 3: E13-tuned diagnostic (hypothesis, not a pass gate) ===")
    print(f"{'market':<9} {'edge':>5} {'ret':>8} {'DD':>7} "
          f"{'rebuild':>7} {'skips':>6} {'TPs':>5} "
          f"{'rt_bps':>7} {'tp_bps':>7}")
    print("-" * 78)
    for label, prof, train, test in (
        ("SOL/4h", sol, sol_train, sol_test),
        ("BTC/4h", btc, btc_train, btc_test),
    ):
        params = tune(train, prof, seed=0)
        for require_edge in (False, True):
            cfg = DynamicGridConfig(
                **params, use_regime=False, require_edge=require_edge,
                fee_rate=bake_fee(prof), half_spread=0.0,
                funding_rate_per_bar=prof["funding_per_bar"])
            eng, result, rt, tp_frac = run_engine(test, cfg)
            print(f"{label:<9} {'ON' if require_edge else 'OFF':>5} "
                  f"{result.total_return*100:>+7.2f}% {result.max_drawdown*100:>6.2f}% "
                  f"{eng.n_rebuilds:>7d} {eng.n_edge_skips:>6d} {eng.n_tp:>5d} "
                  f"{rt*1e4:>7.2f} {tp_frac*1e4:>7.2f}")

    print("\nNotes:")
    print("  - E13/E14 SOL/4h n/a = OFF==ON (router idle), not zero fills.")
    print("  - Tuned atr_mult/tp_mult on SOL/4h usually CLEAR round-trip; "
          "edge filter stays quiet.")
    print("  - Filter still refuses negative-EV zones when spacing is thin "
          f"(criterion 2 {'PASS' if c2 else 'FAIL'}).")
    if not c2:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
