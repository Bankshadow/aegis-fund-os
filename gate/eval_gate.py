"""Offline eval seatbelt for routing / prompt / gate changes.

Deterministic checks only — never calls a model.
Prints SHIP or BLOCKED. Exit 0 only on SHIP.

Held-out cases here are tiny fixtures that encode project laws so a
routing/prompt change that breaks doctrine fails before merge.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import egress_scan  # noqa: E402 — same-directory gate helper

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


CASES: list[tuple[str, Callable[[], None]]] = []


def case(name: str):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("constitutions_exist")
def _():
    for p in ("AGENTS.md", "CLAUDE.md", "ROUTING.md", "STATE.md"):
        assert (ROOT / p).is_file(), f"missing {p}"


@case("agents_has_never_live")
def _():
    text = _read("AGENTS.md").lower()
    assert "never" in text and "live" in text


@case("routing_names_gate")
def _():
    text = _read("ROUTING.md")
    assert "gate/verify" in text
    assert "Fable" in text or "fable" in text.lower()


@case("validation_gate_thresholds_intact")
def _():
    src = _read("dynamic_grid/validation.py")
    assert "min_median_score: float = 0.0" in src
    assert "max_selection_failure_rate: float = 0.50" in src


@case("executor_advisor_consult_cap")
def _():
    src = _read("agent/executor_advisor.py")
    assert "MAX_CONSULTS" in src
    m = re.search(r"MAX_CONSULTS\s*=\s*(\d+)", src)
    assert m and int(m.group(1)) <= 3


@case("handoff_forbids_rl_default")
def _():
    text = _read("docs/HANDOFF_CURSOR.md")
    assert "RL" in text
    assert "ห้าม" in text or "ไม่แนะนำ" in text


@case("egress_allowlist_complete")
def _():
    missing = egress_scan.undeclared()
    assert not missing, (
        "undeclared host(s): "
        + "; ".join(f"{h} at {sites[0]}" for h, sites in missing.items()))


@case("no_live_trading_host_declared")
def _():
    live = egress_scan.live_trading_hosts()
    assert not live, f"live-trading host(s) declared: {live}"


#: Files that read attacker-influenced text: RSS bodies, third-party HTML,
#: vendor status feeds. The lethal trifecta needs an instructable model in this
#: path; deterministic keyword rules cannot be instructed by their input. The
#: news board was built LLM-free for cost, and that choice is also what keeps
#: the Worker — which holds Testnet credentials and a placement path — out of
#: the trifecta. This case exists so the protection cannot be removed by
#: someone "improving" the scoring later.
UNTRUSTED_CONTENT_PATH = (
    "fund-command-center-local/src/lib/news-risk.ts",
    "fund-command-center-local/src/lib/news-risk.functions.ts",
)

MODEL_MARKERS = ("anthropic", "openai", "generativelanguage", "claude-",
                 "gpt-", "gemini-", "generatetext", "chatcompletion")


def model_markers_in(text: str) -> list:
    """Model-provider markers present in `text`, lowercased match."""
    lowered = text.lower()
    return [marker for marker in MODEL_MARKERS if marker in lowered]


@case("untrusted_content_path_has_no_model")
def _():
    for rel in UNTRUSTED_CONTENT_PATH:
        hit = model_markers_in(_read(rel))
        assert not hit, f"{rel} reaches a model ({hit}); untrusted input must stay LLM-free"


def main() -> int:
    failed = []
    for name, fn in CASES:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001 — report all seatbelt fails
            print(f"  FAIL  {name}: {exc}")
            failed.append(name)
    if failed:
        print("BLOCKED")
        print("failed:", ", ".join(failed))
        return 1
    print("SHIP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
