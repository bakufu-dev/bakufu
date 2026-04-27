"""ExternalReviewGate VO + enum tests.

Covers:

* :class:`AuditEntry` VO — frozen, comment NFC-only no-strip,
  occurred_at tz-aware.
* :class:`ReviewDecision` enum — 4 StrEnum values.
* :class:`AuditAction` enum — VIEWED / APPROVED / REJECTED /
  CANCELLED + reserved Phase-2 admin values present.
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.value_objects import (
    AuditAction,
    AuditEntry,
    ReviewDecision,
)
from pydantic import ValidationError

from tests.factories.external_review_gate import (
    is_synthetic,
    make_audit_entry,
)


# ---------------------------------------------------------------------------
# AuditEntry VO
# ---------------------------------------------------------------------------
class TestAuditEntryConstruction:
    """AuditEntry constructs valid + rejects oversize comment."""

    def test_default_audit_entry_constructs(self) -> None:
        """Factory-default AuditEntry has VIEWED action + tz-aware occurred_at."""
        entry = make_audit_entry()
        assert entry.action == AuditAction.VIEWED
        assert entry.occurred_at.tzinfo is not None

    def test_audit_entry_factory_marks_synthetic(self) -> None:
        """Factory output is registered in :func:`is_synthetic`."""
        entry = make_audit_entry()
        assert is_synthetic(entry)

    def test_audit_entry_is_frozen(self) -> None:
        """Direct attribute assignment on AuditEntry is rejected."""
        entry = make_audit_entry()
        with pytest.raises(ValidationError):
            entry.comment = "mutated"  # pyright: ignore[reportAttributeAccessIssue]

    def test_comment_at_max_length_accepted(self) -> None:
        """2000-char comment is at the cap and accepted."""
        comment = "x" * 2000
        entry = make_audit_entry(comment=comment)
        assert len(entry.comment) == 2000

    def test_comment_over_max_length_rejected(self) -> None:
        """2001-char comment exceeds the cap and raises."""
        with pytest.raises(ValidationError):
            make_audit_entry(comment="x" * 2001)

    def test_naive_occurred_at_rejected(self) -> None:
        """``occurred_at`` without a timezone is rejected."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            AuditEntry(
                id=uuid4(),
                actor_id=uuid4(),
                action=AuditAction.VIEWED,
                comment="",
                occurred_at=naive,
            )

    def test_comment_nfc_normalization_no_strip(self) -> None:
        """Comment is NFC-normalized but **not** stripped."""
        raw = "  indented quote\n"
        entry = make_audit_entry(comment=raw)
        # NFC normalization, no strip.
        assert entry.comment == unicodedata.normalize("NFC", raw)
        assert entry.comment.startswith("  ")  # leading whitespace preserved
        assert entry.comment.endswith("\n")  # trailing newline preserved


class TestAuditEntryStructuralEquality:
    """Same-attribute AuditEntry instances are ``==``."""

    def test_same_attributes_compare_equal(self) -> None:
        """Two AuditEntry with identical attrs are ``==``."""
        common_id = uuid4()
        actor = uuid4()
        ts = datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)
        a = make_audit_entry(
            entry_id=common_id,
            actor_id=actor,
            action=AuditAction.APPROVED,
            comment="同意します",
            occurred_at=ts,
        )
        b = make_audit_entry(
            entry_id=common_id,
            actor_id=actor,
            action=AuditAction.APPROVED,
            comment="同意します",
            occurred_at=ts,
        )
        assert a == b


# ---------------------------------------------------------------------------
# ReviewDecision enum (4 values)
# ---------------------------------------------------------------------------
class TestReviewDecisionEnum:
    """ReviewDecision has exactly 4 StrEnum values."""

    def test_four_values(self) -> None:
        """PENDING / APPROVED / REJECTED / CANCELLED — exactly 4."""
        members = list(ReviewDecision)
        assert len(members) == 4

    def test_str_enum_equality(self) -> None:
        """StrEnum members compare equal to their string values."""
        assert ReviewDecision.PENDING == "PENDING"
        assert ReviewDecision.APPROVED == "APPROVED"
        assert ReviewDecision.REJECTED == "REJECTED"
        assert ReviewDecision.CANCELLED == "CANCELLED"


# ---------------------------------------------------------------------------
# AuditAction enum (4 core + reserved Phase-2 values)
# ---------------------------------------------------------------------------
class TestAuditActionEnum:
    """AuditAction has the 4 core states the Gate Aggregate emits."""

    def test_core_actions_present(self) -> None:
        """The 4 core actions are present (VIEWED / APPROVED / REJECTED / CANCELLED)."""
        # Gate aggregate emits exactly these 4 — Phase 2 admin actions
        # may extend the enum; we don't pin a specific count so the
        # test stays stable across enum additions.
        assert AuditAction.VIEWED == "VIEWED"
        assert AuditAction.APPROVED == "APPROVED"
        assert AuditAction.REJECTED == "REJECTED"
        assert AuditAction.CANCELLED == "CANCELLED"

    def test_str_enum_equality(self) -> None:
        """StrEnum members compare equal to their string values."""
        for member in AuditAction:
            assert member.value == str(member)
