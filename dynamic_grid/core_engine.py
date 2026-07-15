"""Promotion-gated core trading engine.

The core is intentionally small: research decides whether a strategy has earned
permission; deterministic regime/risk/execution code then decides every trade.
If research is absent, inconclusive, or selects a benchmark, the engine stays
in cash. This makes the safe state the default state.
"""

from dataclasses import dataclass, replace

from .allocator import RiskBudgetAllocator
from .benchmarks import CashBenchmark
from .grid_engine import DynamicGridConfig
from .orchestrator import make_dual_layers
from .orchestrator_agent import MemoryOrchestrator
from .regime_switch import RegimeSwitchingOrchestrator
from .research import ExecutionProfile, PromotionDecision, ResearchDataset


@dataclass(frozen=True)
class CoreStatus:
    mode: str                    # "cash" or "active"
    selected_strategy: str
    reason: str
    execution_realism_enabled: bool


class CoreTradingEngine:
    """One backtest/paper-compatible engine with a fail-closed promotion gate.

    Allowed strategies are intentionally narrow. Adding a strategy requires
    adding it to the research candidate set, passing validation, and then
    explicitly adding a deterministic builder here.
    """

    _ALLOWED = {"regime_router", "regime_allocator", "dual_pct"}

    def __init__(self, base_config: DynamicGridConfig,
                 promotion: PromotionDecision | None = None,
                 *, dataset: ResearchDataset | None = None,
                 execution: ExecutionProfile | None = None,
                 range_long_weight: float = 0.75,
                 high_vol_risk_scale: float = 0.5):
        self.promotion = promotion or PromotionDecision(
            selected_strategy="none", eligible_for_paper=False,
            reasons=("no validated research decision",))
        self.execution = execution or ExecutionProfile()
        self.dataset = dataset
        # Default Line-B router to E14 percentile-rank (scale-invariant).
        self.config = replace(base_config, use_regime_pct=True)
        if dataset is not None:
            self.config = self.execution.apply(self.config, dataset)

        approved = (self.promotion.eligible_for_paper
                    and self.promotion.selected_strategy in self._ALLOWED)
        self.active = bool(approved)
        self.strategy_name = self.promotion.selected_strategy if approved else "cash"
        if not approved:
            self.engine = CashBenchmark()
            reason = "; ".join(self.promotion.reasons)
            if self.promotion.selected_strategy not in {"none", "cash"}:
                reason = f"unapproved strategy '{self.promotion.selected_strategy}'; {reason}"
            self.status = CoreStatus("cash", self.strategy_name, reason, False)
            return

        if self.strategy_name == "dual_pct":
            self.engine = MemoryOrchestrator(make_dual_layers(self.config))
        else:
            allocator = None
            if self.strategy_name == "regime_allocator":
                allocator = RiskBudgetAllocator(
                    {"long": range_long_weight, "short": 1.0 - range_long_weight},
                    max_weight=0.75, lookback=20, performance_tilt=2.0)
            self.engine = RegimeSwitchingOrchestrator(
                self.config, range_long_weight=range_long_weight,
                high_vol_risk_scale=high_vol_risk_scale, allocator=allocator)
        self.status = CoreStatus(
            "active", self.strategy_name,
            "; ".join(self.promotion.reasons), True)

    def on_bar(self, o, h, l, c, equity):
        return self.engine.on_bar(o, h, l, c, equity)

    def unrealized(self, price):
        return self.engine.unrealized(price)

    def liquidate(self, price):
        return self.engine.liquidate(price)

    def exposure(self, price):
        return self.engine.exposure(price) if hasattr(self.engine, "exposure") else 0.0

    @property
    def n_tp(self): return self.engine.n_tp
    @property
    def n_stopouts(self): return self.engine.n_stopouts
    @property
    def n_rebuilds(self): return self.engine.n_rebuilds
    @property
    def n_consolidations(self): return self.engine.n_consolidations
    @property
    def gross_profit(self): return self.engine.gross_profit
    @property
    def gross_loss(self): return self.engine.gross_loss
