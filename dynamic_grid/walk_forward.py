"""Walk-forward validation on real (non-synthetic) OHLC data.

Rolling-window protocol (standard walk-forward, no lookahead):

    [------- train (in-sample) -------][-- test (out-of-sample) --]
              window optimized here      never seen during optimization
                                        [------- train ---------][-- test --]
                                              (rolled forward by step_bars)

For each fold: random-search-optimize DynamicGridConfig on the train slice
only, then run the resulting config ONCE on the immediately-following test
slice. Aggregate out-of-sample results across all folds - this is the
number that matters, not the in-sample fit.
"""

from dataclasses import dataclass

import numpy as np

from .grid_engine import DynamicGridConfig, StaticGridEngine
from .backtest import run_backtest
from .optimize import SPACE, _sample


@dataclass
class FoldResult:
    fold: int
    train_start: int
    test_start: int
    test_end: int
    params: dict
    dynamic_return: float
    dynamic_maxdd: float
    dynamic_cvar5: float
    static_return: float
    static_maxdd: float


def _make_subwindows(ohlc_train: np.ndarray, n_subwindows: int,
                     subwindow_frac: float) -> list[np.ndarray]:
    """Slice train into several overlapping sub-windows spread across it.

    Fix for the v3.2 overfitting-to-regime finding: scoring against the
    WHOLE train slice as one blob let the optimizer fit to whatever single
    regime dominated that slice (e.g. fold 0's +142% bull run), producing a
    config that fell apart the moment the very next test window saw a
    different regime (a mild pullback). Sub-windows sample the early part,
    middle, and late part of train separately, so a config that only works
    in one regime scores poorly on the others - the same trick the
    synthetic optimizer uses across its 6 scenarios, applied within a
    single real series.
    """
    sub_len = max(int(len(ohlc_train) * subwindow_frac), 30)
    if sub_len >= len(ohlc_train):
        return [ohlc_train]
    starts = np.linspace(0, len(ohlc_train) - sub_len, n_subwindows).astype(int)
    return [ohlc_train[s:s + sub_len] for s in starts]


def _optimize_on_window(ohlc_train: np.ndarray, n_iter: int, seed: int,
                        n_subwindows: int = 4,
                        subwindow_frac: float = 0.5) -> dict:
    """Random search scored across several sub-windows of train (robust to
    regime, not just fit to train's dominant regime - see _make_subwindows).

    Score per sub-window: return - 2*maxDD (system's standard risk weight).
    Combined score: mean(sub-window scores) - 0.5*std(sub-window scores) -
    the same "punish inconsistency across conditions" formula the synthetic
    optimizer uses, just applied across time-slices of one real series
    instead of across synthetic scenarios.
    """
    subwindows = _make_subwindows(ohlc_train, n_subwindows, subwindow_frac)
    rng = np.random.default_rng(seed)
    best_score, best_params = -1e18, None
    for _ in range(n_iter):
        params = _sample(rng)
        cfg = DynamicGridConfig(**params)
        sub_scores = []
        for sw in subwindows:
            r = run_backtest(sw, cfg)
            sub_scores.append(r.total_return - 2.0 * r.max_drawdown)
        score = float(np.mean(sub_scores) - 0.5 * np.std(sub_scores))
        if score > best_score:
            best_score, best_params = score, params
    return best_params


def walk_forward(ohlc: np.ndarray, train_bars: int = 250, test_bars: int = 60,
                 step_bars: int = 60, n_iter: int = 60, seed: int = 0,
                 n_subwindows: int = 4, subwindow_frac: float = 0.5) -> list[FoldResult]:
    """Run the rolling train/optimize -> test/evaluate protocol end to end.

    Pass n_subwindows=1 to reproduce the pre-fix behaviour (optimize against
    the whole train slice as one blob) for A/B comparison.
    """
    results = []
    fold = 0
    start = 0
    while start + train_bars + test_bars <= len(ohlc):
        train = ohlc[start:start + train_bars]
        test = ohlc[start + train_bars: start + train_bars + test_bars]

        params = _optimize_on_window(train, n_iter, seed=seed + fold,
                                     n_subwindows=n_subwindows,
                                     subwindow_frac=subwindow_frac)
        cfg = DynamicGridConfig(**params)

        r_dyn = run_backtest(test, cfg)
        r_stat = run_backtest(test, cfg, StaticGridEngine)

        results.append(FoldResult(
            fold=fold,
            train_start=start,
            test_start=start + train_bars,
            test_end=start + train_bars + test_bars,
            params=params,
            dynamic_return=r_dyn.total_return,
            dynamic_maxdd=r_dyn.max_drawdown,
            dynamic_cvar5=r_dyn.cvar_5,
            static_return=r_stat.total_return,
            static_maxdd=r_stat.max_drawdown,
        ))
        fold += 1
        start += step_bars
    return results
