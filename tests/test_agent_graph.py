"""L2 agent-graph contracts and diamond ops — isolated from trading runtime."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from agent.graph_contracts import DiamondPlan, EdgeContract, NodeContract, ReviewFinding
from agent.graph_ops import (
    adversarial_keep,
    highest_severity,
    is_real_edge,
    loop_until_dry,
    reduce_findings,
    route_review_severity,
)


AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"


class GraphContractTests(unittest.TestCase):
    def test_finding_requires_evidence(self):
        finding = ReviewFinding("f1", "missing auth", "high", "security", "")
        with self.assertRaises(ValueError):
            finding.validate()

    def test_edge_requires_data_key(self):
        with self.assertRaises(ValueError):
            EdgeContract("a", "b", "  ").validate()

    def test_diamond_requires_code_reduce(self):
        with self.assertRaises(ValueError):
            DiamondPlan("p1", "split", ("w1",), False, "synth").validate()


class GraphOpsTests(unittest.TestCase):
    def test_false_and_then_is_not_an_edge(self):
        self.assertFalse(is_real_edge("summary", None))
        self.assertFalse(is_real_edge("a", "b"))
        self.assertTrue(is_real_edge("findings", "findings"))

    def test_reduce_dedupes_and_validates(self):
        a = ReviewFinding("f1", "one", "low", "correctness", "line 1")
        b = ReviewFinding("f1", "dup", "high", "security", "line 2")
        c = ReviewFinding("f2", "two", "medium", "repro", "stack")
        reduced = reduce_findings([a, b, c])
        self.assertEqual([item.finding_id for item in reduced], ["f1", "f2"])
        self.assertEqual(highest_severity(reduced), "medium")

    def test_severity_router_is_deterministic(self):
        self.assertEqual(route_review_severity("low"), "quick_pass")
        self.assertEqual(route_review_severity("medium"), "parallel_audit")
        self.assertEqual(route_review_severity("high"), "judge_panel")

    def test_adversarial_majority(self):
        finding = ReviewFinding("f1", "race", "high", "correctness", "lease")
        self.assertTrue(adversarial_keep(finding, [True, False, True], majority=2))
        self.assertFalse(adversarial_keep(finding, [True, False, False], majority=2))

    def test_loop_until_dry_dedupes_against_seen(self):
        calls = {"n": 0}

        def find(seen: set[str]):
            calls["n"] += 1
            # Same dead-end id every round unless caller tracks seen.
            return [
                ReviewFinding("dead", "dup", "low", "correctness", "x"),
                ReviewFinding(f"new-{calls['n']}", "fresh", "medium", "security", "y"),
            ] if "dead" not in seen or calls["n"] <= 2 else [
                ReviewFinding("dead", "dup", "low", "correctness", "x"),
            ]

        kept = loop_until_dry(find, dry_rounds=2, max_rounds=6)
        ids = [item.finding_id for item in kept]
        self.assertIn("dead", ids)
        self.assertTrue(any(item.startswith("new-") for item in ids))
        self.assertEqual(ids.count("dead"), 1)
        self.assertGreaterEqual(calls["n"], 3)


class FirewallTests(unittest.TestCase):
    def test_agent_graph_modules_do_not_import_runtime(self):
        banned = (
            "fund_command_center",
            "fund-command-center",
            "grid_reconcile",
            "grid_runtime",
            "binance",
            "place_order",
            "placeOrder",
        )
        paths = [
            AGENT_DIR / "graph_contracts.py",
            AGENT_DIR / "graph_ops.py",
            AGENT_DIR / "diamonds" / "runtime_safety_review.py",
        ]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                joined = " ".join(names).lower()
                for token in banned:
                    self.assertNotIn(token, joined, msg=f"{path.name} imported {joined}")


class RuntimeSafetyDiamondTests(unittest.TestCase):
    def test_diamond_reports_clean_on_current_sources(self):
        from agent.diamonds.runtime_safety_review import run_diamond

        report = run_diamond()
        self.assertEqual(report["plan_id"], "runtime-safety-review")
        self.assertEqual(report["finding_count"], 0)
        self.assertEqual(report["action"], "quick_pass")
        self.assertEqual(len(report["lenses"]), 3)


class NodeShapeTests(unittest.TestCase):
    def test_node_contract_round_trip_shape(self):
        node = NodeContract(
            name="review:security",
            job="hunt missing auth",
            input_keys=("route_path",),
            output_schema="ReviewFinding",
        )
        node.validate()
        self.assertEqual(node.output_schema, "ReviewFinding")


if __name__ == "__main__":
    unittest.main()
