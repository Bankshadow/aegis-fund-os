"""Invariants for the deterministic egress policy and the trifecta guard.

A guardrail nobody has watched fire is not a guardrail. Every check here plants
a violation and asserts it is caught, then asserts the real repository is clean.

Doctrine from Archestra, no code from it — see `docs/ARCHESTRA_ADOPTION.md`.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "gate"
sys.path.insert(0, str(GATE))

import egress_scan  # noqa: E402
import eval_gate    # noqa: E402


class ScanTests(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def policy(self, *hosts, live=()):
        entries = {h: {"purpose": "test", "live_trading": False} for h in hosts}
        for h in live:
            entries[h] = {"purpose": "test", "live_trading": True}
        return {"hosts": entries}

    def test_an_undeclared_host_is_caught_with_a_file_and_line(self):
        self.write("connector.py", '\n\nURL = "https://api.evil.example.com/x"\n')  # egress-scan: fixture
        missing = egress_scan.undeclared(self.root, self.policy())
        self.assertIn("api.evil.example.com", missing)
        self.assertEqual(missing["api.evil.example.com"], ["connector.py:3"])

    def test_a_declared_host_is_not_reported(self):
        self.write("connector.py", 'URL = "https://api.binance.com/x"\n')  # egress-scan: fixture
        self.assertEqual(egress_scan.undeclared(self.root, self.policy("api.binance.com")), {})

    def test_a_scheme_less_host_constant_is_caught(self):
        # The hole the scan found in itself: `WEBULL_SANDBOX_HOST` pins a bare
        # hostname, which the URL pattern alone walks straight past.
        self.write("webull.ts", 'const WEBULL_SANDBOX_HOST = "api.sandbox.webull.com";\n')  # egress-scan: fixture
        missing = egress_scan.undeclared(self.root, self.policy())
        self.assertIn("api.sandbox.webull.com", missing)

    def test_bare_host_matching_needs_a_host_shaped_name(self):
        # Precision matters more than reach here: a scan that reports every
        # dotted string would be muted within a week.
        self.write("misc.ts", 'const README_FILE = "news-risk.ts";\nconst v = "1.2.3";\n')
        self.assertEqual(egress_scan.undeclared(self.root, self.policy()), {})

    def test_loopback_and_reserved_test_domains_are_not_egress(self):
        self.write("fixture.mjs", "\n".join([
            'a = "http://localhost:3000/api"',
            'b = "https://news.test/feed"',
            'c = "https://thing.example/x"',
            'd = "https://host.invalid/y"',
        ]))
        self.assertEqual(egress_scan.undeclared(self.root, self.policy()), {})

    def test_vendored_and_generated_trees_are_skipped(self):
        # `.pnpm-store` mirrors our own sources back, so findings there name a
        # path nobody can fix.
        for skipped in ("node_modules", ".pnpm-store", "dist", "data"):
            self.write(f"{skipped}/dep.js", 'u = "https://cdn.vendor.net/a.js"')  # egress-scan: fixture
        self.assertEqual(egress_scan.undeclared(self.root, self.policy()), {})

    def test_only_source_suffixes_are_scanned(self):
        self.write("notes.md", "see https://blog.somewhere.net/post")  # egress-scan: fixture
        self.assertEqual(egress_scan.undeclared(self.root, self.policy()), {})

    def test_a_live_trading_host_is_refused(self):
        policy = self.policy("api.binance.com", live=("api.realvenue.com",))
        self.assertEqual(egress_scan.live_trading_hosts(policy), ["api.realvenue.com"])
        self.assertEqual(egress_scan.live_trading_hosts(self.policy("api.binance.com")), [])

    def test_a_declared_host_that_left_the_source_is_reported_but_not_fatal(self):
        self.write("connector.py", 'URL = "https://api.binance.com/x"')  # egress-scan: fixture
        policy = self.policy("api.binance.com", "api.gone.com")
        self.assertEqual(egress_scan.stale_entries(self.root, policy), ["api.gone.com"])
        self.assertEqual(egress_scan.undeclared(self.root, policy), {})

    def test_the_fixture_pragma_suppresses_a_line_and_is_counted(self):
        # This file needs realistic hosts to prove detection works, so the
        # pragma exists — but a silent opt-out would be worse than no scan.
        self.write("f.py", 'a = "https://api.suppressed.net/x"  # egress-scan: fixture\n'
                           'b = "https://api.visible.net/y"\n')  # egress-scan: fixture
        missing = egress_scan.undeclared(self.root, self.policy())
        self.assertEqual(list(missing), ["api.visible.net"])
        self.assertEqual(egress_scan.suppressed_count(self.root), 1)

    def test_every_occurrence_is_listed_not_just_the_first(self):
        self.write("a.py", 'x = "https://api.two.com/1"')  # egress-scan: fixture
        self.write("b/c.ts", 'y = "https://api.two.com/2"')  # egress-scan: fixture
        sites = egress_scan.undeclared(self.root, self.policy())["api.two.com"]
        self.assertEqual(sites, ["a.py:1", "b/c.ts:1"])


class TrifectaGuardTests(unittest.TestCase):
    """The untrusted-content path must stay free of an instructable model."""

    def test_provider_markers_are_detected(self):
        for snippet in ('import Anthropic from "@anthropic-ai/sdk"',
                        'fetch("https://api.openai.com/v1/chat")',  # egress-scan: fixture
                        'model: "claude-opus-5"',
                        'model: "gpt-4o"'):
            self.assertTrue(eval_gate.model_markers_in(snippet), snippet)

    def test_ordinary_scoring_code_is_not_flagged(self):
        self.assertEqual(eval_gate.model_markers_in(
            'const NEGATIVE = ["hack", "exploit"]; score += weight;'), [])

    def test_the_declared_untrusted_path_still_exists(self):
        # A rename must not silently retire the guard.
        for rel in eval_gate.UNTRUSTED_CONTENT_PATH:
            self.assertTrue((egress_scan.ROOT / rel).is_file(), rel)


class RealRepositoryTests(unittest.TestCase):

    def test_the_repository_declares_every_host_it_reaches(self):
        self.assertEqual(egress_scan.undeclared(), {})

    def test_the_repository_declares_no_live_trading_host(self):
        self.assertEqual(egress_scan.live_trading_hosts(), [])

    def test_the_news_path_reaches_no_model(self):
        for rel in eval_gate.UNTRUSTED_CONTENT_PATH:
            text = (egress_scan.ROOT / rel).read_text(encoding="utf-8")
            self.assertEqual(eval_gate.model_markers_in(text), [], rel)

    def test_every_news_feed_host_is_flagged_untrusted(self):
        # The news feeds are the untrusted-content leg of the trifecta; losing
        # that label would hide the reason the LLM-free rule exists.
        #
        # This asserts the direction that actually protects the news board:
        # every host the board reaches must carry the flag. The converse — that
        # a flagged host must live in the news board — was asserted here
        # originally and is simply false: untrusted third-party text also
        # arrives through research pulls (DefiLlama and CoinGecko return
        # protocol and coin names that anyone can craft). Keeping the old
        # direction would have forced those hosts to be mislabelled as trusted
        # just to keep a test green.
        policy = egress_scan.load_policy()
        flagged = {h for h, e in policy["hosts"].items() if e.get("untrusted_content")}
        news = (egress_scan.ROOT / "fund-command-center-local/src/lib/news-risk.ts"
                ).read_text(encoding="utf-8")
        reached_by_news = {h for h in policy["hosts"] if h in news}
        self.assertTrue(reached_by_news, "the news path reaches no declared host")
        for host in sorted(reached_by_news):
            self.assertIn(host, flagged,
                          f"{host} is used by the news board but not flagged untrusted")
        self.assertGreaterEqual(len(reached_by_news), 8)

    def test_the_policy_file_documents_each_declared_host(self):
        policy = egress_scan.load_policy()
        for host, entry in policy["hosts"].items():
            self.assertTrue(entry.get("purpose"), f"{host} has no stated purpose")
            self.assertIn(entry.get("access"),
                          {"read", "sandbox-write", "asset", "reference", "fixture"}, host)
            self.assertIs(entry.get("live_trading"), False, host)

    def test_the_policy_is_valid_json_with_the_expected_shape(self):
        raw = json.loads((egress_scan.ALLOWLIST).read_text(encoding="utf-8"))
        self.assertIn("hosts", raw)
        self.assertIn("doctrine_source", raw)


if __name__ == "__main__":
    unittest.main()
