"""A/B: fixed long/short allocation versus persistent regime routing.

Criterion is declared before evaluation: robust = return - 2 * max drawdown.
Every variant uses the same conservative execution assumptions.
"""

from dataclasses import replace
from itertools import product

import numpy as np

from bear_short_demo import TRAIN_END, TEST_END, tune
from compare_versions import V1_BEST
from dynamic_grid import (DynamicGridConfig, LayerSpec,
                          MultiLayerOrchestrator, RegimeSwitchingOrchestrator,
                          SCENARIOS, generate_scenario, load_bear_market,
                          load_binance_klines, run_backtest_engine)
from dynamic_grid.grid_engine import DynamicGridEngine
from dynamic_grid.short_engine import ShortGridEngine
from validate_v2 import V2_REGIME


SEEDS = (7, 11, 13)
REALISTIC = dict(
    use_regime_pct=True,
    regime_confirm_bars=3,
    regime_min_dwell_bars=5,
    regime_hysteresis=0.7,
    conservative_intrabar=True,
    stop_slippage_bps=5.0,
    book_entry_fees_immediately=True,
)


def robust(result):
    return result.total_return - 2.0 * result.max_drawdown


def fixed_dual(long_cfg, short_cfg):
    return MultiLayerOrchestrator([
        LayerSpec("long", 0.75, long_cfg),
        LayerSpec("short", 0.25, short_cfg, engine_cls=ShortGridEngine),
    ])


def engines(long_cfg, short_cfg, router_params=None):
    router_params = router_params or {}
    return {
        "long-only": lambda: DynamicGridEngine(long_cfg),
        "fixed-75/25": lambda: fixed_dual(long_cfg, short_cfg),
        "regime-switch": lambda: RegimeSwitchingOrchestrator(
            long_cfg, short_cfg,
            range_long_weight=router_params.get("range_long_weight", 0.5),
            high_vol_risk_scale=router_params.get("high_vol_risk_scale", 0.25)),
    }


def run(data, factory):
    return run_backtest_engine(data, factory(), liquidate_at_end=True)


def tune_router(base_cfg):
    """Small declared grid search on synthetic seeds 1/2 only."""
    datasets = [generate_scenario(s, n_bars=2000, seed=seed)
                for s in SCENARIOS for seed in (1, 2)]
    best = (-1e18, None, None)
    for range_w, hv_scale, confirm, dwell, hysteresis in product(
            (0.5, 0.75, 1.0), (0.0, 0.25, 0.5), (2, 3, 5),
            (3, 5, 10), (0.6, 0.75)):
        cfg = replace(base_cfg, regime_confirm_bars=confirm,
                      regime_min_dwell_bars=dwell,
                      regime_hysteresis=hysteresis)
        params = {"range_long_weight": range_w,
                  "high_vol_risk_scale": hv_scale}
        scores = [robust(run_backtest_engine(
            data, RegimeSwitchingOrchestrator(
                cfg, cfg, range_long_weight=range_w,
                high_vol_risk_scale=hv_scale), liquidate_at_end=True))
            for data in datasets]
        score = float(np.mean(scores) - 0.5 * np.std(scores))
        if score > best[0]:
            best = (score, params, cfg)
    return best


def main():
    common = DynamicGridConfig(**V1_BEST, **V2_REGIME, **REALISTIC)
    train_score, router_params, tuned_common = tune_router(common)
    print("Router selected on synthetic seeds 1/2 only:", router_params,
          f"confirm={tuned_common.regime_confirm_bars}",
          f"dwell={tuned_common.regime_min_dwell_bars}",
          f"hysteresis={tuned_common.regime_hysteresis}",
          f"train robust={train_score:+.4f}")
    variants = engines(tuned_common, tuned_common, router_params)
    print("=== Synthetic held-out, mean robust score ===")
    totals = {name: [] for name in variants}
    print(f"{'scenario':<16}" + "".join(f"{name:>18}" for name in variants))
    for scenario in SCENARIOS:
        row = f"{scenario:<16}"
        for name, factory in variants.items():
            scores = [robust(run(generate_scenario(
                scenario, n_bars=2000, seed=seed), factory))
                for seed in SEEDS]
            score = float(np.mean(scores))
            totals[name].append(score)
            row += f"{score:>+18.4f}"
        print(row)
    print(f"{'MEAN':<16}" + "".join(
        f"{np.mean(totals[name]):>+18.4f}" for name in variants))

    all_bear = load_bear_market()
    train = all_bear[:TRAIN_END]
    router_regime = dict(
        regime_confirm_bars=tuned_common.regime_confirm_bars,
        regime_min_dwell_bars=tuned_common.regime_min_dwell_bars,
        regime_hysteresis=tuned_common.regime_hysteresis)
    real_overrides = {**REALISTIC, **router_regime}
    long_cfg = replace(DynamicGridConfig(**tune(
        train, DynamicGridEngine, 0)), **real_overrides)
    short_cfg = replace(DynamicGridConfig(**tune(
        train, ShortGridEngine, 0)), **real_overrides)
    real_variants = engines(long_cfg, short_cfg, router_params)
    for label, data in (
        ("Real bear 2022", all_bear[TRAIN_END:TEST_END]),
        ("Real bull 2023-2026", load_binance_klines()),
    ):
        print(f"\n=== {label}; parameters selected on 2021 only ===")
        for name, factory in real_variants.items():
            r = run(data, factory)
            print(f"{name:<18} ret {r.total_return*100:+7.2f}%  "
                  f"DD {r.max_drawdown*100:6.2f}%  robust {robust(r):+.4f}")


if __name__ == "__main__":
    main()
