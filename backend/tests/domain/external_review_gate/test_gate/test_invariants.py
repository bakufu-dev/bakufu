"""ExternalReviewGate invariant + auto-mask + Next: hint tests.

TC-UT-GT-007 / 008 / 009 / 010 / 011 / 021〜025 — the 5
``_validate_*`` helpers (4 used by the model_validator + 1 safety net),
the §確定 H webhook auto-mask, and the §確定 J / room §確定 I 踏襲
**Next: hint physical guarantee** across all 5 MSG-GT-001〜005.

The §確定 C **audit_trail append-only** contract is the highest-stakes
one: 4 改ざんパターン (existing edit / prepend / delete / reorder) all
must raise ``audit_trail_append_only``. The §確定 D
**deliverable_snapshot triple-defense** is also exercised here at the
validator-safety-net level (the structural guard — _rebuild_with_state
not accepting a snapshot arg — is verified in test_state_machine via
"failed approve does not change snapshot").
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.aggregate_validators import (
    MAX_FEEDBACK_LENGTH,
    _validate_audit_trail_append_only,  # pyright: ignore[reportPrivateUsage]
    _validate_decided_at_consistency,  # pyright: ignore[reportPrivateUsage]
    _validate_feedback_text_range,  # pyright: ignore[reportPrivateUsage]
    _validate_snapshot_immutable,  # pyright: ignore[reportPrivateUsage]
)
from bakufu.domain.value_objects import (
    AuditAction,
    ReviewDecision,
)

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_audit_entry,
    make_gate,
)
from tests.factories.task import make_deliverable


# ---------------------------------------------------------------------------
# TC-UT-GT-007: decided_at consistency
# ---------------------------------------------------------------------------
class TestDecidedAtConsistency:
    """TC-UT-GT-007: decision==PENDING ⇔ decided_at is None (MSG-GT-002)."""

    def test_pending_with_decided_at_raises(self) -> None:
        """PENDING + decided_at set → raises."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_decided_at_consistency(ReviewDecision.PENDING, datetime.now(UTC))
        assert exc_info.value.kind == "decided_at_inconsistent"

    def test_approved_with_none_decided_at_raises(self) -> None:
        """APPROVED + decided_at None → raises."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_decided_at_consistency(ReviewDecision.APPROVED, None)
        assert exc_info.value.kind == "decided_at_inconsistent"

    def test_pending_with_none_passes(self) -> None:
        """The legal pairing — PENDING + None — is accepted."""
        _validate_decided_at_consistency(ReviewDecision.PENDING, None)

    @pytest.mark.parametrize(
        "decision",
        [ReviewDecision.APPROVED, ReviewDecision.REJECTED, ReviewDecision.CANCELLED],
        ids=lambda d: d.value,
    )
    def test_terminal_with_decided_at_passes(self, decision: ReviewDecision) -> None:
        """Terminal decisions + non-None decided_at are legal."""
        _validate_decided_at_consistency(decision, datetime.now(UTC))


# ---------------------------------------------------------------------------
# TC-UT-GT-010: feedback_text range
# ---------------------------------------------------------------------------
class TestFeedbackTextRange:
    """TC-UT-GT-010: 0 <= len <= 10000 (MSG-GT-004)."""

    def test_empty_string_passes(self) -> None:
        """Empty feedback (default) is legal."""
        _validate_feedback_text_range("")

    def test_at_max_length_passes(self) -> None:
        """10000 chars is the cap and accepted."""
        _validate_feedback_text_range("x" * MAX_FEEDBACK_LENGTH)

    def test_over_max_length_raises(self) -> None:
        """10001 chars exceeds the cap."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_feedback_text_range("x" * (MAX_FEEDBACK_LENGTH + 1))
        assert exc_info.value.kind == "feedback_text_range"


