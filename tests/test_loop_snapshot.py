import json
from pathlib import Path
import tempfile
import unittest

from dynamic_grid.loop_engineering import (
    DriftMonitor,
    DriftResearchQueue,
    DriftSnapshot,
    ExperimentContract,
    ExperimentMemory,
    LoopDecision,
    LoopVerdict,
    PaperReviewDecision,
    PaperReviewLedger,
)
from dynamic_grid.loop_snapshot import build_loop_snapshot, write_loop_snapshot


class LoopSnapshotTests(unittest.TestCase):
    def contract(self, experiment_id):
        return ExperimentContract(
            experiment_id=experiment_id,
            hypothesis=f"Hypothesis for {experiment_id}",
            candidates=("candidate",), benchmarks=("cash", "incumbent"),
            datasets=("BTCUSDT 4h",), held_out_split="last 30%",
            seeds=(1, 2, 3), max_trials=10)

    def snapshot_metric(self, observed_at, robust_score):
        return DriftSnapshot(
            dataset="BTCUSDT 4h", observed_at=observed_at, sample_count=60,
            robust_score=robust_score, max_drawdown=0.04,
            execution_cost_bps=8.0, data_gap_rate=0.0)

    def test_empty_sources_produce_read_only_versioned_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = build_loop_snapshot(
                memory=ExperimentMemory(root / "memory.jsonl"),
                drift_queue=DriftResearchQueue(root / "drift.jsonl"),
                generated_at="2026-07-16T00:00:00+00:00")
            self.assertEqual(snapshot["schemaVersion"], 1)
            self.assertTrue(snapshot["readOnly"])
            self.assertEqual(snapshot["summary"]["experimentCount"], 0)
            self.assertFalse(any(snapshot["capabilities"].values()))

    def test_snapshot_projects_verified_lineage_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory = ExperimentMemory(root / "memory.jsonl")
            memory.append(
                self.contract("E26"), code_hash="a" * 64,
                data_hashes={"BTCUSDT 4h": "b" * 64},
                result={"candidate_mean_robust_score": -0.01, "trial_count": 4,
                        "validation_reports": {}},
                verdict=LoopVerdict(LoopDecision.KILL, ("lost to cash",)),
                recorded_at="2026-07-16T00:00:00+00:00")
            memory.append(
                self.contract("E27"), code_hash="c" * 64,
                data_hashes={"BTCUSDT 4h": "d" * 64},
                result={"candidate_mean_robust_score": 0.01, "trial_count": 6,
                        "validation_reports": {}},
                verdict=LoopVerdict(LoopDecision.PAPER_REVIEW,
                                    ("independent review required",)),
                recorded_at="2026-07-17T00:00:00+00:00")
            reviews = PaperReviewLedger(root / "reviews.jsonl", memory)
            reviews.submit(
                "E27", reviewer="independent-reviewer",
                decision=PaperReviewDecision.APPROVED_FOR_PAPER,
                rationale="Cross-asset evidence independently confirmed",
                reviewed_at="2026-07-18T00:00:00+00:00")
            queue = DriftResearchQueue(root / "drift.jsonl")
            task = DriftMonitor().evaluate(
                "dual_pct",
                self.snapshot_metric("2026-07-01T00:00:00+00:00", 0.03),
                self.snapshot_metric("2026-07-23T00:00:00+00:00", -0.01))
            queue.open(task)

            snapshot = build_loop_snapshot(
                memory=memory, drift_queue=queue, review_ledger=reviews)
            self.assertEqual([item["experimentId"] for item in snapshot["experiments"]],
                             ["E27", "E26"])
            self.assertEqual(snapshot["summary"]["verdictCounts"]["kill"], 1)
            self.assertEqual(snapshot["summary"]["verdictCounts"]["paper_review"], 1)
            self.assertEqual(snapshot["summary"]["openDriftTaskCount"], 1)
            self.assertEqual(snapshot["integrity"]["experimentChain"], "verified")
            self.assertEqual(snapshot["integrity"]["reviewChain"], "verified")
            self.assertEqual(snapshot["summary"]["reviewCounts"]["approved_for_paper"], 1)
            self.assertEqual(snapshot["summary"]["reviewCounts"]["pending"], 0)
            self.assertEqual(snapshot["experiments"][0]["maker"], "research-agent")
            self.assertEqual(
                snapshot["experiments"][0]["paperReview"]["reviewer"],
                "independent-reviewer")
            self.assertIsNone(snapshot["experiments"][1]["paperReview"])

    def test_tampered_memory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory = ExperimentMemory(root / "memory.jsonl")
            memory.append(self.contract("E26"), code_hash="a" * 64,
                          data_hashes={"BTCUSDT 4h": "b" * 64})
            payload = json.loads(memory.path.read_text(encoding="utf-8"))
            payload["contract"]["hypothesis"] = "tampered"
            memory.path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build_loop_snapshot(
                    memory=memory,
                    drift_queue=DriftResearchQueue(root / "drift.jsonl"))

    def test_writer_emits_complete_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = build_loop_snapshot(
                memory=ExperimentMemory(root / "memory.jsonl"),
                drift_queue=DriftResearchQueue(root / "drift.jsonl"))
            target = root / "snapshot.json"
            write_loop_snapshot(snapshot, target)
            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded, snapshot)
            self.assertEqual(list(root.glob(".snapshot.json.*")), [])


if __name__ == "__main__":
    unittest.main()
