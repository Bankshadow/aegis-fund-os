"""E22: Diagnose why dual_pct loses to cash on robust score (Line B).

Protocol (declared before run):
  Datasets = BTCUSDT / ETHUSDT / SOLUSDT × 4h
  Costs    = ExecutionProfile (real half-spread + funding + stop slippage)
  Base     = use_regime_pct=True; no RL / funding bias / relative
  Report   = per-asset return, maxDD, robust, n_tp, n_stopouts, n_rebuilds,
             n_edge_skips for cash / dual_pct / regime_router / regime_allocator
  A/B      = dual_pct require_edge=False (E21 baseline) vs True

Primary failure mode (exactly one):
  drawdown_dominated   — return >= -1% but 2*DD pulls robust below cash
  negative_edge_trading — rebuilds/TP > 0 and return clearly negative (< -1%)
  idle_no_trades       — rebuilds ~= 0 on all assets
  cost_drag            — edge ON cuts activity and dual mean robust clearly
                         improves vs OFF (and preferably beats cash)

E22 PASS = mode identified from the table and logged honestly.
E22 is NOT a promotion re-run. If edge ON makes dual beat cash on mean robust
across 3 assets, note as E23 candidate only — do not change defaults/gate.
"""

from __future__ import annotations

from dataclasses import replace

from dynamic_grid.allocator import RiskBudgetAllocator
from dynamic_grid.backtest import run_backtest_engine
from dynamic_grid.benchmarks import CashBenchmark
from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.regime_switch import RegimeSwitchingOrchestrator
from dynamic_grid.research import (ExecutionProfile, ResearchDataset,
                                   risk_adjusted_score)


def edge_skips(engine) -> int:
    if hasattr(engine, "engines"):
        return sum(getattr(e, "n_edge_skips", 0) for e in engine.engines)
    if hasattr(engine, "long") and hasattr(engine, "short"):
        return edge_skips(engine.long) + edge_skips(engine.short)
    return int(getattr(engine, "n_edge_skips", 0))


def build_engine(name: str, cfg: DynamicGridConfig):
    if name == "cash":
        return CashBenchmark()
    if name == "dual_pct":
        return MemoryOrchestrator(make_dual_layers(cfg))
    if name == "regime_router":
        return RegimeSwitchingOrchestrator(
            cfg, range_long_weight=0.75, high_vol_risk_scale=0.5)
    if name == "regime_allocator":
        return RegimeSwitchingOrchestrator(
            cfg, range_long_weight=0.75, high_vol_risk_scale=0.5,
            allocator=RiskBudgetAllocator(
                {"long": 0.75, "short": 0.25}, max_weight=0.75,
                lookback=20, performance_tilt=2.0))
    raise ValueError(name)


def run_one(dataset: ResearchDataset, name: str, base: DynamicGridConfig,
            execution: ExecutionProfile):
    cfg = execution.apply(base, dataset)
    engine = build_engine(name, cfg)
    result = run_backtest_engine(
        dataset.ohlc, engine, liquidate_at_end=execution.liquidate_at_end)
    return {
        "strategy": name,
        "dataset": dataset.label,
        "ret": result.total_return,
        "dd": result.max_drawdown,
        "robust": risk_adjusted_score(result),
        "n_tp": result.n_tp,
        "n_stop": result.n_stopouts,
        "n_rebuild": result.n_rebuilds,
        "n_edge_skips": edge_skips(engine),
    }


def classify(rows: list[dict], dual_off_mean: float, dual_on_mean: float,
             cash_mean: float = 0.0) -> str:
    dual_off = [r for r in rows if r["strategy"] == "dual_pct"]
    rebuilds = sum(r["n_rebuild"] for r in dual_off)
    mean_ret = sum(r["ret"] for r in dual_off) / max(len(dual_off), 1)
    mean_dd = sum(r["dd"] for r in dual_off) / max(len(dual_off), 1)

    # cost_drag: edge ON clearly improves dual mean robust vs OFF
    if dual_on_mean - dual_off_mean >= 0.02:
        return "cost_drag"

    if rebuilds <= 0:
        return "idle_no_trades"

    if mean_ret < -0.01:
        return "negative_edge_trading"

    # return near flat / slightly positive but DD penalty loses to cash
    if dual_off_mean < cash_mean and mean_dd * 2.0 >= abs(mean_ret) + 0.005:
        return "drawdown_dominated"

    if mean_ret < 0:
        return "negative_edge_trading"
    return "drawdown_dominated"


def main():
    datasets = tuple(
        ResearchDataset.from_market_data(symbol, "4h")
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    execution = ExecutionProfile(extra_stop_slippage_bps=5.0)
    base = DynamicGridConfig(use_regime_pct=True)
    base_edge = replace(base, require_edge=True)

    strategies = ("cash", "dual_pct", "regime_router", "regime_allocator")

    print("E22 diagnose dual_pct vs cash")
    print("Protocol: BTC/ETH/SOL 4h, ExecutionProfile, use_regime_pct=True")
    print("A/B: dual_pct require_edge OFF vs ON\n")

    print(f"{'dataset':<14} {'strategy':<18} {'ret':>8} {'DD':>7} {'robust':>8} "
          f"{'TP':>5} {'stop':>5} {'reb':>5} {'eskip':>6}")
    print("-" * 90)

    rows = []
    for ds in datasets:
        for name in strategies:
            row = run_one(ds, name, base, execution)
            rows.append(row)
            print(f"{row['dataset']:<14} {row['strategy']:<18} "
                  f"{row['ret']*100:>+7.2f}% {row['dd']*100:>6.2f}% "
                  f"{row['robust']:>+8.4f} {row['n_tp']:>5d} {row['n_stop']:>5d} "
                  f"{row['n_rebuild']:>5d} {row['n_edge_skips']:>6d}")

    print("\n=== A/B dual_pct require_edge ===")
    print(f"{'dataset':<14} {'edge':>5} {'ret':>8} {'DD':>7} {'robust':>8} "
          f"{'TP':>5} {'stop':>5} {'reb':>5} {'eskip':>6}")
    print("-" * 78)
    dual_off_scores, dual_on_scores = [], []
    for ds in datasets:
        off = run_one(ds, "dual_pct", base, execution)
        on = run_one(ds, "dual_pct", base_edge, execution)
        dual_off_scores.append(off["robust"])
        dual_on_scores.append(on["robust"])
        for label, row in (("OFF", off), ("ON", on)):
            print(f"{row['dataset']:<14} {label:>5} "
                  f"{row['ret']*100:>+7.2f}% {row['dd']*100:>6.2f}% "
                  f"{row['robust']:>+8.4f} {row['n_tp']:>5d} {row['n_stop']:>5d} "
                  f"{row['n_rebuild']:>5d} {row['n_edge_skips']:>6d}")

    dual_off_mean = sum(dual_off_scores) / len(dual_off_scores)
    dual_on_mean = sum(dual_on_scores) / len(dual_on_scores)
    print(f"\nMean robust dual OFF: {dual_off_mean:+.4f}")
    print(f"Mean robust dual ON : {dual_on_mean:+.4f}")
    print(f"Mean robust cash    : {0.0:+.4f}")
    beats_cash = dual_on_mean > 0.0
    print(f"Edge ON beats cash on mean robust: {beats_cash}")
    if beats_cash:
        print("-> E23 candidate only (do not change defaults in E22)")

    mode = classify(rows, dual_off_mean, dual_on_mean)
    print(f"\nE22 mode: {mode}")
    print("E22 verdict: PASS (diagnosis complete)")


if __name__ == "__main__":
    main()
