import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from dynamic_grid.loop_cli import build_parser, export_loop_snapshot
from dynamic_grid.loop_engineering import ExperimentContract, ExperimentMemory


class LoopCliTests(unittest.TestCase):
    def paths(self, root):
        return {
            "memory_path": root / "memory.jsonl",
            "drift_queue_path": root / "drift.jsonl",
            "review_ledger_path": root / "reviews.jsonl",
            "output_path": root / "snapshot.json",
        }

    def test_export_verifies_empty_sources_and_writes_read_only_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(Path(tmp))
            snapshot = export_loop_snapshot(**paths)
            loaded = json.loads(paths["output_path"].read_text(encoding="utf-8"))
            self.assertEqual(loaded, snapshot)
            self.assertEqual(loaded["integrity"]["reviewChain"], "verified")
            self.assertFalse(any(loaded["capabilities"].values()))

    def test_tampered_memory_does_not_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(Path(tmp))
            memory = ExperimentMemory(paths["memory_path"])
            contract = ExperimentContract(
                experiment_id="E28", hypothesis="A falsifiable hypothesis",
                candidates=("candidate",), benchmarks=("cash", "incumbent"),
                datasets=("BTCUSDT 4h",), held_out_split="last 30%",
                seeds=(1, 2, 3), max_trials=5)
            memory.append(contract, code_hash="a" * 64,
                          data_hashes={"BTCUSDT 4h": "b" * 64})
            payload = json.loads(paths["memory_path"].read_text(encoding="utf-8"))
            payload["contract"]["hypothesis"] = "tampered"
            paths["memory_path"].write_text(json.dumps(payload) + "\n", encoding="utf-8")
            paths["output_path"].write_text("preserve-me", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                export_loop_snapshot(**paths)
            self.assertEqual(paths["output_path"].read_text(encoding="utf-8"),
                             "preserve-me")

    def test_parser_requires_all_four_paths(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])
        option_names = {option for action in parser._actions for option in action.option_strings}
        self.assertFalse({"--live", "--approve", "--place-order"} & option_names)

    def test_module_entrypoint_exports_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.paths(Path(tmp))
            result = subprocess.run(
                [sys.executable, "-m", "dynamic_grid.loop_cli",
                 "--memory", str(paths["memory_path"]),
                 "--drift-queue", str(paths["drift_queue_path"]),
                 "--review-ledger", str(paths["review_ledger_path"]),
                 "--output", str(paths["output_path"])],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("verified Loop snapshot exported", result.stdout)
            self.assertTrue(paths["output_path"].exists())


if __name__ == "__main__":
    unittest.main()
