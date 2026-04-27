"""Unit tests for workflow VOs (CompletionPolicy / NotifyChannel / Transition).

Covers TC-UT-VO-WF-001〜004 from ``docs/features/workflow/test-design.md``.
Tests are grouped into ``Test*`` classes by VO surface so failures cluster by
contract.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.value_objects import CompletionPolicy, TransitionCondition
from bakufu.domain.workflow import Transition
from pydantic import ValidationError

from tests.factories.workflow import (
    DEFAULT_DISCORD_WEBHOOK,
    is_synthetic,
    make_completion_policy,
    make_notify_channel,
)


class TestCompletionPolicy:
    """CompletionPolicy contract (TC-UT-VO-WF-001 / 002)."""

    @pytest.mark.parametrize(
        "kind",
        ["approved_by_reviewer", "all_checklist_checked", "manual"],
    )
    def test_accepts_each_canonical_kind(self, kind: str) -> None:
        """TC-UT-VO-WF-001: every Literal kind constructs successfully."""
        policy = make_completion_policy(kind=kind, description="ok")
        assert policy.kind == kind

    def test_rejects_unknown_kind(self) -> None:
        """TC-UT-VO-WF-002: kind='unknown' raises ValidationError."""
        with pytest.raises(ValidationError):
            CompletionPolicy.model_validate({"kind": "unknown", "description": ""})


class TestNotifyChannelHappyPath:
    """NotifyChannel constructs with a valid Discord webhook URL (TC-UT-VO-WF-003)."""

    def test_construction_with_default_webhook_succeeds(self) -> None:
        """TC-UT-VO-WF-003: NotifyChannel(kind='discord', target=valid) constructs."""
        channel = make_notify_channel()
        assert channel.target == DEFAULT_DISCORD_WEBHOOK

    def test_factory_built_channel_is_synthetic(self) -> None:
        """Factory-built NotifyChannel is registered in the synthetic registry."""
        channel = make_notify_channel()
        assert is_synthetic(channel) is True


class TestTransitionStructuralEquality:
    """Two Transitions with identical fields compare equal (TC-UT-VO-WF-004)."""

    def test_two_transitions_with_identical_fields_compare_equal(self) -> None:
        """TC-UT-VO-WF-004: Transition is structurally equal when all fields match."""
        tid = uuid4()
        from_id = uuid4()
        to_id = uuid4()
        a = Transition(
            id=tid,
            from_stage_id=from_id,
            to_stage_id=to_id,
            condition=TransitionCondition.APPROVED,
        )
        b = Transition(
            id=tid,
            from_stage_id=from_id,
            to_stage_id=to_id,
            condition=TransitionCondition.APPROVED,
        )
        assert a == b
