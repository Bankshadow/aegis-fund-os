"""L2 agent-graph operations — pure code edges for harness diamonds.

Firewall: never imports trading runtime. Uses only graph_contracts.
Orchestration stays in code so model tokens are spent only on judgment nodes.
"""

from __future__ import annotations

from typing import Callable, Iterable

from agent.graph_contracts import (
    GraphAction,
    ReviewFinding,
    ReviewSeverity,
)


def is_real_edge(produces_key: str | None, consumes_key: str | None) -> bool:
    """True only when the next step reads the prior step's named output."""
    if not produces_key or not consumes_key:
        return False
    return produces_key.strip() == consumes_key.strip()


def reduce_findings(findings: Iterable[ReviewFinding]) -> tuple[ReviewFinding, ...]:
    """Code-only fan-in: validate, dedupe by finding_id, drop empties."""
    seen: set[str] = set()
    out: list[ReviewFinding] = []
    for item in findings:
        item.validate()
        if item.finding_id in seen:
            continue
        seen.add(item.finding_id)
        out.append(item)
    return tuple(out)


def route_review_severity(severity: ReviewSeverity) -> GraphAction:
    """Conditional edge: severity chooses path; routing itself is deterministic code."""
    if severity == "low":
        return "quick_pass"
    if severity == "medium":
        return "parallel_audit"
    return "judge_panel"


def highest_severity(findings: Iterable[ReviewFinding]) -> ReviewSeverity:
    order = {"low": 0, "medium": 1, "high": 2}
    peak: ReviewSeverity = "low"
    for item in findings:
        item.validate()
        if order[item.severity] > order[peak]:
            peak = item.severity
    return peak


def adversarial_keep(
    finding: ReviewFinding,
    verdicts: Iterable[bool],
    *,
    majority: int = 2,
) -> bool:
    """Keep a finding only if enough independent skeptics fail to kill it."""
    finding.validate()
    if majority < 1:
        raise ValueError("majority must be >= 1")
    return sum(1 for ok in verdicts if ok) >= majority


def loop_until_dry(
    find: Callable[[set[str]], Iterable[ReviewFinding]],
    *,
    dry_rounds: int = 2,
    max_rounds: int = 8,
) -> tuple[ReviewFinding, ...]:
    """Converging discovery cycle: dedupe against everything seen, not only kept.

    `find(seen)` receives the full seen-id set so rejected/duplicate ids do not
    reappear forever. Stops after `dry_rounds` consecutive empty rounds or
    `max_rounds` absolute.
    """
    if dry_rounds < 1 or max_rounds < 1:
        raise ValueError("dry_rounds and max_rounds must be >= 1")
    seen: set[str] = set()
    confirmed: list[ReviewFinding] = []
    dry = 0
    for _ in range(max_rounds):
        batch = list(find(seen))
        fresh: list[ReviewFinding] = []
        for item in batch:
            item.validate()
            if item.finding_id in seen:
                continue
            seen.add(item.finding_id)
            fresh.append(item)
        if not fresh:
            dry += 1
            if dry >= dry_rounds:
                break
            continue
        dry = 0
        confirmed.extend(fresh)
    return tuple(confirmed)
