"""Fail-closed contracts for strategy research loops.

The loop may propose and evaluate experiments, but it cannot place orders or
promote a strategy beyond human-reviewed paper eligibility.  Criteria are
declared before execution so failed experiments become reusable evidence
rather than prompts for moving the goalposts.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from typing import Callable, Iterable

from .validation import ValidationGate, ValidationReport


ROBUST_SCORE_FORMULA = "return - 2*max_drawdown"


class LoopDecision(str, Enum):
    KILL = "kill"
    REVISE = "revise"
    PAPER_REVIEW = "paper_review"


@dataclass(frozen=True)
class ExperimentContract:
    experiment_id: str
    hypothesis: str
    candidates: tuple[str, ...]
    benchmarks: tuple[str, ...]
    datasets: tuple[str, ...]
    held_out_split: str
    seeds: tuple[int, ...]
    max_trials: int
    score_formula: str = ROBUST_SCORE_FORMULA
    target: str = "research"
    maker: str = "research-agent"

    def validate(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")
        if not self.hypothesis.strip():
            raise ValueError("hypothesis must be declared before the run")
        if len(set(self.candidates)) != len(self.candidates) or not self.candidates:
            raise ValueError("candidates must be non-empty and unique")
        if "cash" not in self.benchmarks:
            raise ValueError("cash benchmark is required")
        if not self.datasets or not all(item.strip() for item in self.datasets):
            raise ValueError("at least one named real-market dataset is required")
        if not self.held_out_split.strip():
            raise ValueError("held-out split must be declared before the run")
        if len(set(self.seeds)) < 3:
            raise ValueError("at least three distinct seeds are required")
        if self.max_trials < 1:
            raise ValueError("max_trials must be a positive circuit breaker")
        if self.score_formula != ROBUST_SCORE_FORMULA:
            raise ValueError(f"score_formula must be {ROBUST_SCORE_FORMULA!r}")
        if self.target not in {"research", "paper"}:
            raise ValueError("loop target may only be research or paper")
        if not self.maker.strip() or "\n" in self.maker:
            raise ValueError("maker is required and must be one line")


@dataclass(frozen=True)
class LoopVerdict:
    decision: LoopDecision
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentMemoryRecord:
    sequence: int
    recorded_at: str
    experiment_id: str
    contract: dict
    code_hash: str
    data_hashes: dict[str, str]
    result: dict | None
    verdict: dict | None
    previous_hash: str | None
    record_hash: str


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: str | Path) -> str:
    """Hash one input artifact without loading it entirely into memory."""
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_paths(paths: Iterable[str | Path]) -> str:
    """Hash named files deterministically, including paths and contents."""
    normalized = sorted(Path(path) for path in paths)
    if not normalized:
        raise ValueError("at least one code path is required")
    digest = sha256()
    for path in normalized:
        if not path.is_file():
            raise ValueError(f"hash input is not a file: {path}")
        encoded = path.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def _canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class ExperimentMemory:
    """Append-only, hash-chained JSONL memory for research evidence."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read_verified(self) -> tuple[ExperimentMemoryRecord, ...]:
        if not self.path.exists():
            return ()
        records = []
        previous_hash = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    raise ValueError(f"blank memory record at line {line_number}")
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid memory JSON at line {line_number}") from exc
                supplied_hash = payload.pop("record_hash", None)
                expected_hash = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
                if supplied_hash != expected_hash:
                    raise ValueError(f"memory hash mismatch at line {line_number}")
                if payload.get("sequence") != line_number:
                    raise ValueError(f"memory sequence mismatch at line {line_number}")
                if payload.get("previous_hash") != previous_hash:
                    raise ValueError(f"memory chain mismatch at line {line_number}")
                for label, value in (("code_hash", payload.get("code_hash")),
                                     *payload.get("data_hashes", {}).items()):
                    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                        raise ValueError(f"invalid SHA-256 for {label} at line {line_number}")
                payload["record_hash"] = supplied_hash
                records.append(ExperimentMemoryRecord(**payload))
                previous_hash = supplied_hash
        return tuple(records)

    def append(self, contract: ExperimentContract, *, code_hash: str,
               data_hashes: dict[str, str], result: dict | None = None,
               verdict: LoopVerdict | None = None,
               recorded_at: str | None = None) -> ExperimentMemoryRecord:
        contract.validate()
        if not _SHA256_RE.fullmatch(code_hash):
            raise ValueError("code_hash must be a lowercase SHA-256 hex digest")
        if not data_hashes:
            raise ValueError("at least one data hash is required")
        for name, digest in data_hashes.items():
            if not name.strip() or not _SHA256_RE.fullmatch(digest):
                raise ValueError("data hashes need non-empty names and SHA-256 digests")

        existing = self.read_verified()
        if any(record.experiment_id == contract.experiment_id for record in existing):
            raise ValueError(f"experiment_id already recorded: {contract.experiment_id}")
        payload = {
            "sequence": len(existing) + 1,
            "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
            "experiment_id": contract.experiment_id,
            "contract": asdict(contract),
            "code_hash": code_hash,
            "data_hashes": dict(sorted(data_hashes.items())),
            "result": result,
            "verdict": None if verdict is None else {
                "decision": verdict.decision.value,
                "reasons": list(verdict.reasons),
            },
            "previous_hash": existing[-1].record_hash if existing else None,
        }
        payload["record_hash"] = sha256(
            _canonical_json(payload).encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return ExperimentMemoryRecord(**payload)


class PaperReviewDecision(str, Enum):
    APPROVED_FOR_PAPER = "approved_for_paper"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PaperReviewRecord:
    sequence: int
    reviewed_at: str
    experiment_id: str
    experiment_record_hash: str
    maker: str
    reviewer: str
    decision: str
    rationale: str
    previous_hash: str | None
    record_hash: str


class PaperReviewLedger:
    """Independent, hash-chained decisions for paper eligibility only."""

    def __init__(self, path: str | Path, experiment_memory: ExperimentMemory):
        self.path = Path(path)
        self.experiment_memory = experiment_memory

    def read_verified(self) -> tuple[PaperReviewRecord, ...]:
        if not self.path.exists():
            return ()
        experiments = {item.experiment_id: item
                       for item in self.experiment_memory.read_verified()}
        records = []
        previous_hash = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid paper review JSON at line {line_number}") from exc
                supplied_hash = payload.pop("record_hash", None)
                expected_hash = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
                if supplied_hash != expected_hash:
                    raise ValueError(f"paper review hash mismatch at line {line_number}")
                if payload.get("sequence") != line_number:
                    raise ValueError(f"paper review sequence mismatch at line {line_number}")
                if payload.get("previous_hash") != previous_hash:
                    raise ValueError(f"paper review chain mismatch at line {line_number}")
                if payload.get("decision") not in {item.value for item in PaperReviewDecision}:
                    raise ValueError(f"invalid paper review decision at line {line_number}")
                if str(payload.get("maker", "")).casefold() == str(
                        payload.get("reviewer", "")).casefold():
                    raise ValueError(f"paper review independence failed at line {line_number}")
                if not _SHA256_RE.fullmatch(str(payload.get("experiment_record_hash", ""))):
                    raise ValueError(f"invalid experiment hash at line {line_number}")
                payload["record_hash"] = supplied_hash
                record = PaperReviewRecord(**payload)
                experiment = experiments.get(record.experiment_id)
                if experiment is None or experiment.record_hash != record.experiment_record_hash:
                    raise ValueError(f"paper review experiment binding failed at line {line_number}")
                if (experiment.verdict or {}).get("decision") != LoopDecision.PAPER_REVIEW.value:
                    raise ValueError(f"paper review eligibility failed at line {line_number}")
                if str(experiment.contract.get("maker", "")) != record.maker:
                    raise ValueError(f"paper review maker binding failed at line {line_number}")
                records.append(record)
                previous_hash = supplied_hash
        return tuple(records)

    def submit(self, experiment_id: str, *, reviewer: str,
               decision: PaperReviewDecision, rationale: str,
               reviewed_at: str | None = None) -> PaperReviewRecord:
        if not isinstance(decision, PaperReviewDecision):
            raise ValueError("decision must be approved_for_paper or rejected")
        if not reviewer.strip() or "\n" in reviewer:
            raise ValueError("reviewer is required and must be one line")
        if not rationale.strip():
            raise ValueError("paper review rationale is required")
        experiments = self.experiment_memory.read_verified()
        experiment = next((item for item in experiments
                           if item.experiment_id == experiment_id), None)
        if experiment is None:
            raise ValueError(f"unknown experiment_id: {experiment_id}")
        if (experiment.verdict or {}).get("decision") != LoopDecision.PAPER_REVIEW.value:
            raise ValueError("only paper_review experiments may receive a decision")
        maker = str(experiment.contract.get("maker", "")).strip()
        if not maker:
            raise ValueError("experiment has no declared maker")
        if maker.casefold() == reviewer.strip().casefold():
            raise PermissionError("maker cannot review their own experiment")

        existing = self.read_verified()
        if any(item.experiment_id == experiment_id for item in existing):
            raise ValueError(f"paper review already recorded: {experiment_id}")
        payload = {
            "sequence": len(existing) + 1,
            "reviewed_at": reviewed_at or datetime.now(timezone.utc).isoformat(),
            "experiment_id": experiment_id,
            "experiment_record_hash": experiment.record_hash,
            "maker": maker,
            "reviewer": reviewer.strip(),
            "decision": decision.value,
            "rationale": rationale.strip(),
            "previous_hash": existing[-1].record_hash if existing else None,
        }
        payload["record_hash"] = sha256(
            _canonical_json(payload).encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return PaperReviewRecord(**payload)


@dataclass(frozen=True)
class EvaluationEvidence:
    reports: dict[str, ValidationReport]
    candidate_mean_robust_score: float
    trial_count: int


@dataclass(frozen=True)
class ExperimentRunResult:
    contract: ExperimentContract
    evidence: EvaluationEvidence
    verdict: LoopVerdict
    memory_record: ExperimentMemoryRecord


class OneContractResearchRunner:
    """Execute exactly one preregistered research contract and persist evidence."""

    def __init__(self, memory: ExperimentMemory,
                 gate: ValidationGate | None = None):
        self.memory = memory
        self.gate = gate or ValidationGate()

    def run(
        self,
        contract: ExperimentContract,
        *,
        code_paths: Iterable[str | Path],
        dataset_paths: dict[str, str | Path],
        evaluate: Callable[[ExperimentContract], EvaluationEvidence],
        recorded_at: str | None = None,
    ) -> ExperimentRunResult:
        contract.validate()
        if set(dataset_paths) != set(contract.datasets):
            missing = sorted(set(contract.datasets) - set(dataset_paths))
            extra = sorted(set(dataset_paths) - set(contract.datasets))
            raise ValueError(f"dataset paths do not match contract; missing={missing}, extra={extra}")
        code_paths = tuple(code_paths)
        normalized_data_paths = {name: Path(path)
                                 for name, path in dataset_paths.items()}
        code_hash = sha256_paths(code_paths)
        data_hashes = {name: sha256_file(path)
                       for name, path in normalized_data_paths.items()}

        evidence = evaluate(contract)
        if not isinstance(evidence, EvaluationEvidence):
            raise TypeError("evaluate must return EvaluationEvidence")
        if not 1 <= evidence.trial_count <= contract.max_trials:
            raise ValueError("trial_count must be within the preregistered trial budget")

        if sha256_paths(code_paths) != code_hash:
            raise ValueError("code changed during experiment; result not recorded")
        current_data_hashes = {name: sha256_file(path)
                               for name, path in normalized_data_paths.items()}
        if current_data_hashes != data_hashes:
            raise ValueError("dataset changed during experiment; result not recorded")

        verdict = deterministic_verdict(
            contract, evidence.reports, evidence.candidate_mean_robust_score,
            gate=self.gate)
        report_summary = {
            name: {
                "fold_count": len(report.folds),
                "median_test_score": report.median_test_score,
                "selection_failure_rate": report.selection_failure_rate,
            }
            for name, report in sorted(evidence.reports.items())
        }
        result = {
            "candidate_mean_robust_score": evidence.candidate_mean_robust_score,
            "trial_count": evidence.trial_count,
            "validation_reports": report_summary,
        }
        memory_record = self.memory.append(
            contract, code_hash=code_hash, data_hashes=data_hashes,
            result=result, verdict=verdict, recorded_at=recorded_at)
        return ExperimentRunResult(contract, evidence, verdict, memory_record)


@dataclass(frozen=True)
class DriftPolicy:
    min_sample_count: int = 30
    robust_score_drop: float = 0.02
    max_drawdown_increase: float = 0.02
    execution_cost_increase_bps: float = 5.0
    max_data_gap_rate: float = 0.01

    def validate(self) -> None:
        if self.min_sample_count < 1:
            raise ValueError("min_sample_count must be positive")
        values = (self.robust_score_drop, self.max_drawdown_increase,
                  self.execution_cost_increase_bps, self.max_data_gap_rate)
        if not all(math.isfinite(value) and value >= 0 for value in values):
            raise ValueError("drift thresholds must be finite and non-negative")
        if self.max_data_gap_rate > 1:
            raise ValueError("max_data_gap_rate must be at most 1")


@dataclass(frozen=True)
class DriftSnapshot:
    dataset: str
    observed_at: str
    sample_count: int
    robust_score: float
    max_drawdown: float
    execution_cost_bps: float
    data_gap_rate: float

    def validate(self) -> None:
        if not self.dataset.strip() or not self.observed_at.strip():
            raise ValueError("drift snapshot needs dataset and observed_at")
        if self.sample_count < 1:
            raise ValueError("sample_count must be positive")
        values = (self.robust_score, self.max_drawdown,
                  self.execution_cost_bps, self.data_gap_rate)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("drift metrics must be finite")
        if self.max_drawdown < 0 or self.execution_cost_bps < 0:
            raise ValueError("drawdown and execution cost must be non-negative")
        if not 0 <= self.data_gap_rate <= 1:
            raise ValueError("data_gap_rate must be between 0 and 1")


@dataclass(frozen=True)
class ResearchTaskDraft:
    task_id: str
    action: str
    strategy: str
    dataset: str
    observed_at: str
    signals: tuple[str, ...]
    baseline: dict[str, float]
    current: dict[str, float]


class DriftMonitor:
    """Detect degradation and emit research-only task drafts."""

    def __init__(self, policy: DriftPolicy | None = None):
        self.policy = policy or DriftPolicy()
        self.policy.validate()

    def evaluate(self, strategy: str, baseline: DriftSnapshot,
                 current: DriftSnapshot) -> ResearchTaskDraft | None:
        baseline.validate()
        current.validate()
        if not strategy.strip() or "\n" in strategy:
            raise ValueError("strategy name is required and must be one line")
        if baseline.dataset != current.dataset:
            raise ValueError("baseline and current dataset must match")
        if current.sample_count < self.policy.min_sample_count:
            return None

        signals = []
        if baseline.robust_score - current.robust_score >= self.policy.robust_score_drop:
            signals.append("robust_score_drop")
        if current.max_drawdown - baseline.max_drawdown >= self.policy.max_drawdown_increase:
            signals.append("max_drawdown_increase")
        if (current.execution_cost_bps - baseline.execution_cost_bps
                >= self.policy.execution_cost_increase_bps):
            signals.append("execution_cost_increase")
        if current.data_gap_rate >= self.policy.max_data_gap_rate:
            signals.append("data_gap_rate")
        if not signals:
            return None

        identity = _canonical_json({
            "strategy": strategy,
            "dataset": current.dataset,
            "observed_at": current.observed_at,
            "signals": signals,
        })
        task_id = "drift-" + sha256(identity.encode("utf-8")).hexdigest()[:16]
        return ResearchTaskDraft(
            task_id=task_id,
            action="open_research_task",
            strategy=strategy,
            dataset=current.dataset,
            observed_at=current.observed_at,
            signals=tuple(signals),
            baseline={
                "robust_score": baseline.robust_score,
                "max_drawdown": baseline.max_drawdown,
                "execution_cost_bps": baseline.execution_cost_bps,
                "data_gap_rate": baseline.data_gap_rate,
            },
            current={
                "robust_score": current.robust_score,
                "max_drawdown": current.max_drawdown,
                "execution_cost_bps": current.execution_cost_bps,
                "data_gap_rate": current.data_gap_rate,
            },
        )


class DriftResearchQueue:
    """Append-only triage queue; it has no strategy mutation or execution API."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> tuple[ResearchTaskDraft, ...]:
        if not self.path.exists():
            return ()
        tasks = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    payload = json.loads(line)
                    payload["signals"] = tuple(payload["signals"])
                    tasks.append(ResearchTaskDraft(**payload))
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise ValueError(f"invalid drift task at line {line_number}") from exc
        return tuple(tasks)

    def open(self, task: ResearchTaskDraft) -> bool:
        if task.action != "open_research_task":
            raise ValueError("drift queue accepts research-task drafts only")
        existing = self.read()
        if any(item.task_id == task.task_id for item in existing):
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_json(asdict(task)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True


def deterministic_verdict(
    contract: ExperimentContract,
    reports: dict[str, ValidationReport],
    candidate_mean_robust_score: float,
    *,
    gate: ValidationGate | None = None,
) -> LoopVerdict:
    """Return a deterministic research verdict; never a live-trading approval."""
    contract.validate()
    validation_gate = gate or ValidationGate()
    missing = sorted(set(contract.datasets) - set(reports))
    if missing:
        return LoopVerdict(LoopDecision.REVISE,
                           ("missing validation reports: " + ", ".join(missing),))
    failed = sorted(name for name in contract.datasets
                    if not validation_gate.passes(reports[name]))
    reasons = []
    if failed:
        reasons.append("validation gate failed: " + ", ".join(failed))
    if candidate_mean_robust_score <= 0.0:
        reasons.append("candidate does not beat cash on mean robust score")
    if reasons:
        return LoopVerdict(LoopDecision.KILL, tuple(reasons))
    return LoopVerdict(
        LoopDecision.PAPER_REVIEW,
        ("all declared gates passed; independent paper-review approval required",),
    )
