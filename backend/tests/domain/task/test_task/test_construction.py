"""Task construction tests (TC-UT-TS-001 / 002 / 014 / 040 / 044 / 045 / 053).

Per ``docs/features/task/test-design.md`` §Task 構築. Covers
construction defaults, the 6 ``TaskStatus`` rehydration cases, frozen
+ structural equality, NFC-without-strip ``last_error`` normalization
(§確定 C), frozen-instance assignment rejection, ``extra='forbid'``,
and the type-error class for fields that bypass the kind enum
(§確定 J).
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.task import Task
from bakufu.domain.value_objects import TaskStatus
from pydantic import ValidationError

from tests.factories.task import (
    is_synthetic,
    make_awaiting_review_task,
    make_blocked_task,
    make_cancelled_task,
    make_done_task,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# TC-UT-TS-001: default-valued construction
# ---------------------------------------------------------------------------
class TestTaskDefaults:
    """TC-UT-TS-001: factory default Task is structurally PENDING + empty."""

    def test_default_task_is_pending_with_empty_state(self) -> None:
        """Defaults: status=PENDING, assigned=[], deliverables={}, last_error=None."""
        task = make_task()
        assert task.status == TaskStatus.PENDING
        assert task.assigned_agent_ids == []
        assert task.deliverables == {}
        assert task.last_error is None
        assert task.created_at <= task.updated_at

    def test_factory_marks_instance_synthetic(self) -> None:
        """Factory output is registered in :func:`is_synthetic`."""
        task = make_task()
        assert is_synthetic(task)


# ---------------------------------------------------------------------------
# TC-UT-TS-002: rehydration into all 6 TaskStatus values
# ---------------------------------------------------------------------------
class TestRehydrateAllStatuses:
    """TC-UT-TS-002: each of the 6 TaskStatus values constructs cleanly.

    Repository hydration must be able to land any persisted status —
    BLOCKED needs ``last_error``, every other status needs
    ``last_error is None``.
    """

    def test_pending_constructs(self) -> None:
        assert make_task(status=TaskStatus.PENDING).status == TaskStatus.PENDING

    def test_in_progress_constructs(self) -> None:
        assert make_in_progress_task().status == TaskStatus.IN_PROGRESS

    def test_awaiting_external_review_constructs(self) -> None:
        assert make_awaiting_review_task().status == TaskStatus.AWAITING_EXTERNAL_REVIEW

    def test_blocked_requires_last_error(self) -> None:
        task = make_blocked_task(last_error="some failure")
        assert task.status == TaskStatus.BLOCKED
        assert task.last_error == "some failure"

    def test_done_constructs(self) -> None:
        assert make_done_task().status == TaskStatus.DONE

    def test_cancelled_constructs(self) -> None:
        assert make_cancelled_task().status == TaskStatus.CANCELLED


# ---------------------------------------------------------------------------
# TC-UT-TS-014: frozen + structural equality + hash
# ---------------------------------------------------------------------------
class TestFrozenStructuralEquality:
    """TC-UT-TS-014: same-attributes Tasks are ``==`` and hashable identically."""

    def test_same_attributes_compare_equal(self) -> None:
        """Two Task instances with identical attrs are ``==``."""
        common_id = uuid4()
        common_room = uuid4()
        common_directive = uuid4()
        common_stage = uuid4()
        ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        a = make_task(
            task_id=common_id,
            room_id=common_room,
            directive_id=common_directive,
            current_stage_id=common_stage,
            created_at=ts,
            updated_at=ts,
        )
        b = make_task(
            task_id=common_id,
            room_id=common_room,
            directive_id=common_directive,
            current_stage_id=common_stage,
            created_at=ts,
            updated_at=ts,
        )
        assert a == b


# ---------------------------------------------------------------------------
# TC-UT-TS-040: NFC-without-strip on last_error (§確定 C)
# ---------------------------------------------------------------------------
class TestLastErrorNormalization:
    """TC-UT-TS-040: ``last_error`` is NFC-normalized but **not** stripped.

    LLM stack traces rely on leading whitespace for indentation;
    stripping would silently corrupt the diagnostic. The §確定 C
    contract is "NFC normalize, never strip".
    """

    def test_leading_and_trailing_whitespace_preserved(self) -> None:
        """Newlines + leading/trailing spaces survive normalization."""
        raw = "AuthExpired:\n  at line 1\n  at line 2\n"
        task = make_blocked_task(last_error=raw)
        # The post-validator is mode='before', so it runs before
        # field type checks. The value should round-trip through NFC
        # but keep every leading-/trailing-whitespace character.
        assert task.last_error is not None
        assert task.last_error == unicodedata.normalize("NFC", raw)
        assert task.last_error.startswith("AuthExpired:")
        assert task.last_error.endswith("\n")
        assert "  at line 1" in task.last_error  # leading space kept

    def test_decomposed_form_normalizes_to_composed_form(self) -> None:
        """A composed-form characte equals its decomposed counterpart after NFC."""
        composed = "café: error"  # NFC-composed (é = U+00E9)
        decomposed = "café: error"  # NFC-decomposed (e + COMBINING ACCENT)
        task_composed = make_blocked_task(last_error=composed)
        task_decomposed = make_blocked_task(last_error=decomposed)
        # Both forms normalize to the same NFC string, so the field
        # values match byte-for-byte.
        assert task_composed.last_error == task_decomposed.last_error


# ---------------------------------------------------------------------------
# TC-UT-TS-044: frozen instance — direct attribute assignment rejected
# ---------------------------------------------------------------------------
class TestFrozenInstance:
    """TC-UT-TS-044: ``task.<attr> = value`` raises on a frozen Pydantic model."""

    def test_status_assignment_rejected(self) -> None:
        """Direct ``task.status = ...`` is rejected by Pydantic frozen."""
        task = make_task()
        with pytest.raises(ValidationError):
            task.status = TaskStatus.IN_PROGRESS  # pyright: ignore[reportAttributeAccessIssue]

    def test_assigned_agents_assignment_rejected(self) -> None:
        """Direct ``task.assigned_agent_ids = ...`` is rejected."""
        task = make_task()
        with pytest.raises(ValidationError):
            task.assigned_agent_ids = [uuid4()]  # pyright: ignore[reportAttributeAccessIssue]

    def test_last_error_assignment_rejected(self) -> None:
        """Direct ``task.last_error = ...`` is rejected."""
        task = make_blocked_task()
        with pytest.raises(ValidationError):
            task.last_error = "new"  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# TC-UT-TS-045: extra='forbid' rejects unknown fields
# ---------------------------------------------------------------------------
class TestExtraForbid:
    """TC-UT-TS-045: an unknown field at construction time is rejected."""

    def test_unknown_field_rejected_via_model_validate(self) -> None:
        """``Task.model_validate({..., 'unknown': 'x'})`` raises ValidationError."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Task.model_validate(
                {
                    "id": uuid4(),
                    "room_id": uuid4(),
                    "directive_id": uuid4(),
                    "current_stage_id": uuid4(),
                    "created_at": now,
                    "updated_at": now,
                    "unknown_field": "should-be-rejected",
                }
            )