# ---------------------------------------------------------------------------
# TC-UT-GT-009: audit_trail append-only — 4 改ざんパターン
# ---------------------------------------------------------------------------
class TestAuditTrailAppendOnly:
    """TC-UT-GT-009: 4 改ざんパターン (§確定 C inputs/expectations table).

    Every modification to the audit_trail beyond a strict
    "append at the end" pattern raises ``audit_trail_append_only``.
    The 4 cases enumerated in the design doc:

    1. **modification**: existing entry's content edited.
    2. **prepend**: a new entry inserted before existing ones.
    3. **delete**: an existing entry removed.
    4. **reorder**: existing entries shuffled.
    """

    def test_construction_with_no_previous_accepts_any_list(self) -> None:
        """``previous=None`` (construction) is permissive — pins the initial trail."""
        # Any non-None list is accepted at construction time.
        _validate_audit_trail_append_only(None, [])
        _validate_audit_trail_append_only(None, [make_audit_entry(action=AuditAction.VIEWED)])

    def test_legal_append_passes(self) -> None:
        """Strict append (previous + 1 new entry) is the only legal mutation."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1]
        current = [e1, e2]
        _validate_audit_trail_append_only(previous, current)

    # 改ざんパターン 1: modification
    def test_existing_entry_modification_raises(self) -> None:
        """Editing an existing entry's content is rejected."""
        e1 = make_audit_entry(action=AuditAction.VIEWED, comment="original")
        previous = [e1]
        # Replace e1 with a different entry (different uuid + comment) —
        # this represents the case where someone tries to "fix a typo"
        # in an existing audit entry.
        e1_modified = make_audit_entry(
            action=AuditAction.VIEWED,
            comment="rewritten",
        )
        current = [e1_modified]
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 改ざんパターン 2: prepend
    def test_prepend_raises(self) -> None:
        """Inserting a new entry at the head pushes existing entries — rejected."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        previous = [e1]
        e_prepended = make_audit_entry(action=AuditAction.APPROVED)
        current = [e_prepended, e1]
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 改ざんパターン 3: delete
    def test_delete_raises(self) -> None:
        """Removing an existing entry shrinks the trail — rejected."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1, e2]
        current = [e1]  # e2 dropped
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 改ざんパターン 4: reorder
    def test_reorder_raises(self) -> None:
        """Swapping the order of existing entries is rejected."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1, e2]
        current = [e2, e1]  # swapped
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # Composite: deletion-then-append (still illegal because the head is corrupted)
    def test_delete_then_append_raises(self) -> None:
        """Deleting an existing entry while appending a new one is still illegal."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1, e2]
        e_new = make_audit_entry(action=AuditAction.VIEWED)
        current = [e1, e_new]  # e2 dropped, e_new appended (but length matches)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"


# ---------------------------------------------------------------------------
# TC-UT-GT-008: deliverable_snapshot immutability validator (§確定 D safety net)
# ---------------------------------------------------------------------------
class TestSnapshotImmutableValidator:
    """TC-UT-GT-008: validator safety net for §確定 D snapshot immutability.

    The structural guard is the absence of ``deliverable_snapshot``
    in ``_rebuild_with_state``'s argument set. This validator is the
    failure-path safety net if that contract ever leaks. We test it
    directly here.
    """

    def test_construction_with_no_previous_accepts_any_snapshot(self) -> None:
        """``previous=None`` is permissive — pins the initial snapshot."""
        _validate_snapshot_immutable(None, make_deliverable())

    def test_same_snapshot_passes(self) -> None:
        """Equal snapshots round-trip cleanly (Pydantic frozen ``==``)."""
        d = make_deliverable()
        # Reuse the same instance — Pydantic frozen models compare by value.
        _validate_snapshot_immutable(d, d)

    def test_different_snapshot_raises(self) -> None:
        """A different snapshot at rebuild raises ``snapshot_immutable``."""
        d1 = make_deliverable(body_markdown="original")
        d2 = make_deliverable(body_markdown="replaced")
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_snapshot_immutable(d1, d2)
        assert exc_info.value.kind == "snapshot_immutable"


# ---------------------------------------------------------------------------
# §確定 D triple-defense behavioural confirmation
# ---------------------------------------------------------------------------
class TestSnapshotImmutableViaBehaviors:
    """§確定 D: the 4 behavior methods all preserve deliverable_snapshot byte-for-byte.

    This is the **structural guarantee** test — we walk all 4 methods
    on a Gate and confirm the snapshot field is byte-identical
    afterwards. Even though the validator catches any leak, having
    each method tested independently catches the case where one
    method accidentally accepts a snapshot kwarg in a refactor.
    """

    def test_approve_preserves_snapshot(self) -> None:
        """``approve`` keeps deliverable_snapshot byte-equal."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.approve(uuid4(), "ok", decided_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot

    def test_reject_preserves_snapshot(self) -> None:
        """``reject`` keeps deliverable_snapshot byte-equal."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.reject(uuid4(), "rev", decided_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot

    def test_cancel_preserves_snapshot(self) -> None:
        """``cancel`` keeps deliverable_snapshot byte-equal."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.cancel(uuid4(), "withdrawn", decided_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot

    def test_record_view_preserves_snapshot(self) -> None:
        """``record_view`` keeps deliverable_snapshot byte-equal."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.record_view(uuid4(), viewed_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot


