"""E23: Tune dual_pct geometry under real Line-B ExecutionProfile costs.

Hypothesis (from E22): Line B ran untuned dataclass defaults under full costs;
require_edge cannot fix runtime expectancy. Per-asset dual-stack tuning should
recover edge on held-out 4h data.

Protocol (declared before run):
  Datasets = BTCUSDT / ETHUSDT / SOLUSDT × 4h
  Split    = 60% train / 40% test (time-ordered)
  Costs    = ExecutionProfile(extra_stop_slippage_bps=5.0) — do NOT bake spread
  Engine   = MemoryOrchestrator(make_dual_layers(cfg)); shared base (no short_cfg)
  Search   = optimize._sample(), 60 iters, seeds 0/1/2
  Score    = return - 2*maxDD; use_regime_pct=True; no RL/funding/relative

Pass (all required):
  1. Mean robust of tuned dual on TEST across 3 assets (avg over 3 seeds) > 0
  2. That mean >= untuned mean robust on same TEST windows + 0.03
  3. Every asset engaged: mean n_rebuilds > 0 and mean n_tp > 0 on test
  4. Promotion with seed-0 params per asset: eligible_for_paper and
     selected_strategy == "dual_pct" under unchanged ValidationGate;
     cash stays on the leaderboard

Fail any criterion -> record FAIL honestly. Do not change production defaults.
"""

from __future__ import annotations

import numpy as np

from dynamic_grid.allocator import RiskBudgetAllocator
from dynamic_grid.backtest import run_backtest_engine
from dynamic_grid.benchmarks import BuyHoldBenchmark, CashBenchmark
from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.optimize import _sample
from dynamic_grid.orchestrator import make_dual_layers
from dynamic_grid.orchestrator_agent import MemoryOrchestrator
from dynamic_grid.regime_switch import RegimeSwitchingOrchestrator
from dynamic_grid.research import (ExecutionProfile, ResearchDataset,
                                   risk_adjusted_score)
from dynamic_grid.validation import ValidationGate, combinatorial_purged_screen

N_ITER = 60
SEEDS = (0, 1, 2)
TRAIN_FRAC = 0.60
IMPROVE_MIN = 0.03


def dual_cfg(params: dict, dataset: ResearchDataset,
             execution: ExecutionProfile) -> DynamicGridConfig:
    base = DynamicGridConfig(use_regime_pct=True, **params)
    return execution.apply(base, dataset)


def run_dual(ohlc, cfg: DynamicGridConfig, liquidate: bool = True):
    engine = MemoryOrchestrator(make_dual_layers(cfg))
    result = run_backtest_engine(ohlc, engine, liquidate_at_end=liquidate)
    return result, engine


def tune_dual(train, dataset: ResearchDataset, execution: ExecutionProfile,
              seed: int, n_iter: int = N_ITER) -> tuple[dict, float]:
    rng = np.random.default_rng(seed)
    best_s, best_p = -9e9, None
    for it in range(n_iter):
        params = _sample(rng)
        cfg = dual_cfg(params, dataset, execution)
        result, _ = run_dual(train, cfg)
        score = risk_adjusted_score(result)
        if score > best_s:
            best_s, best_p = score, params
        if (it + 1) % 20 == 0:
            print(f"    seed={seed} iter {it+1}/{n_iter} best_train={best_s:+.4f}")
    return best_p, best_s


def eval_row(label: str, variant: str, result, seed: int | None = None) -> dict:
    return {
        "dataset": label,
        "variant": variant,
        "seed": seed,
        "ret": result.total_return,
        "dd": result.max_drawdown,
        "robust": risk_adjusted_score(result),
        "n_tp": result.n_tp,
        "n_rebuild": result.n_rebuilds,
    }


