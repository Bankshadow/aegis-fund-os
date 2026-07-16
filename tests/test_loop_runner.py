from pathlib import Path
import tempfile
import unittest

from dynamic_grid.loop_engineering import (
    EvaluationEvidence,
    ExperimentContract,
    ExperimentMemory,
    LoopDecision,
    OneContractResearchRunner,
)
from dynamic_grid.validation import ValidationFold, ValidationReport


def passing_report():
    folds = tuple(ValidationFold((i,), "candidate", 0.04, 0.03, 1, 2)
                  for i in range(3))
    return ValidationReport(folds, median_test_score=0.03,
                            selection_failure_rate=0.0)


class OneContractResearchRunnerTests(unittest.TestCase):
    def contract(self):
        return ExperimentContract(
            experiment_id="E26",
            hypothesis="A volatility pause improves held-out robust score.",
            candidates=("dual_pct_pause",),
            benchmarks=("cash", "dual_pct"),
            datasets=("BTCUSDT 4h",),
            held_out_split="last 30%, embargo 1 group",
            seeds=(11, 22, 33),
            max_trials=20,
        )

    def files(self, root):
        code, data = root / "strategy.py", root / "BTCUSDT_4h.json"
        code.write_text("PARAMETER = 1\n", encoding="utf-8")
        data.write_text("[[1,2,0,1]]\n", encoding="utf-8")
        return code, data

    def test_runner_records_one_immutable_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, data = self.files(root)
            memory = ExperimentMemory(root / "memory.jsonl")
            runner = OneContractResearchRunner(memory)
            calls = []

            def evaluate(contract):
                calls.append(contract.experiment_id)
                return EvaluationEvidence(
                    {"BTCUSDT 4h": passing_report()}, 0.01, 7)

            result = runner.run(
                self.contract(), code_paths=(code,),
                dataset_paths={"BTCUSDT 4h": data}, evaluate=evaluate,
                recorded_at="2026-07-16T00:00:00+00:00")
            self.assertEqual(calls, ["E26"])
            self.assertEqual(result.verdict.decision, LoopDecision.PAPER_REVIEW)
            record = memory.read_verified()[0]
            self.assertEqual(record.result["trial_count"], 7)
            self.assertEqual(record.result["candidate_mean_robust_score"], 0.01)

    def test_runner_rejects_dataset_mapping_before_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, data = self.files(root)
            runner = OneContractResearchRunner(ExperimentMemory(root / "memory.jsonl"))
            called = []
            with self.assertRaisesRegex(ValueError, "do not match contract"):
                runner.run(self.contract(), code_paths=(code,),
                           dataset_paths={"ETHUSDT 4h": data},
                           evaluate=lambda _: called.append(True))
            self.assertEqual(called, [])

    def test_runner_rejects_trial_budget_overrun_without_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, data = self.files(root)
            memory = ExperimentMemory(root / "memory.jsonl")
            runner = OneContractResearchRunner(memory)
            with self.assertRaisesRegex(ValueError, "trial budget"):
                runner.run(
                    self.contract(), code_paths=(code,),
                    dataset_paths={"BTCUSDT 4h": data},
                    evaluate=lambda _: EvaluationEvidence(
                        {"BTCUSDT 4h": passing_report()}, 0.01, 21))
            self.assertEqual(memory.read_verified(), ())

    def test_runner_detects_dataset_mutation_without_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, data = self.files(root)
            memory = ExperimentMemory(root / "memory.jsonl")
            runner = OneContractResearchRunner(memory)

            def mutate_data(_):
                data.write_text("changed during run\n", encoding="utf-8")
                return EvaluationEvidence(
                    {"BTCUSDT 4h": passing_report()}, 0.01, 1)

            with self.assertRaisesRegex(ValueError, "dataset changed"):
                runner.run(self.contract(), code_paths=(code,),
                           dataset_paths={"BTCUSDT 4h": data},
                           evaluate=mutate_data)
            self.assertEqual(memory.read_verified(), ())


if __name__ == "__main__":
    unittest.main()
