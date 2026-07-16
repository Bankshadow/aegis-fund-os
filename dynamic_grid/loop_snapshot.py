"""Versioned read-only projection of Loop Engineering lineage for Aegis."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .loop_engineering import (DriftResearchQueue, ExperimentMemory,
                               PaperReviewLedger, sha256_file)


LOOP_SNAPSHOT_SCHEMA_VERSION = 1


def build_loop_snapshot(
    *,
    memory: ExperimentMemory,
    drift_queue: DriftResearchQueue,
    review_ledger: PaperReviewLedger | None = None,
    generated_at: str | None = None,
) -> dict:
    """Verify sources and return a UI-safe, mutation-free lineage projection."""
    records = memory.read_verified()
    drift_tasks = drift_queue.read()
    reviews = review_ledger.read_verified() if review_ledger is not None else ()
    review_by_experiment = {item.experiment_id: item for item in reviews}
    verdict_counts = {"kill": 0, "revise": 0, "paper_review": 0,
                      "unresolved": 0}
    experiments = []
    for record in reversed(records):
        decision = (record.verdict or {}).get("decision", "unresolved")
        verdict_counts[decision] = verdict_counts.get(decision, 0) + 1
        result = record.result or {}
        review = review_by_experiment.get(record.experiment_id)
        experiments.append({
            "sequence": record.sequence,
            "experimentId": record.experiment_id,
            "recordedAt": record.recorded_at,
            "hypothesis": record.contract.get("hypothesis", ""),
            "maker": record.contract.get("maker", ""),
            "target": record.contract.get("target", "research"),
            "candidates": list(record.contract.get("candidates", ())),
            "benchmarks": list(record.contract.get("benchmarks", ())),
            "datasets": list(record.contract.get("datasets", ())),
            "heldOutSplit": record.contract.get("held_out_split", ""),
            "seedCount": len(record.contract.get("seeds", ())),
            "maxTrials": record.contract.get("max_trials"),
            "trialCount": result.get("trial_count"),
            "meanRobustScore": result.get("candidate_mean_robust_score"),
            "validationReports": result.get("validation_reports", {}),
            "decision": decision,
            "reasons": list((record.verdict or {}).get("reasons", ())),
            "codeHash": record.code_hash,
            "dataHashes": dict(record.data_hashes),
            "recordHash": record.record_hash,
            "previousHash": record.previous_hash,
            "paperReview": None if review is None else {
                "reviewedAt": review.reviewed_at,
                "experimentRecordHash": review.experiment_record_hash,
                "maker": review.maker,
                "reviewer": review.reviewer,
                "decision": review.decision,
                "rationale": review.rationale,
                "recordHash": review.record_hash,
            },
        })

    task_items = [
        {
            "taskId": task.task_id,
            "action": task.action,
            "strategy": task.strategy,
            "dataset": task.dataset,
            "observedAt": task.observed_at,
            "signals": list(task.signals),
            "baseline": dict(task.baseline),
            "current": dict(task.current),
        }
        for task in reversed(drift_tasks)
    ]
    return {
        "schemaVersion": LOOP_SNAPSHOT_SCHEMA_VERSION,
        "source": "verified_loop_lineage",
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "readOnly": True,
        "integrity": {
            "experimentChain": "verified",
            "experimentRecordCount": len(records),
            "memoryFileHash": sha256_file(memory.path) if memory.path.exists() else None,
            "driftQueueRecordCount": len(drift_tasks),
            "driftQueueFileHash": (sha256_file(drift_queue.path)
                                   if drift_queue.path.exists() else None),
            "reviewChain": "verified" if review_ledger is not None else "unconfigured",
            "reviewRecordCount": len(reviews),
            "reviewFileHash": (sha256_file(review_ledger.path)
                               if review_ledger is not None and review_ledger.path.exists()
                               else None),
        },
        "summary": {
            "experimentCount": len(records),
            "openDriftTaskCount": len(drift_tasks),
            "verdictCounts": verdict_counts,
            "reviewCounts": {
                "approved_for_paper": sum(
                    item.decision == "approved_for_paper" for item in reviews),
                "rejected": sum(item.decision == "rejected" for item in reviews),
                "pending": sum(
                    (record.verdict or {}).get("decision") == "paper_review"
                    and record.experiment_id not in review_by_experiment
                    for record in records),
            },
        },
        "experiments": experiments,
        "driftTasks": task_items,
        "capabilities": {
            "canMutateStrategy": False,
            "canApprovePaper": False,
            "canPlaceOrder": False,
        },
    }


def write_loop_snapshot(snapshot: dict, path: str | Path) -> None:
    """Atomically replace a generated snapshot; readers never see partial JSON."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                            prefix=f".{target.name}.", delete=False) as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2, sort_keys=True,
                  allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(target)
