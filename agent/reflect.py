"""Reflect — turn user corrections into durable, reviewable lessons.

Adapted from the idea behind haddock-development/claude-reflect-system (capture
correction signals from a session and write them into a file the agent reads next
time), with two of its mechanisms deliberately removed because they are unsafe in
this repository.

WHAT WAS KEPT
    Explicit corrections are the highest-value artefact a session produces and the
    thing most reliably lost. Writing them down, dated and with evidence, is worth
    doing.

WHAT WAS REMOVED, AND WHY
    1. Approval / praise signals ("perfect", "works great", "yes"). The upstream
       system treats these as MEDIUM-confidence endorsements and promotes the
       preceding behaviour into a best-practices section. In this repository that
       inverts the truth. In the session that motivated this module the user replied
       "ได้" (yes/ok) to almost every proposal, including the one where the agent
       said the lab was ready for students while it was in fact returning 404 in
       production. Harvesting that as an endorsement would have recorded a mistake
       as a validated pattern. Acknowledgement is not endorsement, and outcomes here
       are decided by the gate, never by tone of reply.

    2. Automatic, unattended writes (the upstream stop-hook / auto mode). Every
       lesson here needs a human in the loop, for the same reason the ValidationGate
       exists: nothing self-certifies.

WHAT WAS ADDED
    A protected-path list. This project's integrity rests on rules that must not be
    adaptable: criteria are frozen before a run, the gate is never softened, tests
    are never edited to pass. A component that rewrites rule files from
    conversational signal is precisely the thing that would erode that, so it is
    barred from writing to them at all. Lessons land in one append-only document.

This module only records. It changes no behaviour on its own and runs no experiment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Files encoding the project's laws, its frozen experiment criteria, or its evidence
# record. Reflect must never write here; changing any of these is a deliberate human
# act, not something derived from how a conversation went.
PROTECTED_PATHS = frozenset(
    {
        "CLAUDE.md",
        "AGENTS.md",
        "ROUTING.md",
        "docs/AOT_VALIDATION_CRITERIA.md",
        "docs/VALIDATION_LOG.md",
        "gate/verify.ps1",
        "gate/verify.sh",
        "gate/eval_gate.py",
    }
)

PROTECTED_PREFIXES = ("gate/", "experiments/", "fund-command-center-local/experiments/")

LESSONS_DOC = "docs/AGENT_LESSONS.md"

# Praise and acknowledgement, in English and Thai. Matching text is explicitly NOT a
# learning signal — see the module docstring. Kept as data so the decision is
# testable rather than merely documented.
_APPROVAL_PATTERNS = (
    r"(?i)\b(perfect|exactly right|great job|nice work|works? (perfectly|great|well))\b",
    r"(?i)^\s*(yes|yep|ok|okay|sure)\b",
    r"^\s*(ได้|โอเค|ครับ|ค่ะ|ดีแล้ว|เยี่ยม)\s*$",
)

# Explicit corrections and standing directives — the signals worth keeping.
_CORRECTION_PATTERNS = (
    r"(?i)\bno,?\s+(don't|do not|use|it's)\b",
    r"(?i)\b(instead of|rather than)\b.+\b(use|do|should)\b",
    r"(?i)\bactually,?\b",
    r"(?i)\b(never|always)\s+\w+",
    r"(ไม่ใช่|ผิด|ยังไม่โอเค|ห้าม|ต้อง)\b",
)


class ProtectedTargetError(RuntimeError):
    """Raised when reflect is asked to write into a law, criteria or gate file."""


class WeakLessonError(ValueError):
    """Raised when a candidate lesson is praise, or lacks evidence."""


def is_protected(path: str) -> bool:
    """True if `path` (repo-relative, forward slashes) must never be written by reflect."""
    normalised = path.replace("\\", "/").lstrip("./")
    if normalised in PROTECTED_PATHS:
        return True
    return any(normalised.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def is_approval(text: str) -> bool:
    """True if `text` is praise or acknowledgement, which is never a learning signal."""
    return any(re.search(pattern, text) for pattern in _APPROVAL_PATTERNS)


def is_correction(text: str) -> bool:
    """True if `text` looks like an explicit correction or a standing directive."""
    if is_approval(text):
        return False
    return any(re.search(pattern, text) for pattern in _CORRECTION_PATTERNS)


@dataclass(frozen=True)
class Lesson:
    """One durable lesson.

    `trigger` is the situation it applies to, `rule` is what to do, and `evidence` is
    what actually happened that justifies it. Evidence is mandatory: a rule with no
    incident behind it is a preference, and this project already has enough of those
    written down.
    """

    trigger: str
    rule: str
    evidence: str
    recorded_on: date

    def to_markdown(self) -> str:
        return (
            f"### {self.trigger}\n\n"
            f"- **กฎ:** {self.rule}\n"
            f"- **หลักฐาน:** {self.evidence}\n"
            f"- **บันทึกเมื่อ:** {self.recorded_on.isoformat()}\n"
        )


def validate_lesson(lesson: Lesson) -> None:
    """Reject lessons that are praise, or too thin to act on later."""
    if is_approval(lesson.rule) or is_approval(lesson.trigger):
        raise WeakLessonError("approval/praise is not a lesson — see module docstring")
    for field_name in ("trigger", "rule", "evidence"):
        value = getattr(lesson, field_name).strip()
        if len(value) < 12:
            raise WeakLessonError(f"{field_name} is too thin to be actionable: {value!r}")


def lesson_exists(document: str, lesson: Lesson) -> bool:
    """True if a lesson with the same trigger heading is already recorded."""
    return f"### {lesson.trigger}" in document


def append_lesson(repo_root: Path, lesson: Lesson, target: str = LESSONS_DOC) -> bool:
    """Append `lesson` to the lessons document.

    Returns False if an identical trigger is already recorded. Raises if the target is
    a protected file, or if the lesson does not hold up on its own.
    """
    if is_protected(target):
        raise ProtectedTargetError(
            f"refusing to write into {target}: laws, frozen criteria and the gate are not learnable"
        )
    validate_lesson(lesson)

    path = repo_root / target
    document = path.read_text(encoding="utf-8") if path.exists() else _new_document()
    if lesson_exists(document, lesson):
        return False

    if not document.endswith("\n"):
        document += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document + "\n" + lesson.to_markdown(), encoding="utf-8")
    return True


def _new_document() -> str:
    return (
        "# Agent Lessons — บทเรียนจากการถูกแก้\n\n"
        "> บันทึกเฉพาะ **การแก้ที่ผู้ใช้บอกตรง ๆ** พร้อมหลักฐานว่าเกิดอะไรขึ้นจริง\n"
        "> คำชมหรือการตอบรับ (\"ได้\", \"โอเค\", \"perfect\") **ไม่ถูกบันทึก** — การตอบรับ\n"
        "> ไม่เท่ากับการรับรองว่าถูก และผลลัพธ์ในโปรเจกต์นี้ตัดสินด้วย gate เท่านั้น\n"
        ">\n"
        "> ไฟล์กฎ (`CLAUDE.md`, `AGENTS.md`), เกณฑ์ที่ประกาศแล้ว\n"
        "> (`docs/AOT_VALIDATION_CRITERIA.md`), สมุดหลักฐาน (`docs/VALIDATION_LOG.md`)\n"
        "> และ `gate/` **ห้ามแก้จากที่นี่** — ดู `agent/reflect.py`\n"
    )
