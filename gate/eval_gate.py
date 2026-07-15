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
