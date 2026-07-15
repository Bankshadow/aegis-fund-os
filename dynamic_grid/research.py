"""Multi-strategy research framework for the Dynamic Grid system.

It composes existing deterministic engines into comparable candidates, applies
one explicit execution profile per market, and rejects promotion unless every
cross-asset validation gate passes.  It is a research layer only: it neither
places orders nor introduces an LLM into sizing or execution.
"""

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np

from .allocator import RiskBudgetAllocator
from .backtest import BacktestResult, run_backtest_engine
from .benchmarks import BuyHoldBenchmark, CashBenchmark
from .grid_engine import DynamicGridConfig
from .market_data import market_profile
from .orchestrator import make_dual_layers
from .orchestrator_agent import MemoryOrchestrator
from .regime_switch import RegimeSwitchingOrchestrator
from .validation import ValidationGate, ValidationReport, combinatorial_purged_screen


@dataclass(frozen=True)
class ResearchDataset:
    symbol: str
    timeframe: str
    ohlc: np.ndarray
    half_spread: float = 0.0       # estimated fraction of price
    funding_per_bar: float = 0.0
    median_quote_volume: float = 0.0

    @classmethod
    def from_market_data(cls, symbol: str, timeframe: str) -> "ResearchDataset":
        profile = market_profile(symbol, timeframe)
        return cls(symbol=symbol, timeframe=timeframe, ohlc=profile["ohlc"],
                   half_spread=profile["half_spread"],
                   funding_per_bar=profile["funding_per_bar"],
                   median_quote_volume=profile["median_quote_volume"])

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.timeframe}"


@dataclass(frozen=True)
class ExecutionProfile:
    """Explicit costs shared by every tradable candidate in one comparison."""

    fee_rate: float = 0.0005
    extra_stop_slippage_bps: float = 5.0
    use_estimated_spread: bool = True
    conservative_intrabar: bool = True
    book_entry_fees_immediately: bool = True
    liquidate_at_end: bool = True

    def apply(self, cfg: DynamicGridConfig, dataset: ResearchDataset) -> DynamicGridConfig:
        # The current engine supports adverse stop fills but not a full bid/ask
        # fill model. The estimated half spread is therefore added as a stop
        # stress cost and remains documented as an approximation.
        spread_bps = dataset.half_spread * 10_000 if self.use_estimated_spread else 0.0
        half_spread = dataset.half_spread if self.use_estimated_spread else 0.0
        return replace(
            cfg, fee_rate=self.fee_rate,
            funding_rate_per_bar=dataset.funding_per_bar,
            stop_slippage_bps=max(cfg.stop_slippage_bps,
                                  self.extra_stop_slippage_bps + spread_bps),
            half_spread=half_spread,
            conservative_intrabar=self.conservative_intrabar,
            book_entry_fees_immediately=self.book_entry_fees_immediately,
        )


EngineBuilder = Callable[[DynamicGridConfig], object]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    build_engine: EngineBuilder
    tradable: bool = True
    description: str = ""


@dataclass(frozen=True)
class StrategyResult:
    strategy: str
    dataset: str
    score: float
    total_return: float
    max_drawdown: float
    result: BacktestResult


@dataclass(frozen=True)
class PromotionDecision:
    selected_strategy: str
    eligible_for_paper: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ResearchRun:
    results: tuple[StrategyResult, ...]
    validation_by_dataset: dict[str, ValidationReport]
    leaderboard: tuple[tuple[str, float], ...]
    promotion: PromotionDecision


def risk_adjusted_score(result: BacktestResult) -> float:
    """Project-standard score: drawdown costs twice the return benefit."""
    return result.total_return - 2.0 * result.max_drawdown