def run_promotion(datasets: tuple[ResearchDataset, ...],
                  seed0_params: dict[str, dict],
                  execution: ExecutionProfile) -> tuple:
    """E21-style gate with dual_pct using per-asset seed-0 tuned params."""
    gate = ValidationGate()
    default_base = DynamicGridConfig(use_regime_pct=True)
    scores_by_strategy = {
        "cash": [], "buy_hold": [], "regime_router": [],
        "regime_allocator": [], "dual_pct": [],
    }
    reports = {}

    def build(name: str, cfg: DynamicGridConfig):
        if name == "cash":
            return CashBenchmark()
        if name == "buy_hold":
            return BuyHoldBenchmark(cfg.fee_rate)
        if name == "regime_router":
            return RegimeSwitchingOrchestrator(
                cfg, range_long_weight=0.75, high_vol_risk_scale=0.5)
        if name == "regime_allocator":
            return RegimeSwitchingOrchestrator(
                cfg, range_long_weight=0.75, high_vol_risk_scale=0.5,
                allocator=RiskBudgetAllocator(
                    {"long": 0.75, "short": 0.25}, max_weight=0.75,
                    lookback=20, performance_tilt=2.0))
        if name == "dual_pct":
            return MemoryOrchestrator(make_dual_layers(cfg))
        raise ValueError(name)

    for dataset in datasets:
        default_cfg = execution.apply(default_base, dataset)
        dual_base = DynamicGridConfig(
            use_regime_pct=True, **seed0_params[dataset.label])
        dual_applied = execution.apply(dual_base, dataset)

        def cfg_for(name: str, dual=dual_applied, default=default_cfg):
            return dual if name == "dual_pct" else default

        for name in scores_by_strategy:
            eng = build(name, cfg_for(name))
            result = run_backtest_engine(
                dataset.ohlc, eng, liquidate_at_end=execution.liquidate_at_end)
            scores_by_strategy[name].append(risk_adjusted_score(result))

        candidates = {}
        for name in scores_by_strategy:
            def make_eval(name=name, cfg_for=cfg_for):
                def evaluate(window):
                    eng = build(name, cfg_for(name))
                    return run_backtest_engine(
                        window, eng, liquidate_at_end=execution.liquidate_at_end)
                return evaluate
            candidates[name] = make_eval()

        reports[dataset.label] = combinatorial_purged_screen(
            dataset.ohlc, candidates, n_groups=6, n_test_groups=2, purge_groups=1)

    leaderboard = sorted(
        ((n, float(np.mean(s))) for n, s in scores_by_strategy.items()),
        key=lambda x: x[1], reverse=True)
    selected = leaderboard[0][0]
    tradable = selected not in {"cash", "buy_hold"}
    failed = [lab for lab, rep in reports.items() if not gate.passes(rep)]
    eligible = tradable and not failed
    return leaderboard, reports, selected, eligible, failed