# ---------------------------------------------------------------------------
# TC-UT-TS-053: type errors land as pydantic.ValidationError (§確定 J)
# ---------------------------------------------------------------------------
class TestTypeErrorsRaisePydanticValidationError:
    """TC-UT-TS-053: type-shaped failures use ``pydantic.ValidationError`` (no kind concept).

    The §確定 J contract: structural / field-type errors are pure
    Pydantic validation errors; only the 7 ``TaskInvariantViolation``
    kinds are issued by the aggregate's invariants. Tests pin this
    so a hypothetical refactor that wrapped pydantic errors in a
    custom exception would force a docs revisit.
    """

    def test_naive_datetime_rejected(self) -> None:
        """``created_at`` without a timezone must be rejected."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            make_task(created_at=naive)

    def test_unknown_status_string_rejected(self) -> None:
        """A non-enum status string is rejected by the Pydantic enum coercion."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Task.model_validate(
                {
                    "id": uuid4(),
                    "room_id": uuid4(),
                    "directive_id": uuid4(),
                    "current_stage_id": uuid4(),
                    "status": "UNKNOWN_STATUS_VALUE",
                    "created_at": now,
                    "updated_at": now,
                }
            )

    def test_non_uuid_id_rejected(self) -> None:
        """A malformed UUID-shaped string for ``id`` is rejected."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Task.model_validate(
                {
                    "id": "not-a-uuid",
                    "room_id": uuid4(),
                    "directive_id": uuid4(),
                    "current_stage_id": uuid4(),
                    "created_at": now,
                    "updated_at": now,
                }
            )


# ---------------------------------------------------------------------------
# Smoke: created_at > updated_at via factory raises (covered also by invariants)
# ---------------------------------------------------------------------------
class TestTimestampOrderSmoke:
    """A construction-time timestamp violation surfaces immediately."""

    def test_created_after_updated_rejected_at_construction(self) -> None:
        """``created_at > updated_at`` raises ``TaskInvariantViolation``."""
        from bakufu.domain.exceptions import TaskInvariantViolation

        ts_old = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
        ts_new = ts_old - timedelta(seconds=1)
        with pytest.raises(TaskInvariantViolation):
            make_task(created_at=ts_old, updated_at=ts_new)
