"""Cheap offline router — prints decision, reason, and traffic-split hint.

Does not call models. Guilty until eval_gate + live traffic prove a 5x gap.
"""

from __future__ import annotations

import argparse
import re
import sys

MARKERS = (
    "why", "debug", "race", "deadlock", "refactor", "security",
    "overfit", "promote", "regime", "walk-forward", "walkforward",
    "funding", "reconcile", "ledger", "kill-switch",
)


def score(prompt: str) -> int:
    p = prompt.lower()
    pts = sum(1 for m in MARKERS if m in p)
    if re.search(r"```|def |class ", prompt):
        pts += 1
    if "failed" in p or "again" in p or "retry" in p:
        pts += 1
    if prompt.count("\n") > 40:
        pts += 1
    return pts


def route(prompt: str) -> tuple[str, str, str]:
    """Return (tier, reason, split_hint)."""
    pts = score(prompt)
    if pts <= 1:
        return ("cheap", f"score={pts} -> Luna/Haiku or Sonnet-low", "target >=70% cheap")
    if pts == 2:
        return ("mid", f"score={pts} -> Sonnet 5 / GPT-5.6 Sol @ medium-high", "mid is default driver")
    return (
        "frontier_in_loop",
        f"score={pts} -> Sonnet/Sol driver + Fable advisor (<=3 consults)",
        "frontier grams only",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline model router")
    ap.add_argument("prompt", nargs="?", default="", help="Task text to score")
    ap.add_argument("-f", "--file", type=str, help="Read prompt from file")
    args = ap.parse_args(argv)
    text = open(args.file, encoding="utf-8").read() if args.file else args.prompt
    if not text.strip():
        text = sys.stdin.read() if not sys.stdin.isatty() else "routine unittest fix"
    tier, reason, split = route(text)
    print(f"decision: {tier}")
    print(f"reason:   {reason}")
    print(f"split:    {split}")
    print("policy:   ROUTING.md (effort before model; gate is final vote)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