def default_strategies(range_long_weight: float = 0.75,
                       high_vol_risk_scale: float = 0.5) -> tuple[StrategySpec, ...]:
    """Candidate set: benchmarks, regime sleeves, and dual+percentile stack."""
    return (
        StrategySpec("cash", lambda cfg: CashBenchmark(), tradable=False,
                     description="No-trade baseline"),
        StrategySpec("buy_hold", lambda cfg: BuyHoldBenchmark(cfg.fee_rate), tradable=False,
                     description="One-times long benchmark with fees"),
        StrategySpec(
            "regime_router",
            lambda cfg: RegimeSwitchingOrchestrator(
                cfg, range_long_weight=range_long_weight,
                high_vol_risk_scale=high_vol_risk_scale),
            description="Persistent regime routes long, short, and range sleeves"),
        StrategySpec(
            "regime_allocator",
            lambda cfg: RegimeSwitchingOrchestrator(
                cfg, range_long_weight=range_long_weight,
                high_vol_risk_scale=high_vol_risk_scale,
                allocator=RiskBudgetAllocator(
                    {"long": range_long_weight,
                     "short": 1.0 - range_long_weight},
                    max_weight=0.75, lookback=20, performance_tilt=2.0)),
            description="Regime router plus capped realized-PnL allocator"),
        StrategySpec(
            "dual_pct",
            lambda cfg: MemoryOrchestrator(make_dual_layers(cfg)),
            description="Dual 75/25 long/short layers with percentile regime (E11+E14)"),
    )


class MultiStrategyResearchFramework:
    """Compare candidates under common costs, then enforce promotion gates."""

    def __init__(self, strategies: tuple[StrategySpec, ...],
                 execution: ExecutionProfile | None = None,
                 gate: ValidationGate | None = None):
        if len(strategies) < 2:
            raise ValueError("research needs at least two strategies")
        names = [strategy.name for strategy in strategies]
        if len(set(names)) != len(names):
            raise ValueError("strategy names must be unique")
        self.strategies = strategies
        self.execution = execution or ExecutionProfile()
        self.gate = gate or ValidationGate()

    def _evaluate(self, strategy: StrategySpec, dataset: ResearchDataset,
                  base_config: DynamicGridConfig, window=None) -> BacktestResult:
        cfg = self.execution.apply(base_config, dataset)
        engine = strategy.build_engine(cfg)
        return run_backtest_engine(dataset.ohlc if window is None else window, engine,
                                   liquidate_at_end=self.execution.liquidate_at_end)

    def run(self, datasets: tuple[ResearchDataset, ...], base_config: DynamicGridConfig,
            *, n_groups: int = 6, n_test_groups: int = 2,
            purge_groups: int = 1) -> ResearchRun:
        if not datasets:
            raise ValueError("at least one dataset is required")
        results, reports = [], {}
        scores_by_strategy = {strategy.name: [] for strategy in self.strategies}
        for dataset in datasets:
            for strategy in self.strategies:
                result = self._evaluate(strategy, dataset, base_config)
                score = risk_adjusted_score(result)
                results.append(StrategyResult(strategy.name, dataset.label, score,
                                              result.total_return, result.max_drawdown, result))
                scores_by_strategy[strategy.name].append(score)

            candidates = {
                strategy.name: (lambda window, strategy=strategy, dataset=dataset:
                                self._evaluate(strategy, dataset, base_config, window))
                for strategy in self.strategies
            }
            reports[dataset.label] = combinatorial_purged_screen(
                dataset.ohlc, candidates, n_groups=n_groups,
                n_test_groups=n_test_groups, purge_groups=purge_groups)

        leaderboard = tuple(sorted(
            ((name, float(np.mean(scores))) for name, scores in scores_by_strategy.items()),
            key=lambda item: item[1], reverse=True))
        selected = leaderboard[0][0]
        spec = next(strategy for strategy in self.strategies if strategy.name == selected)
        reasons = []
        if not spec.tradable:
            reasons.append(f"{selected} is a benchmark, not a tradable strategy")
        failed = [label for label, report in reports.items() if not self.gate.passes(report)]
        if failed:
            reasons.append("validation gate failed: " + ", ".join(failed))
        if not reasons:
            reasons.append("all cross-asset validation gates passed")
        return ResearchRun(
            results=tuple(results), validation_by_dataset=reports,
            leaderboard=leaderboard,
            promotion=PromotionDecision(selected, not failed and spec.tradable, tuple(reasons)),
        )
