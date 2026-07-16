import json
from pathlib import Path
import tempfile
import unittest

from dynamic_grid.loop_engineering import (
    ExperimentContract,
    ExperimentMemory,
    LoopDecision,
    LoopVerdict,
    PaperReviewDecision,
    PaperReviewLedger,
)


class PaperReviewLedgerTests(unittest.TestCase):
    def contract(self, experiment_id="E26", maker="maker@example.com"):
        return ExperimentContract(
            experiment_id=experiment_id,
            hypothesis="A volatility pause improves robust score.",
            candidates=("candidate",), benchmarks=("cash", "incumbent"),
            datasets=("BTCUSDT 4h",), held_out_split="last 30%",
            seeds=(1, 2, 3), max_trials=10, maker=maker)

    def memory_with_verdict(self, root, decision=LoopDecision.PAPER_REVIEW):
        memory = ExperimentMemory(root / "memory.jsonl")
        memory.append(
            self.contract(), code_hash="a" * 64,
            data_hashes={"BTCUSDT 4h": "b" * 64},
            verdict=LoopVerdict(decision, ("deterministic verdict",)))
        return memory

    def test_maker_cannot_review_own_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = PaperReviewLedger(root / "reviews.jsonl",
                                       self.memory_with_verdict(root))
            with self.assertRaisesRegex(PermissionError, "own experiment"):
                ledger.submit("E26", reviewer="MAKER@example.com",
                              decision=PaperReviewDecision.APPROVED_FOR_PAPER,
                              rationale="Looks good")

    def test_non_paper_verdict_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = PaperReviewLedger(
                root / "reviews.jsonl",
                self.memory_with_verdict(root, LoopDecision.KILL))
            with self.assertRaisesRegex(ValueError, "only paper_review"):
                ledger.submit("E26", reviewer="reviewer@example.com",
                              decision=PaperReviewDecision.APPROVED_FOR_PAPER,
                              rationale="Override the gate")

    def test_independent_decision_is_hash_chained_and_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory = self.memory_with_verdict(root)
            memory.append(
                self.contract("E27"), code_hash="c" * 64,
                data_hashes={"BTCUSDT 4h": "d" * 64},
                verdict=LoopVerdict(LoopDecision.PAPER_REVIEW, ("passed",)))
            ledger = PaperReviewLedger(root / "reviews.jsonl", memory)
            first = ledger.submit(
                "E26", reviewer="reviewer@example.com",
                decision=PaperReviewDecision.APPROVED_FOR_PAPER,
                rationale="Independent evidence review passed",
                reviewed_at="2026-07-16T00:00:00+00:00")
            second = ledger.submit(
                "E27", reviewer="reviewer@example.com",
                decision=PaperReviewDecision.REJECTED,
                rationale="Insufficient cross-asset evidence",
                reviewed_at="2026-07-17T00:00:00+00:00")
            self.assertEqual(second.previous_hash, first.record_hash)
            self.assertEqual(len(ledger.read_verified()), 2)
            with self.assertRaisesRegex(ValueError, "already recorded"):
                ledger.submit("E26", reviewer="other@example.com",
                              decision=PaperReviewDecision.REJECTED,
                              rationale="Try to rewrite decision")

    def test_tampered_review_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = PaperReviewLedger(root / "reviews.jsonl",
                                       self.memory_with_verdict(root))
            ledger.submit("E26", reviewer="reviewer@example.com",
                          decision=PaperReviewDecision.REJECTED,
                          rationale="Evidence incomplete")
            payload = json.loads(ledger.path.read_text(encoding="utf-8"))
            payload["decision"] = "approved_for_paper"
            ledger.path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                ledger.read_verified()

    def test_review_cannot_be_rebound_to_another_experiment_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_memory = self.memory_with_verdict(root)
            review_path = root / "reviews.jsonl"
            PaperReviewLedger(review_path, original_memory).submit(
                "E26", reviewer="reviewer@example.com",
                decision=PaperReviewDecision.APPROVED_FOR_PAPER,
                rationale="Independent evidence review passed")
            other_memory = ExperimentMemory(root / "other-memory.jsonl")
            other_memory.append(
                self.contract(), code_hash="f" * 64,
                data_hashes={"BTCUSDT 4h": "e" * 64},
                verdict=LoopVerdict(LoopDecision.PAPER_REVIEW, ("passed",)))
            with self.assertRaisesRegex(ValueError, "experiment binding"):
                PaperReviewLedger(review_path, other_memory).read_verified()

    def test_live_decision_is_not_in_the_type_or_api(self):
        self.assertEqual(
            {item.value for item in PaperReviewDecision},
            {"approved_for_paper", "rejected"})


if __name__ == "__main__":
    unittest.main()
