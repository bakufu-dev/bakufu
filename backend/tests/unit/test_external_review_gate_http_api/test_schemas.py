"""ExternalReviewGate HTTP API schema unit tests.

Covers:
  TC-UT-ERG-HTTP-001, TC-UT-ERG-HTTP-002, TC-UT-ERG-HTTP-005,
  TC-UT-ERG-HTTP-008

Issue: #61
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestExternalReviewGateResponseSchema:
    def test_response_model_converts_value_objects_to_strings(self) -> None:
        """TC-UT-ERG-HTTP-001: Gate factory 由来 VO を HTTP 文字列表現へ変換する。"""
        from bakufu.interfaces.http.schemas.external_review_gate import ExternalReviewGateResponse

        from tests.factories.external_review_gate import make_gate

        gate = make_gate()

        response = ExternalReviewGateResponse.model_validate(gate)

        assert response.id == str(gate.id)
        assert response.task_id == str(gate.task_id)
        assert response.stage_id == str(gate.stage_id)
        assert response.reviewer_id == str(gate.reviewer_id)
        assert response.decision == "PENDING"

    def test_response_model_does_not_remask_or_unmask_repository_values(self) -> None:
        """TC-UT-ERG-HTTP-002: schema は Repository 復元値をそのまま載せる。"""
        from bakufu.interfaces.http.schemas.external_review_gate import ExternalReviewGateResponse

        from tests.factories.external_review_gate import make_audit_entry, make_gate
        from tests.factories.task import make_deliverable

        gate = make_gate(
            deliverable_snapshot=make_deliverable(body_markdown="<REDACTED:webhook_url>"),
            feedback_text="raw feedback text",
            audit_trail=[make_audit_entry(comment="<REDACTED:token>")],
        )

        response = ExternalReviewGateResponse.model_validate(gate)

        assert response.deliverable_snapshot.body_markdown == "<REDACTED:webhook_url>"
        assert response.feedback_text == "raw feedback text"
        assert response.audit_trail[0].comment == "<REDACTED:token>"


class TestExternalReviewGateRequestSchemas:
    def test_reject_request_rejects_empty_feedback(self) -> None:
        """TC-UT-ERG-HTTP-005: feedback_text='' は validation error。"""
        from bakufu.interfaces.http.schemas.external_review_gate import (
            ExternalReviewGateRejectRequest,
        )

        with pytest.raises(ValidationError):
            ExternalReviewGateRejectRequest(feedback_text="")

    def test_cancel_request_accepts_10000_characters(self) -> None:
        """TC-UT-ERG-HTTP-008: reason 10000 文字は受理する。"""
        from bakufu.interfaces.http.schemas.external_review_gate import (
            ExternalReviewGateCancelRequest,
        )

        request = ExternalReviewGateCancelRequest(reason="x" * 10000)

        assert request.reason == "x" * 10000

    def test_cancel_request_rejects_10001_characters(self) -> None:
        """TC-UT-ERG-HTTP-008: reason 10001 文字は validation error。"""
        from bakufu.interfaces.http.schemas.external_review_gate import (
            ExternalReviewGateCancelRequest,
        )

        with pytest.raises(ValidationError):
            ExternalReviewGateCancelRequest(reason="x" * 10001)

    def test_decision_requests_forbid_actor_id_injection(self) -> None:
        """TC-IT-ERG-HTTP-009補強: actor_id 混入は extra='forbid' で拒否する。"""
        from bakufu.interfaces.http.schemas.external_review_gate import (
            ExternalReviewGateRejectRequest,
        )

        with pytest.raises(ValidationError):
            ExternalReviewGateRejectRequest.model_validate(
                {"feedback_text": "直して", "actor_id": "self-reported"}
            )
