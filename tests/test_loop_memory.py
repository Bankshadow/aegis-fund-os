import json
from pathlib import Path
import tempfile
import unittest

from dynamic_grid.loop_engineering import (
    ExperimentContract,
    ExperimentMemory,
    LoopDecision,
    LoopVerdict,
    sha256_file,
    sha256_paths,
)


class ExperimentMemoryTests(unittest.TestCase):
    def contract(self, experiment_id="E26"):
        return ExperimentContract(
            experiment_id=experiment_id,
            hypothesis="A volatility pause improves held-out robust score.",
            candidates=("dual_pct_pause",),
            benchmarks=("cash", "dual_pct"),
            datasets=("BTCUSDT 4h",),
            held_out_split="last 30%, embargo 1 group",
            seeds=(11, 22, 33),
            max_trials=20,
        )

    def test_hash_helpers_are_content_and_path_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / "a.py", root / "b.py"
            first.write_text("print('a')\n", encoding="utf-8")
            second.write_text("print('b')\n", encoding="utf-8")
            self.assertEqual(len(sha256_file(first)), 64)
            combined = sha256_paths((first, second))
            second.write_text("print('changed')\n", encoding="utf-8")
            self.assertNotEqual(combined, sha256_paths((first, second)))

    def test_append_builds_verified_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.jsonl"
            memory = ExperimentMemory(path)
            first = memory.append(
                self.contract("E26"), code_hash="a" * 64,
                data_hashes={"BTCUSDT 4h": "b" * 64},
                recorded_at="2026-07-16T00:00:00+00:00")
            second = memory.append(
                self.contract("E27"), code_hash="c" * 64,
                data_hashes={"BTCUSDT 4h": "d" * 64},
                verdict=LoopVerdict(LoopDecision.KILL, ("lost to cash",)),
                recorded_at="2026-07-17T00:00:00+00:00")
            verified = memory.read_verified()
            self.assertEqual([item.sequence for item in verified], [1, 2])
            self.assertEqual(second.previous_hash, first.record_hash)
            self.assertEqual(verified[1].verdict["decision"], "kill")

    def test_duplicate_experiment_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = ExperimentMemory(Path(tmp) / "memory.jsonl")
            args = dict(code_hash="a" * 64,
                        data_hashes={"BTCUSDT 4h": "b" * 64})
            memory.append(self.contract(), **args)
            with self.assertRaisesRegex(ValueError, "already recorded"):
                memory.append(self.contract(), **args)

    def test_tampering_is_detected_before_next_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.jsonl"
            memory = ExperimentMemory(path)
            memory.append(self.contract(), code_hash="a" * 64,
                          data_hashes={"BTCUSDT 4h": "b" * 64})
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["contract"]["hypothesis"] = "rewritten after results"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                memory.read_verified()


if __name__ == "__main__":
    unittest.main()
