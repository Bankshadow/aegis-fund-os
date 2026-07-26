"""Tests for the reflect module.

The interesting cases are the refusals. Reflect exists to record corrections, but the
reason it is safe to have in this repository at all is that it cannot touch the law
files and cannot learn from approval — so those are the properties under test.
"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from agent.reflect import (
    Lesson,
    ProtectedTargetError,
    WeakLessonError,
    append_lesson,
    is_approval,
    is_correction,
    is_protected,
)


def _lesson(**overrides) -> Lesson:
    base = dict(
        trigger="ก่อนบอกผู้ใช้ว่างานพร้อมใช้",
        rule="ตรวจ environment จริงที่ผู้ใช้จะเปิดก่อนเสมอ ไม่ใช่แค่ local",
        evidence="บอกให้เอาลิงก์ไปให้นักเรียน ทั้งที่ทั้ง 3 route ยัง 404 บน production เพราะยังไม่ merge",
        recorded_on=date(2026, 7, 26),
    )
    base.update(overrides)
    return Lesson(**base)


class ProtectedPathTests(unittest.TestCase):
    def test_laws_criteria_and_gate_are_protected(self):
        for path in (
            "CLAUDE.md",
            "AGENTS.md",
            "docs/AOT_VALIDATION_CRITERIA.md",
            "docs/VALIDATION_LOG.md",
            "gate/verify.ps1",
            "gate/eval_gate.py",
            "fund-command-center-local/experiments/E29.json",
        ):
            self.assertTrue(is_protected(path), path)

    def test_ordinary_docs_are_writable(self):
        self.assertFalse(is_protected("docs/AGENT_LESSONS.md"))
        self.assertFalse(is_protected("STATE.md"))

    def test_backslashes_and_dot_prefix_do_not_evade_protection(self):
        self.assertTrue(is_protected("gate\\verify.ps1"))
        self.assertTrue(is_protected("./docs/VALIDATION_LOG.md"))

    def test_append_refuses_protected_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProtectedTargetError):
                append_lesson(Path(tmp), _lesson(), target="docs/AOT_VALIDATION_CRITERIA.md")


class SignalTests(unittest.TestCase):
    def test_approval_is_not_a_learning_signal(self):
        # Thai acknowledgement especially: the session that motivated this module had
        # the user answer "ได้" to nearly every proposal, including a mistaken one.
        for text in ("ได้", "โอเค", "ok", "Yes", "that's perfect", "works great"):
            self.assertTrue(is_approval(text), text)
            self.assertFalse(is_correction(text), text)

    def test_explicit_corrections_are_signals(self):
        for text in (
            "No, don't use that, use the shared function",
            "instead of computing per request you should precompute",
            "actually the deploy only runs on main",
            "never lower the gate criteria",
            "ยังไม่โอเค",
            "ไม่ใช่แบบนั้น",
        ):
            self.assertTrue(is_correction(text), text)


class AppendTests(unittest.TestCase):
    def test_append_creates_document_and_records_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(append_lesson(root, _lesson()))
            text = (root / "docs/AGENT_LESSONS.md").read_text(encoding="utf-8")
            self.assertIn("ก่อนบอกผู้ใช้ว่างานพร้อมใช้", text)
            self.assertIn("หลักฐาน", text)
            self.assertIn("2026-07-26", text)

    def test_duplicate_trigger_is_not_appended_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(append_lesson(root, _lesson()))
            self.assertFalse(append_lesson(root, _lesson()))

    def test_praise_is_rejected_as_a_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WeakLessonError):
                append_lesson(Path(tmp), _lesson(rule="perfect", trigger="ได้"))

    def test_lesson_without_real_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WeakLessonError):
                append_lesson(Path(tmp), _lesson(evidence="n/a"))


if __name__ == "__main__":
    unittest.main()
