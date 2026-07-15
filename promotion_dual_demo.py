"""E21: Promotion gate with dual_pct on Line B (BTC/ETH/SOL 4h).

Protocol (declared before run):
  Candidates = cash + buy_hold + regime_router + regime_allocator + dual_pct
  Datasets   = BTCUSDT / ETHUSDT / SOLUSDT × 4h
  Costs      = ExecutionProfile (real half-spread + funding + stop slippage)
  Base cfg   = use_regime_pct=True (no RL / funding bias / relative)
  Gate       = ValidationGate defaults (median_test_score >= 0,
               failure_rate <= 50%, folds >= 3) must pass EVERY dataset

Pass criterion (aggregate):
  eligible_for_paper=True AND selected_strategy == "dual_pct"
  Otherwise record FAIL honestly (wiring still counts as done).
"""

from dynamic_grid.core_engine import CoreTradingEngine
from dynamic_grid.grid_engine import DynamicGridConfig
from dynamic_grid.research import (ExecutionProfile, MultiStrategyResearchFramework,
                                   ResearchDataset, default_strategies)


if __name__ == "__main__":
    datasets = tuple(
        ResearchDataset.from_market_data(symbol, "4h")
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    base = DynamicGridConfig(use_regime_pct=True)
    execution = ExecutionProfile(extra_stop_slippage_bps=5.0)
    names = [s.name for s in default_strategies()]
    assert "dual_pct" in names, "dual_pct missing from default_strategies"

    print("E21 candidates:", ", ".join(names))
    print("Datasets:", ", ".join(d.label for d in datasets))
    print("Gate: median_test_score>=0, failure_rate<=50%, folds>=3 (all datasets)")
    print("Pass if: eligible_for_paper and selected_strategy==dual_pct\n")

    framework = MultiStrategyResearchFramework(
        default_strategies(), execution=execution)
    run = framework.run(datasets, base)

    print("Leaderboard (mean return - 2*maxDD)")
    for name, score in run.leaderboard:
        print(f"  {name:18s} {score:+.4f}")

    print("\nValidation gates")
    for label, report in run.validation_by_dataset.items():
        passed = framework.gate.passes(report)
        print(f"  {label:12s} median={report.median_test_score:+.4f} "
              f"failure={report.selection_failure_rate:.1%} "
              f"folds={len(report.folds)} "
              f"{'PASS' if passed else 'FAIL'}")

    promo = run.promotion
    print(f"\nSelected: {promo.selected_strategy}")
    print(f"Paper eligible: {promo.eligible_for_paper}")
    for reason in promo.reasons:
        print(f" - {reason}")

    e21_pass = (promo.eligible_for_paper
                and promo.selected_strategy == "dual_pct")
    print(f"\nE21 verdict: {'PASS' if e21_pass else 'FAIL'}")

    core = CoreTradingEngine(
        DynamicGridConfig(), promo, dataset=datasets[0], execution=execution)
    print(f"Core mode: {core.status.mode} / strategy={core.status.selected_strategy}")