# ---------------------------------------------------------------------------
# TC-UT-GT-011: ExternalReviewGateInvariantViolation auto-mask (§確定 H)
# ---------------------------------------------------------------------------
class TestExceptionAutoMasksDiscordWebhooks:
    """TC-UT-GT-011: webhook URLs in feedback / detail get masked at construction.

    The §確定 H contract is on
    ``ExternalReviewGateInvariantViolation.__init__`` — auto-mask
    fires for every kind / detail shape, not for any specific
    validator. We construct the exception directly with secret-bearing
    payloads and assert the redaction sentinel replaces the raw token
    in both ``message`` and ``detail`` (recursively).
    """

    _SECRET = "https://discord.com/api/webhooks/123456789012345678/SneakyToken-xyz"
    _REDACT_SENTINEL = "<REDACTED:DISCORD_WEBHOOK>"
    _RAW_TOKEN = "SneakyToken-xyz"

    def test_webhook_redacted_in_message_and_detail(self) -> None:
        """Both message and recursive detail values lose the raw token."""
        exc = ExternalReviewGateInvariantViolation(
            kind="audit_trail_append_only",
            message=f"[FAIL] secret in message: {self._SECRET}\nNext: re-input.",
            detail={
                "feedback_value": self._SECRET,
                "nested": {"target": self._SECRET},
                "as_list": [self._SECRET, "ok"],
            },
        )

        # Message: raw token absent, sentinel present.
        assert self._RAW_TOKEN not in exc.message
        assert self._REDACT_SENTINEL in exc.message
        # Detail: every nested value masked.
        flat = repr(exc.detail)
        assert self._RAW_TOKEN not in flat
        assert self._REDACT_SENTINEL in flat


# ---------------------------------------------------------------------------
# TC-UT-GT-021〜025: 5 MSG kinds + Next: hint physical guarantee (§確定 J)
# ---------------------------------------------------------------------------
class TestNextHintPhysicalGuarantee:
    """All 5 ``ExternalReviewGateViolationKind`` values carry 'Next:' in str(exc).

    The room §確定 I 踏襲 contract: every error message has a 2-line
    structure (``[FAIL] <fact>\\nNext: <action>``). A failing assertion
    on ``"Next:" in str(exc)`` means a developer wrote a one-line
    MSG and the operator-feedback contract is broken.
    """

    def test_decision_already_decided_carries_next_hint(self) -> None:
        """TC-UT-GT-021: MSG-GT-001 (decision_already_decided)."""
        gate = make_approved_gate()
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            gate.approve(uuid4(), "double", decided_at=datetime.now(UTC) + timedelta(seconds=1))
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "decided once" in s

    def test_decided_at_inconsistent_carries_next_hint(self) -> None:
        """TC-UT-GT-022: MSG-GT-002 (decided_at_inconsistent)."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_decided_at_consistency(ReviewDecision.APPROVED, None)
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Repository row integrity" in s

    def test_snapshot_immutable_carries_next_hint(self) -> None:
        """TC-UT-GT-023: MSG-GT-003 (snapshot_immutable)."""
        d1 = make_deliverable(body_markdown="a")
        d2 = make_deliverable(body_markdown="b")
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_snapshot_immutable(d1, d2)
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "frozen at Gate creation" in s

    def test_feedback_text_range_carries_next_hint(self) -> None:
        """TC-UT-GT-024: MSG-GT-004 (feedback_text_range)."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_feedback_text_range("x" * (MAX_FEEDBACK_LENGTH + 1))
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Trim" in s

    def test_audit_trail_append_only_carries_next_hint(self) -> None:
        """TC-UT-GT-025: MSG-GT-005 (audit_trail_append_only)."""
        e1 = make_audit_entry()
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only([e1], [])  # delete pattern
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "append" in s.lower()


# ---------------------------------------------------------------------------
# Composite: a Gate that walks the full lifecycle preserves audit chain
# ---------------------------------------------------------------------------
class TestAuditTrailChainIntegrity:
    """Walking a full lifecycle keeps every previous entry byte-equal."""

    def test_lifecycle_preserves_all_previous_entries(self) -> None:
        """record_view x 2 → approve preserves the 2 VIEWED entries verbatim."""
        gate = make_gate()
        v1 = uuid4()
        v2 = uuid4()
        ts1 = datetime(2026, 4, 28, 10, 0, 0, tzinfo=UTC)
        ts2 = ts1 + timedelta(hours=1)
        ts3 = ts2 + timedelta(hours=1)

        gate = gate.record_view(v1, viewed_at=ts1)
        gate = gate.record_view(v2, viewed_at=ts2)
        # Snapshot the audit trail at this point.
        before_approve = copy.copy(gate.audit_trail)
        assert len(before_approve) == 2

        # Approve.
        gate = gate.approve(uuid4(), "all good", decided_at=ts3)

        # The first 2 entries must be byte-equal (the §確定 C contract);
        # the third entry is the new APPROVED audit row.
        assert gate.audit_trail[:2] == before_approve
        assert gate.audit_trail[2].action == AuditAction.APPROVED
        assert len(gate.audit_trail) == 3
