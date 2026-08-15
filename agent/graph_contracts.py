"""L2 agent-graph contracts — schemas only, no execution authority.

Firewall: this module must never import fund-command-center, exchange adapters,
or any path that can place orders. It exists so harness work can fan out and
merge with validated shapes while L3 runtime stays deterministic code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


ReviewSeverity = Literal["low", "medium", "high"]
ReviewLens = Literal["correctness", "security", "repro", "performance"]
GraphAction = Literal["quick_pass", "parallel_audit", "judge_panel", "halt_for_human"]


@dataclass(frozen=True)
class ReviewFinding:
    """One bounded review finding — a node output contract."""

    finding_id: str
    title: str
    severity: ReviewSeverity
    lens: ReviewLens
    evidence: str
    file_path: str = ""

    def validate(self) -> None:
        if not self.finding_id.strip():
            raise ValueError("finding_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if self.severity not in {"low", "medium", "high"}:
            raise ValueError("severity must be low|medium|high")
        if self.lens not in {"correctness", "security", "repro", "performance"}:
            raise ValueError("lens must be a known review lens")
        if not self.evidence.strip():
            raise ValueError("evidence is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class NodeContract:
    """Declare one agent-graph node: one job, bounded in/out."""

    name: str
    job: str
    input_keys: tuple[str, ...]
    output_schema: str

    def validate(self) -> None:
        if not self.name.strip() or not self.job.strip():
            raise ValueError("name and job are required")
        if not self.input_keys:
            raise ValueError("input_keys must be non-empty")
        if not self.output_schema.strip():
            raise ValueError("output_schema is required")


@dataclass(frozen=True)
class EdgeContract:
    """An edge exists only when data actually moves."""

    source: str
    target: str
    data_key: str

    def validate(self) -> None:
        if not self.source.strip() or not self.target.strip():
            raise ValueError("source and target are required")
        if not self.data_key.strip():
            raise ValueError("data_key is required — order-only links are not edges")


@dataclass(frozen=True)
class DiamondPlan:
    """Canonical fan-out → reduce → synthesize topology for harness work."""

    plan_id: str
    split_node: str
    work_nodes: tuple[str, ...]
    reduce_is_code: bool
    synthesize_node: str

    def validate(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id is required")
        if not self.split_node.strip() or not self.synthesize_node.strip():
            raise ValueError("split_node and synthesize_node are required")
        if len(self.work_nodes) < 1:
            raise ValueError("work_nodes must include at least one parallel job")
        if not self.reduce_is_code:
            raise ValueError("reduce must be code (zero model tokens on the edge)")
