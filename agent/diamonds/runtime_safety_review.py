"""L2 diamond #1 — adversarial static review of Testnet runtime safety paths.

Fan-out three deterministic lenses (correctness / concurrency / fail-closed),
reduce with code, then route by highest severity. Never imports Fund OS runtime
modules as libraries — only reads source text. No model calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.graph_contracts import DiamondPlan, ReviewFinding
from agent.graph_ops import highest_severity, reduce_findings, route_review_severity

REPO = Path(__file__).resolve().parents[2]
FCC = REPO / "fund-command-center-local" / "src" / "lib"

TARGETS = {
    "safety": FCC / "grid-runtime-safety.ts",
    "reconcile": FCC / "grid-reconcile.ts",
    "graph": FCC / "grid-runtime-graph.ts",
    "fleet": FCC / "grid-runtime-fleet.ts",
}


def _read(name: str) -> tuple[str, str]:
    path = TARGETS[name]
    return str(path.relative_to(REPO)).replace("\\", "/"), path.read_text(encoding="utf-8")


def lens_correctness(_seen: set[str]) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    path, text = _read("safety")
    if "finishRuntimeRun" in text and "result.route" not in text and "classifyReconcileRoute" not in text:
        findings.append(ReviewFinding(
            "correctness-route-persist",
            "Runtime run finish may omit route classification",
            "high",
            "correctness",
            "finishRuntimeRun should persist route on success and failure",
            path,
        ))
    if "releaseRuntimeLease" not in text or "finally" not in text:
        findings.append(ReviewFinding(
            "correctness-lease-finally",
            "Lease release must live in finally",
            "high",
            "correctness",
            "acquire without finally-release strands the bot lease",
            path,
        ))
    path_r, text_r = _read("reconcile")
    if "route: classifyReconcileRoute" not in text_r and "classifyReconcileRoute(summary)" not in text_r:
        findings.append(ReviewFinding(
            "correctness-reconcile-route",
            "Reconcile result missing route classification",
            "medium",
            "correctness",
            "ReconcileResult.route should be attached after summary build",
            path_r,
        ))
    return findings


def lens_concurrency(_seen: set[str]) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    path, text = _read("safety")
    if "renewRuntimeLease" not in text:
        findings.append(ReviewFinding(
            "concurrency-lease-renew",
            "Missing lease renewal before placement",
            "high",
            "security",
            "Long multi-order runs need renewRuntimeLease in beforePlace",
            path,
        ))
    if "acquireRuntimeLease" not in text:
        findings.append(ReviewFinding(
            "concurrency-lease-acquire",
            "Missing compare-and-set lease acquire",
            "high",
            "security",
            "Concurrent cron/manual sync must be serialized per bot",
            path,
        ))
    path_f, text_f = _read("fleet")
    if "reconcileTestnetGridSafely" not in text_f:
        findings.append(ReviewFinding(
            "concurrency-fleet-safety",
            "Fleet dry-loop bypasses safety wrapper",
            "high",
            "security",
            "Every dry-loop iteration must call reconcileTestnetGridSafely",
            path_f,
        ))
    return findings


def lens_fail_closed(_seen: set[str]) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    path, text = _read("safety")
    if "killSwitch" not in text:
        findings.append(ReviewFinding(
            "failclosed-kill-switch",
            "Global kill switch check missing",
            "high",
            "security",
            "Placement must refuse when GRID_TESTNET_KILL_SWITCH is armed",
            path,
        ))
    if "stale or invalid" not in text and "maxStatusAgeSeconds" not in text:
        findings.append(ReviewFinding(
            "failclosed-stale-evidence",
            "Stale exchange evidence gate missing",
            "high",
            "security",
            "Status checkedAt must be validated before place",
            path,
        ))
    path_g, text_g = _read("graph")
    if "operator_review" not in text_g:
        findings.append(ReviewFinding(
            "failclosed-mismatch-route",
            "Mismatch path does not demand operator review",
            "medium",
            "repro",
            "reconciliationRequired must map to operator_review",
            path_g,
        ))
    path_f, text_f = _read("fleet")
    if 'GRID_RECONCILE_DRY_LOOP' not in text_f and 'enabled: env.GRID_RECONCILE_DRY_LOOP' not in text_f:
        # dryLoopPolicyFromEnv uses the env key
        if "DRY_LOOP" not in text_f:
            findings.append(ReviewFinding(
                "failclosed-dry-loop-optin",
                "Dry-loop is not opt-in gated",
                "medium",
                "repro",
                "Dry-loop must default off and require explicit env arming",
                path_f,
            ))
    return findings


LENSES = (
    ("correctness", lens_correctness),
    ("concurrency", lens_concurrency),
    ("fail_closed", lens_fail_closed),
)


def run_diamond() -> dict:
    DiamondPlan(
        plan_id="runtime-safety-review",
        split_node="scope:runtime-safety",
        work_nodes=tuple(name for name, _ in LENSES),
        reduce_is_code=True,
        synthesize_node="route_review_severity",
    ).validate()

    raw: list[ReviewFinding] = []
    for _name, lens in LENSES:
        raw.extend(lens(set()))
    reduced = reduce_findings(raw)
    severity = highest_severity(reduced) if reduced else "low"
    action = route_review_severity(severity)
    return {
        "plan_id": "runtime-safety-review",
        "findings": [item.to_dict() for item in reduced],
        "finding_count": len(reduced),
        "peak_severity": severity,
        "action": action,
        "lenses": [name for name, _ in LENSES],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L2 diamond: runtime safety adversarial review")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    args = parser.parse_args(argv)
    report = run_diamond()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"plan: {report['plan_id']}")
        print(f"lenses: {', '.join(report['lenses'])}")
        print(f"findings: {report['finding_count']}")
        print(f"peak_severity: {report['peak_severity']}")
        print(f"action: {report['action']}")
        for item in report["findings"]:
            print(f"- [{item['severity']}/{item['lens']}] {item['title']} ({item['file_path']})")
    # Non-zero only when high findings survive — gate-friendly signal.
    return 1 if report["peak_severity"] == "high" and report["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
