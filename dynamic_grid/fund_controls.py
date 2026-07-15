"""MVP governance guardrails: RBAC, audit events, and fail-closed permissions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Role(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"


class Operation(str, Enum):
    VIEW_REPORT = "view_report"
    SYNC_READ_ONLY = "sync_read_only"
    CLOSE_REPORT = "close_report"
    MANAGE_CREDENTIAL_REFERENCE = "manage_credential_reference"
    PLACE_ORDER = "place_order"


_ALLOWED = {
    Role.VIEWER: {Operation.VIEW_REPORT},
    Role.OPERATOR: {Operation.VIEW_REPORT, Operation.SYNC_READ_ONLY},
    Role.APPROVER: {Operation.VIEW_REPORT, Operation.CLOSE_REPORT},
    Role.ADMIN: {Operation.VIEW_REPORT, Operation.SYNC_READ_ONLY,
                 Operation.CLOSE_REPORT, Operation.MANAGE_CREDENTIAL_REFERENCE},
}


@dataclass(frozen=True)
class AuditEvent:
    occurred_at: datetime
    actor_id: str
    operation: Operation
    outcome: str
    detail: str


@dataclass
class AccessController:
    audit_events: list[AuditEvent] = field(default_factory=list)

    def authorize(self, actor_id: str, role: Role, operation: Operation) -> None:
        allowed = operation is not Operation.PLACE_ORDER and operation in _ALLOWED[role]
        self.audit_events.append(AuditEvent(datetime.now(timezone.utc), actor_id, operation,
                                            "allowed" if allowed else "denied", "MVP policy"))
        if not allowed:
            raise PermissionError(f"{role.value} may not perform {operation.value}")
