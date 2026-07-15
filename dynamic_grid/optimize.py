"""Multi-scenario random-search optimizer.

Fine-tunes zone/order-distance/risk parameters across ALL synthetic
scenarios at once, scoring robustness (mean performance minus a
dispersion penalty) rather than best-case performance - a parameter set
must survive sideways, trend, crash and regime-switch markets together.
"""

import numpy as np

from .grid_engine import DynamicGridConfig
from .backtest import run_backtest
from .synthetic import generate_scenario, SCENARIOS

# search space: (low, high, is_int)
SPACE = {
    "levels":         (3, 10, True),
    "atr_mult":       (0.8, 3.0, False),
    "risk_per_zone":  (0.02, 0.08, False),
    "stop_mult":      (0.5, 2.0, False),
    "shift_trigger":  (0.5, 3.0, False),
    "anomaly_z":      (2.0, 4.5, False),
    "consolidation_scale": (0.8, 1.5, False),
    "cooldown_bars":  (0, 80, True),
    "tp_mult":        (0.8, 2.5, False),
    "trend_k":        (0.0, 6.0, False),
    # regime adaptation (v2)
    "regime_m_threshold": (0.2, 1.0, False),
    "regime_vol_hi":      (1.1, 1.8, False),
    "hv_risk_scale":      (0.3, 1.0, False),
    "hv_spacing_scale":   (1.0, 2.0, False),
    "up_risk_scale":      (0.8, 1.6, False),
}


def _sample(rng) -> dict:
    params = {}
    for k, (lo, hi, is_int) in SPACE.items():
        v = rng.uniform(lo, hi)
        params[k] = int(round(v)) if is_int else round(v, 3)
    return params


def _score(results) -> float:
    """Robust score: reward return, punish drawdown and inconsistency."""
    rets = np.array([r.total_return for r in results])
    dds = np.array([r.max_drawdown for r in results])
    per_run = rets - 2.0 * dds          # DD hurts twice as much as return helps
    return float(per_run.mean() - 0.5 * per_run.std())


def optimize(n_iter: int = 80, n_bars: int = 2000, seeds=(1, 2),
             scenarios=SCENARIOS, verbose: bool = True):
    """Random search; returns list of (score, params, results) best-first."""
    rng = np.random.default_rng(42)

    # pre-generate all datasets once
    datasets = [generate_scenario(s, n_bars=n_bars, seed=sd)
                for s in scenarios for sd in seeds]

    leaderboard = []
    for it in range(n_iter):
        params = _sample(rng)
        cfg = DynamicGridConfig(**params)
        results = [run_backtest(d, cfg) for d in datasets]
        score = _score(results)
        leaderboard.append((score, params, results))
        if verbose and (it + 1) % 20 == 0:
            best = max(leaderboard, key=lambda x: x[0])
            print(f"  iter {it+1:3d}/{n_iter}  best score so far: {best[0]:+.4f}")

    leaderboard.sort(key=lambda x: -x[0])
    return leaderboard
