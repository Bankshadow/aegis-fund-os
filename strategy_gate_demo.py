"""Run the strategy promotion gate on a real BTC 4h candidate comparison.

E15 protocol (declared before run): A/B fixed-threshold (use_regime_2d) vs
percentile-rank (use_regime_pct) on the SAME purged-CV gate. Report PASS/FAIL
and median OOS for both detectors. Do not cherry-pick or claim live readiness.
"""

from dynamic_grid.allocator import RiskBudgetAllocator
from dynamic_grid.backtest import run_backtest_engine
from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.market_data import load_klines
from dynamic_grid.regime_switch import RegimeSwitchingOrchestrator
from dynamic_grid.validation import ValidationGate, combinatorial_purged_screen


def make_candidate(cfg: DynamicGridConfig, use_allocator: bool):
    def evaluate(window):
        allocator = None
        if use_allocator:
            allocator = RiskBudgetAllocator(
                {"long": 0.75, "short": 0.25}, max_weight=0.75,
                lookback=20, performance_tilt=2.0)
        engine = RegimeSwitchingOrchestrator(
            cfg, range_long_weight=0.75, high_vol_risk_scale=0.5,
            allocator=allocator)
        return run_backtest_engine(window, engine, liquidate_at_end=True)

    return evaluate


def run_gate(ohlc, label: str, cfg: DynamicGridConfig):
    report = combinatorial_purged_screen(
        ohlc,
        {"fixed_router": make_candidate(cfg, False),
         "allocated_router": make_candidate(cfg, True)},
        n_groups=6, n_test_groups=2, purge_groups=1)
    gate = ValidationGate()
    passed = gate.passes(report)
    print(f"\n=== {label} ===")
    print(f"validation folds: {len(report.folds)}")
    print(f"median OOS score: {report.median_test_score:+.4f}")
    print(f"selection failure rate: {report.selection_failure_rate:.1%}")
    print(f"promotion gate: {'PASS' if passed else 'FAIL'}")
    return {
        "label": label,
        "median_oos": report.median_test_score,
        "failure_rate": report.selection_failure_rate,
        "passed": passed,
        "n_folds": len(report.folds),
    }


if __name__ == "__main__":
    ohlc = load_klines("BTCUSDT", "4h")["ohlc"]
    common = dict(
        conservative_intrabar=True,
        stop_slippage_bps=5.0,
        book_entry_fees_immediately=True,
    )
    fixed_cfg = DynamicGridConfig(use_regime_2d=True, **common)
    pct_cfg = DynamicGridConfig(use_regime_pct=True, **common)

    fixed = run_gate(ohlc, "fixed-threshold (use_regime_2d)", fixed_cfg)
    pct = run_gate(ohlc, "percentile-rank (use_regime_pct)", pct_cfg)

    print("\n=== E15 A/B summary ===")
    print(f"{'detector':<32} {'gate':>6} {'median_oos':>12} {'fail%':>8}")
    for row in (fixed, pct):
        print(f"{row['label']:<32} "
              f"{'PASS' if row['passed'] else 'FAIL':>6} "
              f"{row['median_oos']:>+12.4f} "
              f"{row['failure_rate']:>7.1%}")