def main():
    datasets = tuple(
        ResearchDataset.from_market_data(symbol, "4h")
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    execution = ExecutionProfile(extra_stop_slippage_bps=5.0)

    print("E23 tune dual_pct under ExecutionProfile")
    print(f"split={TRAIN_FRAC:.0%} train / {1-TRAIN_FRAC:.0%} test; "
          f"iters={N_ITER}; seeds={SEEDS}")
    print("Pass: mean_robust>0; improve>=+0.03 vs untuned; engaged; "
          "promo dual_pct eligible\n")

    tuned_rows = []
    untuned_by_asset = {}
    seed0_params: dict[str, dict] = {}
    asset_seed_robust: dict[str, list[float]] = {}
    asset_engaged: dict[str, list[tuple[int, int]]] = {}

    for dataset in datasets:
        cut = int(len(dataset.ohlc) * TRAIN_FRAC)
        train, test = dataset.ohlc[:cut], dataset.ohlc[cut:]
        print(f"=== {dataset.label} bars={len(dataset.ohlc)} "
              f"train={len(train)} test={len(test)} ===")

        untuned_cfg = execution.apply(
            DynamicGridConfig(use_regime_pct=True), dataset)
        u_res, _ = run_dual(test, untuned_cfg)
        untuned_by_asset[dataset.label] = eval_row(
            dataset.label, "untuned", u_res)
        print(f"  untuned test robust={untuned_by_asset[dataset.label]['robust']:+.4f} "
              f"ret={u_res.total_return*100:+.2f}% DD={u_res.max_drawdown*100:.2f}% "
              f"TP={u_res.n_tp} reb={u_res.n_rebuilds}")

        asset_seed_robust[dataset.label] = []
        asset_engaged[dataset.label] = []
        for seed in SEEDS:
            print(f"  tuning seed={seed}...")
            params, train_s = tune_dual(train, dataset, execution, seed)
            if seed == 0:
                seed0_params[dataset.label] = params
            cfg = dual_cfg(params, dataset, execution)
            t_res, _ = run_dual(test, cfg)
            row = eval_row(dataset.label, "tuned", t_res, seed=seed)
            tuned_rows.append(row)
            asset_seed_robust[dataset.label].append(row["robust"])
            asset_engaged[dataset.label].append((row["n_rebuild"], row["n_tp"]))
            print(f"  seed={seed} train={train_s:+.4f} test robust={row['robust']:+.4f} "
                  f"ret={row['ret']*100:+.2f}% DD={row['dd']*100:.2f}% "
                  f"TP={row['n_tp']} reb={row['n_rebuild']}")

    print("\n=== Per-asset mean (3 seeds) ===")
    print(f"{'dataset':<14} {'untuned':>9} {'tuned':>9} {'delta':>9} "
          f"{'reb':>6} {'TP':>6}")
    asset_means = []
    untuned_means = []
    all_engaged = True
    for dataset in datasets:
        label = dataset.label
        t_mean = float(np.mean(asset_seed_robust[label]))
        u_mean = untuned_by_asset[label]["robust"]
        reb_mean = float(np.mean([r for r, _ in asset_engaged[label]]))
        tp_mean = float(np.mean([t for _, t in asset_engaged[label]]))
        engaged = reb_mean > 0 and tp_mean > 0
        all_engaged = all_engaged and engaged
        asset_means.append(t_mean)
        untuned_means.append(u_mean)
        print(f"{label:<14} {u_mean:>+9.4f} {t_mean:>+9.4f} "
              f"{t_mean - u_mean:>+9.4f} {reb_mean:>6.1f} {tp_mean:>6.1f} "
              f"{'OK' if engaged else 'IDLE'}")

    cross_tuned = float(np.mean(asset_means))
    cross_untuned = float(np.mean(untuned_means))
    c1 = cross_tuned > 0.0
    c2 = cross_tuned >= cross_untuned + IMPROVE_MIN
    c3 = all_engaged
    print(f"\nCross-asset mean robust tuned={cross_tuned:+.4f} "
          f"untuned={cross_untuned:+.4f} delta={cross_tuned-cross_untuned:+.4f}")
    print(f"C1 mean>0: {'PASS' if c1 else 'FAIL'}")
    print(f"C2 improve>=+{IMPROVE_MIN}: {'PASS' if c2 else 'FAIL'}")
    print(f"C3 engaged all: {'PASS' if c3 else 'FAIL'}")

    primary = c1 and c2 and c3
    print(f"\nPrimary (C1-C3): {'PASS' if primary else 'FAIL'}")

    # Criterion 4: always attempt promotion with seed-0 params (declared)
    print("\n=== Promotion (seed-0 tuned dual_pct) ===")
    leaderboard, reports, selected, eligible, failed = run_promotion(
        datasets, seed0_params, execution)
    for name, score in leaderboard:
        print(f"  {name:18s} {score:+.4f}")
    for label, report in reports.items():
        ok = ValidationGate().passes(report)
        print(f"  gate {label:12s} median={report.median_test_score:+.4f} "
              f"fail={report.selection_failure_rate:.1%} "
              f"{'PASS' if ok else 'FAIL'}")
    print(f"Selected: {selected}")
    print(f"Paper eligible: {eligible}")
    if failed:
        print(f"Failed gates: {', '.join(failed)}")
    c4 = eligible and selected == "dual_pct"
    print(f"C4 promotion dual_pct: {'PASS' if c4 else 'FAIL'}")

    e23_pass = primary and c4
    print(f"\nE23 verdict: {'PASS' if e23_pass else 'FAIL'}")
    if primary and not c4:
        print("Note: held-out improved but promotion gate did not select dual_pct")


if __name__ == "__main__":
    main()
