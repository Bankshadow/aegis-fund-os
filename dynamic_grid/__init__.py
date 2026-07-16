"""Dynamic Grid Trading system.

Modules:
    synthetic   - synthetic OHLC scenario generators
    indicators  - ATR / volatility / anomaly helpers
    risk        - risk-per-zone position sizing
    grid_engine - adaptive grid construction & lifecycle
    backtest    - bar-by-bar simulator + metrics
    optimize    - multi-scenario random-search optimizer
"""

from .synthetic import generate_scenario, SCENARIOS
from .grid_engine import (DynamicGridConfig, DynamicGridEngine, StaticGridEngine,
                          has_positive_edge, round_trip_cost_frac)
from .orchestrator import LayerSpec, MultiLayerOrchestrator, make_layers
from .backtest import run_backtest, run_backtest_engine, BacktestResult
from .optimize import optimize
from .real_data import load_binance_klines
from .walk_forward import walk_forward, FoldResult
from .event_log import DecisionLog, DecisionEvent
from .orchestrator_agent import MemoryOrchestrator
from .short_engine import ShortGridEngine
from .real_data import load_bear_market
from .rl_agent import RLGovernor, train_q, train_q_on_ohlc
from .regime_switch import RegimeSwitchingOrchestrator
from .signals import (StrategySignal, RegimeSignalModel, FundingBiasModel,
                      RelativeStrengthModel)
from .allocator import RiskBudgetAllocator
from .validation import ValidationGate, ValidationReport, combinatorial_purged_screen
from .research import (ExecutionProfile, MultiStrategyResearchFramework,
                       ResearchDataset, StrategySpec, default_strategies)
from .core_engine import CoreStatus, CoreTradingEngine
from .loop_snapshot import (LOOP_SNAPSHOT_SCHEMA_VERSION, build_loop_snapshot,
                            write_loop_snapshot)
from .loop_engineering import (DriftMonitor, DriftPolicy, DriftResearchQueue,
                               DriftSnapshot, EvaluationEvidence, ExperimentContract,
                               ExperimentMemory, ExperimentMemoryRecord,
                               ExperimentRunResult, LoopDecision, LoopVerdict,
                               OneContractResearchRunner, ResearchTaskDraft,
                               PaperReviewDecision, PaperReviewLedger,
                               PaperReviewRecord,
                               deterministic_verdict,
                               sha256_file, sha256_paths)
from .fund_ops import (AppendOnlyLedger, ConnectorSync, EventType, LedgerEvent,
                       PlatformBalance, PnLSnapshot, Position,
                       ReadOnlyPlatformConnector)
from .fund_storage import SQLiteLedgerStore
from .binance_connector import BinanceReadOnlyCredentials, BinanceSpotReadOnlyConnector
from .binance_futures_connector import BinanceUsdmFundingReadOnlyConnector
from .reconciliation import (ReconciliationException, ReconciliationResult,
                             ReconciliationStatus, reconcile_positions)
from .fund_reporting import DailyCloseReport, build_daily_close, write_daily_close
from .fund_controls import AccessController, AuditEvent, Operation, Role
from .fund_ops_job import DailyCloseRun, run_read_only_daily_close
from .fund_v2 import (CloseRegistry, InternalReportService, PaperExecutionGate,
                      PaperOrder, PortfolioClose, ValuationPolicy, aggregate_closes,
                      ApprovedFxValuation, time_weighted_return)

# NOTE: cognee_adapter is intentionally NOT imported here — it guards an
# optional dependency (cognee). Import it explicitly where needed:
#   from dynamic_grid.cognee_adapter import push_log, push_findings, recall

__all__ = [
    "generate_scenario", "SCENARIOS",
    "DynamicGridConfig", "DynamicGridEngine", "StaticGridEngine",
    "has_positive_edge", "round_trip_cost_frac",
    "LayerSpec", "MultiLayerOrchestrator", "make_layers",
    "run_backtest", "run_backtest_engine", "BacktestResult", "optimize",
    "load_binance_klines", "walk_forward", "FoldResult",
    "DecisionLog", "DecisionEvent", "MemoryOrchestrator",
    "ShortGridEngine", "load_bear_market", "RLGovernor", "train_q",
    "train_q_on_ohlc",
    "RegimeSwitchingOrchestrator",
    "StrategySignal", "RegimeSignalModel", "FundingBiasModel",
    "RelativeStrengthModel", "RiskBudgetAllocator",
    "ValidationGate", "ValidationReport", "combinatorial_purged_screen",
    "ExecutionProfile", "MultiStrategyResearchFramework", "ResearchDataset",
    "StrategySpec", "default_strategies",
    "CoreStatus", "CoreTradingEngine",
    "LOOP_SNAPSHOT_SCHEMA_VERSION", "build_loop_snapshot", "write_loop_snapshot",
    "DriftMonitor", "DriftPolicy", "DriftResearchQueue", "DriftSnapshot",
    "EvaluationEvidence", "ExperimentContract", "ExperimentMemory",
    "ExperimentMemoryRecord", "ExperimentRunResult", "LoopDecision",
    "LoopVerdict", "OneContractResearchRunner", "ResearchTaskDraft",
    "PaperReviewDecision", "PaperReviewLedger", "PaperReviewRecord",
    "deterministic_verdict",
    "sha256_file", "sha256_paths",
    "AppendOnlyLedger", "ConnectorSync", "EventType", "LedgerEvent",
    "PlatformBalance", "PnLSnapshot", "Position", "ReadOnlyPlatformConnector",
    "SQLiteLedgerStore", "BinanceReadOnlyCredentials", "BinanceSpotReadOnlyConnector",
    "BinanceUsdmFundingReadOnlyConnector",
    "ReconciliationException", "ReconciliationResult", "ReconciliationStatus",
    "reconcile_positions", "DailyCloseReport", "build_daily_close", "write_daily_close",
    "AccessController", "AuditEvent", "Operation", "Role",
    "DailyCloseRun", "run_read_only_daily_close",
    "CloseRegistry", "InternalReportService", "PaperExecutionGate", "PaperOrder",
    "PortfolioClose", "ValuationPolicy", "ApprovedFxValuation", "aggregate_closes",
    "time_weighted_return",
]
