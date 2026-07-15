"""E25: Conservative-geometry dual tune under Line-B costs (shared base).

Hypothesis (from E22 negative_edge_trading + E23/E24 still < 0): cut trade
frequency and DD via a constrained search space — wider ATR spacing, longer
cooldown, smaller risk_per_zone, fewer levels — without lowering ValidationGate
and without separate short_cfg (E24 did not help).

Protocol (declared before run):
  Datasets = BTCUSDT / ETHUSDT / SOLUSDT × 4h
  Split    = 60% train / 40% test
  Costs    = ExecutionProfile(extra_stop_slippage_bps=5.0)
  Engine   = MemoryOrchestrator(make_dual_layers(cfg)); shared base
  Search   = _sample_conservative(), 60 iters, seeds 0/1/2
  Score    = return - 2*maxDD; use_regime_pct=True; no RL/funding/relative
  Untuned  = dataclass defaults (same E23 baseline)

Conservative SPACE (declared; not cherry-picked after seeing scores):
  levels 3-6; atr_mult 1.5-3.0; risk_per_zone 0.02-0.04; cooldown 40-80;
  stop_mult 0.8-2.0; tp_mult 1.0-2.5; other keys same as optimize.SPACE

Pass (all required) — identical to E23/E24:
  1. Mean robust test across 3 assets (3 seeds) > 0
  2. Mean >= untuned + 0.03
  3. Engaged all assets
  4. Promotion seed-0 -> eligible and selected dual_pct

Fail -> log FAIL. Do not change production defaults or gate.
"""

from __future__ import annotations

import numpy as np

from dynamic_grid.allocator import RiskBudgetAllocator
from dynamic_grid.backtest import run_backtest_engine
from dynamic_grid.benchmarks import BuyHoldBenchmark, CashBenchmark
from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.optimize import SPACE
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

# Constrained subspace — declared before run
CONSERVATIVE = {
    **SPACE,
    "levels": (3, 6, True),
    "atr_mult": (1.5, 3.0, False),
    "risk_per_zone": (0.02, 0.04, False),
    "cooldown_bars": (40, 80, True),
    "stop_mult": (0.8, 2.0, False),
    "tp_mult": (1.0, 2.5, False),
}


def _sample_conservative(rng) -> dict:
    params = {}
    for k, (lo, hi, is_int) in CONSERVATIVE.items():
        v = rng.uniform(lo, hi)
        params[k] = int(round(v)) if is_int else round(v, 3)
    return params


def dual_cfg(params: dict, dataset: ResearchDataset,
             execution: ExecutionProfile) -> DynamicGridConfig:
    return execution.apply(DynamicGridConfig(use_regime_pct=True, **params), dataset)


def run_dual(ohlc, cfg: DynamicGridConfig, liquidate: bool = True):
    engine = MemoryOrchestrator(make_dual_layers(cfg))
    return run_backtest_engine(ohlc, engine, liquidate_at_end=liquidate), engine


def tune(train, dataset, execution, seed, n_iter=N_ITER):
    rng = np.random.default_rng(seed)
    best_s, best_p = -9e9, None
    for it in range(n_iter):
        params = _sample_conservative(rng)
        result, _ = run_dual(train, dual_cfg(params, dataset, execution))
        score = risk_adjusted_score(result)
        if score > best_s:
            best_s, best_p = score, params
        if (it + 1) % 20 == 0:
            print(f"    seed={seed} iter {it+1}/{n_iter} best_train={best_s:+.4f}")
    return best_p, best_s


def run_promotion(datasets, seed0_params, execution):
    gate = ValidationGate()
    default_base = DynamicGridConfig(use_regime_pct=True)
    scores_by_strategy = {
        "cash": [], "buy_hold": [], "regime_router": [],
        "regime_allocator": [], "dual_pct": [],
    }
    reports = {}

    def build(name, cfg):
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
        dual_applied = dual_cfg(seed0_params[dataset.label], dataset, execution)

        for name in scores_by_strategy:
            cfg = dual_applied if name == "dual_pct" else default_cfg
            eng = build(name, cfg)
            result = run_backtest_engine(
                dataset.ohlc, eng, liquidate_at_end=execution.liquidate_at_end)
            scores_by_strategy[name].append(risk_adjusted_score(result))

        candidates = {}
        for name in scores_by_strategy:
            def make_eval(name=name, dual=dual_applied, default=default_cfg):
                def evaluate(window):
                    cfg = dual if name == "dual_pct" else default
                    return run_backtest_engine(
                        window, build(name, cfg),
                        liquidate_at_end=execution.liquidate_at_end)
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

    print("E25 conservative-geometry dual_pct under ExecutionProfile")
    print(f"split={TRAIN_FRAC:.0%} train / {1-TRAIN_FRAC:.0%} test; "
          f"iters={N_ITER}; seeds={SEEDS}")
    print("SPACE: levels 3-6, atr_mult 1.5-3, risk 0.02-0.04, cooldown 40-80\n")

    untuned_by_asset = {}
    seed0_params = {}
    asset_seed_robust = {}
    asset_engaged = {}

    for dataset in datasets:
        cut = int(len(dataset.ohlc) * TRAIN_FRAC)
        train, test = dataset.ohlc[:cut], dataset.ohlc[cut:]
        print(f"=== {dataset.label} bars={len(dataset.ohlc)} "
              f"train={len(train)} test={len(test)} ===")

        untuned_cfg = execution.apply(
            DynamicGridConfig(use_regime_pct=True), dataset)
        u_res, _ = run_dual(test, untuned_cfg)
        u_robust = risk_adjusted_score(u_res)
        untuned_by_asset[dataset.label] = u_robust
        print(f"  untuned test robust={u_robust:+.4f} "
              f"ret={u_res.total_return*100:+.2f}% DD={u_res.max_drawdown*100:.2f}% "
              f"TP={u_res.n_tp} reb={u_res.n_rebuilds}")

        asset_seed_robust[dataset.label] = []
        asset_engaged[dataset.label] = []
        for seed in SEEDS:
            print(f"  tuning seed={seed}...")
            params, train_s = tune(train, dataset, execution, seed)
            if seed == 0:
                seed0_params[dataset.label] = params
            t_res, _ = run_dual(test, dual_cfg(params, dataset, execution))
            robust = risk_adjusted_score(t_res)
            asset_seed_robust[dataset.label].append(robust)
            asset_engaged[dataset.label].append((t_res.n_rebuilds, t_res.n_tp))
            print(f"  seed={seed} train={train_s:+.4f} test robust={robust:+.4f} "
                  f"ret={t_res.total_return*100:+.2f}% DD={t_res.max_drawdown*100:.2f}% "
                  f"TP={t_res.n_tp} reb={t_res.n_rebuilds}")

    print("\n=== Per-asset mean (3 seeds) ===")
    print(f"{'dataset':<14} {'untuned':>9} {'tuned':>9} {'delta':>9} "
          f"{'reb':>6} {'TP':>6}")
    asset_means, untuned_means = [], []
    all_engaged = True
    for dataset in datasets:
        label = dataset.label
        t_mean = float(np.mean(asset_seed_robust[label]))
        u_mean = untuned_by_asset[label]
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

    print("\n=== Promotion (seed-0 conservative dual_pct) ===")
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
    print(f"\nE25 verdict: {'PASS' if primary and c4 else 'FAIL'}")


if __name__ == "__main__":
    main()
