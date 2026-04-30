"""ExternalReviewGateService ユニットテスト (TC-UT-ERG-HTTP-001~005).

Covers:
  TC-UT-ERG-HTTP-001  find_by_id_or_raise → repo returns gate → returns gate
  TC-UT-ERG-HTTP-002  find_by_id_or_raise → repo returns None → raises GateNotFoundError
  TC-UT-ERG-HTTP-003  approve → PENDING gate + correct reviewer_id → returns APPROVED gate
  TC-UT-ERG-HTTP-004  approve → APPROVED gate + same reviewer_id → raises GateAlreadyDecidedError
  TC-UT-ERG-HTTP-005  GateReject schema validation → feedback_text="" → raises ValidationError

Issue: #61
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


class TestFindByIdOrRaise:
    """TC-UT-ERG-HTTP-001/002: find_by_id_or_raise."""

    async def test_returns_gate_when_found(self) -> None:
        """TC-UT-ERG-HTTP-001: repo が gate を返す場合 → そのまま gate を返す."""
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )
        from tests.factories.external_review_gate import make_gate

        gate = make_gate()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=gate)

        service = ExternalReviewGateService(repo=mock_repo)
        result = await service.find_by_id_or_raise(gate.id)

        assert result is gate

    async def test_raises_gate_not_found_error_when_not_found(self) -> None:
        """TC-UT-ERG-HTTP-002: repo が None を返す場合 → GateNotFoundError を raise."""
        from bakufu.application.exceptions.gate_exceptions import GateNotFoundError
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)

        service = ExternalReviewGateService(repo=mock_repo)
        gate_id = uuid4()

        with pytest.raises(GateNotFoundError):
            await service.find_by_id_or_raise(gate_id)


class TestApproveGate:
    """TC-UT-ERG-HTTP-003/004: approve."""

    async def test_approve_pending_gate_with_correct_reviewer(self) -> None:
        """TC-UT-ERG-HTTP-003: PENDING gate + correct reviewer_id → APPROVED gate を返す."""
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )
        from bakufu.domain.value_objects.enums import ReviewDecision
        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        mock_repo = AsyncMock()

        service = ExternalReviewGateService(repo=mock_repo)
        result = await service.approve(
            gate=gate,
            reviewer_id=reviewer_id,
            comment="LGTM",
            decided_at=datetime.now(UTC),
        )

        assert result.decision == ReviewDecision.APPROVED

    async def test_approve_already_approved_gate_raises_already_decided_error(self) -> None:
        """TC-UT-ERG-HTTP-004: APPROVED gate + same reviewer_id → GateAlreadyDecidedError."""
        from bakufu.application.exceptions.gate_exceptions import GateAlreadyDecidedError
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )
        from tests.factories.external_review_gate import make_approved_gate

        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        mock_repo = AsyncMock()

        service = ExternalReviewGateService(repo=mock_repo)

        with pytest.raises(GateAlreadyDecidedError):
            await service.approve(
                gate=gate,
                reviewer_id=reviewer_id,
                comment="LGTM again",
                decided_at=datetime.now(UTC),
            )


class TestGateRejectSchemaValidation:
    """TC-UT-ERG-HTTP-005: GateReject スキーマバリデーション."""

    def test_empty_feedback_text_raises_validation_error(self) -> None:
        """TC-UT-ERG-HTTP-005: feedback_text="" → Pydantic ValidationError (min_length=1)."""
        from pydantic import ValidationError

        from bakufu.interfaces.http.schemas.external_review_gate import GateReject

        with pytest.raises(ValidationError):
            GateReject(feedback_text="")
