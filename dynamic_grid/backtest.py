"""Bar-by-bar backtester and performance metrics."""

from dataclasses import dataclass

import numpy as np

from .grid_engine import DynamicGridConfig, DynamicGridEngine, StaticGridEngine


@dataclass
class BacktestResult:
    total_return: float      # fraction of initial equity
    max_drawdown: float      # fraction, peak-to-trough on equity
    mar: float               # total_return / max_drawdown
    cvar_5: float            # Expected Shortfall: mean of worst 5% bar returns
    profit_factor: float     # gross TP profit / gross stop loss (trade-level)
    recovery_factor: float   # net profit / max drawdown (จากยอดเงินจริง)
    n_tp: int
    n_stopouts: int
    n_rebuilds: int
    n_consolidations: int
    final_equity: float
    equity_curve: np.ndarray

    def row(self) -> str:
        return (f"{self.total_return*100:+8.2f}%  "
                f"{self.max_drawdown*100:7.2f}%  "
                f"{self.mar:7.2f}  "
                f"{self.n_tp:5d}  {self.n_stopouts:5d}  "
                f"{self.n_rebuilds:4d}  {self.n_consolidations:4d}")


def run_backtest_engine(ohlc: np.ndarray, engine,
                        initial_equity: float = 10_000.0,
                        liquidate_at_end: bool = False) -> BacktestResult:
    """Drive any pre-built engine-like object (DynamicGridEngine,
    StaticGridEngine, or MultiLayerOrchestrator - anything exposing
    on_bar/unrealized/n_tp/n_stopouts/n_rebuilds/n_consolidations).
    """
    cash_pnl = 0.0
    equity = np.empty(len(ohlc))

    for i, (o, h, l, c) in enumerate(ohlc):
        cash_pnl += engine.on_bar(o, h, l, c, initial_equity + cash_pnl)
        equity[i] = initial_equity + cash_pnl + engine.unrealized(c)

    if liquidate_at_end and len(ohlc) and hasattr(engine, "liquidate"):
        cash_pnl += engine.liquidate(float(ohlc[-1, 3]))
        equity[-1] = initial_equity + cash_pnl

    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / peak
    max_dd = float(dd.max())
    total_return = float(equity[-1] / initial_equity - 1.0)
    mar = total_return / max(max_dd, 0.001)  # floor DD at 0.1% to keep MAR sane

    # -- deep evaluation metrics (v3.1) --
    # CVaR 5% (Expected Shortfall): เมื่อเจอแท่งที่เลวร้ายที่สุด 5% โดยเฉลี่ยเสียเท่าไหร่
    bar_rets = np.diff(equity) / equity[:-1]
    k = max(int(len(bar_rets) * 0.05), 1)
    cvar_5 = float(np.sort(bar_rets)[:k].mean()) if len(bar_rets) else 0.0
    # Profit Factor จากผลจริงรายไม้ (TP vs stop-out) ไม่ใช่จาก equity curve
    gp = getattr(engine, "gross_profit", 0.0)
    gl = getattr(engine, "gross_loss", 0.0)
    profit_factor = gp / gl if gl > 1e-9 else float("inf") if gp > 0 else 0.0
    recovery_factor = (equity[-1] - initial_equity) / max(max_dd * initial_equity, 1e-9)

    return BacktestResult(
        total_return=total_return,
        max_drawdown=max_dd,
        mar=mar,
        cvar_5=cvar_5,
        profit_factor=profit_factor,
        recovery_factor=recovery_factor,
        n_tp=engine.n_tp,
        n_stopouts=engine.n_stopouts,
        n_rebuilds=engine.n_rebuilds,
        n_consolidations=engine.n_consolidations,
        final_equity=float(equity[-1]),
        equity_curve=equity,
    )


def run_backtest(ohlc: np.ndarray, cfg: DynamicGridConfig,
                 engine_cls=DynamicGridEngine,
                 initial_equity: float = 10_000.0,
                 liquidate_at_end: bool = False) -> BacktestResult:
    return run_backtest_engine(ohlc, engine_cls(cfg), initial_equity,
                               liquidate_at_end=liquidate_at_end)


def compare_engines(ohlc: np.ndarray, cfg: DynamicGridConfig):
    """Run the same data through the static baseline and the dynamic grid."""
    static = run_backtest(ohlc, cfg, StaticGridEngine)
    dynamic = run_backtest(ohlc, cfg, DynamicGridEngine)
    return static, dynamic
