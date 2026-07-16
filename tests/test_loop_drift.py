from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest

from dynamic_grid.loop_engineering import (
    DriftMonitor,
    DriftPolicy,
    DriftResearchQueue,
    DriftSnapshot,
)


class DriftMonitorTests(unittest.TestCase):
    def snapshot(self, **changes):
        values = dict(
            dataset="BTCUSDT 4h",
            observed_at="2026-07-16T00:00:00+00:00",
            sample_count=60,
            robust_score=0.03,
            max_drawdown=0.04,
            execution_cost_bps=8.0,
            data_gap_rate=0.0,
        )
        values.update(changes)
        return DriftSnapshot(**values)

    def monitor(self):
        return DriftMonitor(DriftPolicy(
            min_sample_count=30,
            robust_score_drop=0.02,
            max_drawdown_increase=0.02,
            execution_cost_increase_bps=5.0,
            max_data_gap_rate=0.01,
        ))

    def test_stable_snapshot_opens_no_task(self):
        current = self.snapshot(observed_at="2026-07-23T00:00:00+00:00",
                                robust_score=0.025, max_drawdown=0.045)
        self.assertIsNone(self.monitor().evaluate("dual_pct", self.snapshot(), current))

    def test_insufficient_sample_opens_no_task(self):
        current = self.snapshot(sample_count=29, robust_score=-0.20)
        self.assertIsNone(self.monitor().evaluate("dual_pct", self.snapshot(), current))

    def test_degradation_creates_research_only_immutable_draft(self):
        current = self.snapshot(
            observed_at="2026-07-23T00:00:00+00:00",
            robust_score=-0.01, max_drawdown=0.07,
            execution_cost_bps=14.0, data_gap_rate=0.02)
        task = self.monitor().evaluate("dual_pct", self.snapshot(), current)
        self.assertEqual(task.action, "open_research_task")
        self.assertEqual(set(task.signals), {
            "robust_score_drop", "max_drawdown_increase",
            "execution_cost_increase", "data_gap_rate"})
        self.assertNotIn("parameters", task.__dataclass_fields__)
        with self.assertRaises(FrozenInstanceError):
            task.action = "change_parameters"

    def test_queue_is_append_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = DriftResearchQueue(Path(tmp) / "drift_tasks.jsonl")
            task = self.monitor().evaluate(
                "dual_pct", self.snapshot(),
                self.snapshot(observed_at="2026-07-23T00:00:00+00:00",
                              robust_score=-0.01))
            self.assertTrue(queue.open(task))
            self.assertFalse(queue.open(task))
            stored = queue.read()
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0], task)

    def test_cross_dataset_comparison_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dataset must match"):
            self.monitor().evaluate(
                "dual_pct", self.snapshot(),
                self.snapshot(dataset="ETHUSDT 4h"))


if __name__ == "__main__":
    unittest.main()
