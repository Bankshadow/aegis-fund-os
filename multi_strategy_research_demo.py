"""Cross-asset research run with regime switching and realistic execution."""

from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.research import (ExecutionProfile, MultiStrategyResearchFramework,
                                   ResearchDataset, default_strategies)


if __name__ == "__main__":
    datasets = tuple(ResearchDataset.from_market_data(symbol, "4h")
                     for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    base = DynamicGridConfig(use_regime_pct=True)
    framework = MultiStrategyResearchFramework(
        default_strategies(), execution=ExecutionProfile(extra_stop_slippage_bps=5.0))
    run = framework.run(datasets, base)

    print("Cross-asset leaderboard (mean return - 2*maxDD)")
    for name, score in run.leaderboard:
        print(f"  {name:18s} {score:+.4f}")
    print("\nValidation gates")
    for label, report in run.validation_by_dataset.items():
        print(f"  {label:12s} median={report.median_test_score:+.4f} "
              f"failure={report.selection_failure_rate:.1%}")
    print(f"\nSelected: {run.promotion.selected_strategy}")
    print("Paper eligible:", run.promotion.eligible_for_paper)
    for reason in run.promotion.reasons:
        print(" -", reason)
