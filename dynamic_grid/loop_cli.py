"""Command-line export of a verified, read-only Loop lineage snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .loop_engineering import DriftResearchQueue, ExperimentMemory, PaperReviewLedger
from .loop_snapshot import build_loop_snapshot, write_loop_snapshot


def export_loop_snapshot(
    *,
    memory_path: str | Path,
    drift_queue_path: str | Path,
    review_ledger_path: str | Path,
    output_path: str | Path,
) -> dict:
    """Verify every source before atomically replacing the output snapshot."""
    memory = ExperimentMemory(memory_path)
    drift_queue = DriftResearchQueue(drift_queue_path)
    review_ledger = PaperReviewLedger(review_ledger_path, memory)
    snapshot = build_loop_snapshot(
        memory=memory,
        drift_queue=drift_queue,
        review_ledger=review_ledger,
    )
    write_loop_snapshot(snapshot, output_path)
    return snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Loop evidence and export a read-only Aegis snapshot."
    )
    parser.add_argument("--memory", required=True, help="Experiment memory JSONL path")
    parser.add_argument("--drift-queue", required=True, help="Drift queue JSONL path")
    parser.add_argument("--review-ledger", required=True, help="Paper review JSONL path")
    parser.add_argument("--output", required=True, help="Snapshot JSON output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = export_loop_snapshot(
        memory_path=args.memory,
        drift_queue_path=args.drift_queue,
        review_ledger_path=args.review_ledger,
        output_path=args.output,
    )
    print(
        "verified Loop snapshot exported: "
        f"experiments={snapshot['summary']['experimentCount']} "
        f"drift_tasks={snapshot['summary']['openDriftTaskCount']} "
        f"output={Path(args.output)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
