"""Show how research approval controls the consolidated core engine."""

from dynamic_grid.backtest import run_backtest_engine
from dynamic_grid.core_engine import CoreTradingEngine
from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.research import (ExecutionProfile, MultiStrategyResearchFramework,
                                   ResearchDataset, default_strategies)


if __name__ == "__main__":
    dataset = ResearchDataset.from_market_data("BTCUSDT", "4h")
    research = MultiStrategyResearchFramework(default_strategies()).run(
        (dataset,), DynamicGridConfig(use_regime_pct=True))
    core = CoreTradingEngine(
        DynamicGridConfig(), research.promotion, dataset=dataset,
        execution=ExecutionProfile())
    result = run_backtest_engine(dataset.ohlc, core, liquidate_at_end=True)
    print(f"core mode: {core.status.mode}")
    print(f"strategy: {core.status.selected_strategy}")
    print(f"reason: {core.status.reason}")
    print(f"return: {result.total_return:+.2%}")
