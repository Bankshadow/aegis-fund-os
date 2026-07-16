import unittest

from dynamic_grid.loop_engineering import (
    ExperimentContract,
    LoopDecision,
    deterministic_verdict,
)
from dynamic_grid.validation import ValidationFold, ValidationReport


def passing_report():
    folds = tuple(ValidationFold((i,), "candidate", 0.04, 0.03, 1, 2)
                  for i in range(3))
    return ValidationReport(folds, median_test_score=0.03,
                            selection_failure_rate=0.0)


class LoopEngineeringTests(unittest.TestCase):
    def contract(self, **changes):
        values = dict(
            experiment_id="E26",
            hypothesis="A volatility pause improves held-out robust score.",
            candidates=("dual_pct_pause",),
            benchmarks=("cash", "dual_pct"),
            datasets=("BTCUSDT 4h", "ETHUSDT 4h"),
            held_out_split="last 30%, embargo 1 group",
            seeds=(11, 22, 33),
            max_trials=20,
        )
        values.update(changes)
        return ExperimentContract(**values)

    def test_contract_rejects_fewer_than_three_seeds(self):
        with self.assertRaisesRegex(ValueError, "three distinct seeds"):
            self.contract(seeds=(1, 2)).validate()

    def test_contract_rejects_live_target(self):
        with self.assertRaisesRegex(ValueError, "research or paper"):
            self.contract(target="live").validate()

    def test_verdict_kills_candidate_that_loses_to_cash(self):
        reports = {name: passing_report() for name in self.contract().datasets}
        verdict = deterministic_verdict(self.contract(), reports, -0.001)
        self.assertEqual(verdict.decision, LoopDecision.KILL)
        self.assertIn("cash", verdict.reasons[0])

    def test_verdict_stops_at_independent_paper_review(self):
        reports = {name: passing_report() for name in self.contract().datasets}
        verdict = deterministic_verdict(self.contract(), reports, 0.01)
        self.assertEqual(verdict.decision, LoopDecision.PAPER_REVIEW)
        self.assertIn("independent", verdict.reasons[0])


if __name__ == "__main__":
    unittest.main()
