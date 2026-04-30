"""ExternalReviewGate HTTP API 結合テスト — 差し戻しフロー (TC-IT-ERG-HTTP-014~019, 027).

Covers:
  TC-IT-ERG-HTTP-014  PENDING gate, 正しい reviewer, feedback_text="要修正" → 200, REJECTED
  TC-IT-ERG-HTTP-015  feedback_text="" → 422, code="validation_error"
  TC-IT-ERG-HTTP-016  Wrong reviewer → 403
  TC-IT-ERG-HTTP-017  APPROVED gate, reject → 409
  TC-IT-ERG-HTTP-018  No Authorization header → 422
  TC-IT-ERG-HTTP-019  Unknown gate → 404
  TC-IT-ERG-HTTP-027  POST /api/gates/invalid-not-uuid/reject + valid Bearer + valid body → 422

Issue: #61
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_gate,
)
from tests.integration.test_external_review_gate_http.conftest import (
    GateTestCtx,
    seed_gate_with_deps,
)

pytestmark = pytest.mark.asyncio


class TestRejectGateSuccess:
    """TC-IT-ERG-HTTP-014: 正常差し戻しフロー."""

    async def test_reject_returns_200(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 200

    async def test_reject_decision_is_rejected(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["decision"] == "REJECTED"

    async def test_reject_feedback_text_is_preserved(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["feedback_text"] == "要修正"


class TestRejectGateEmptyFeedback:
    """TC-IT-ERG-HTTP-015: feedback_text="" → 422 (Pydantic min_length=1)."""

    async def test_empty_feedback_text_returns_422(self, gate_ctx: GateTestCtx) -> None:
        # Pydantic バリデーションは DB lookup より前に行われるため gate の seed 不要。
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/reject",
            json={"feedback_text": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 422

    async def test_empty_feedback_text_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/reject",
            json={"feedback_text": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "validation_error"


class TestRejectGateWrongReviewer:
    """TC-IT-ERG-HTTP-016: 異なる reviewer_id → 403."""

    async def test_wrong_reviewer_returns_403(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        assert resp.status_code == 403


class TestRejectGateAlreadyDecided:
    """TC-IT-ERG-HTTP-017: APPROVED gate に reject → 409."""

    async def test_already_approved_returns_409(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 409


class TestRejectGateNoAuthHeader:
    """TC-IT-ERG-HTTP-018: Authorization ヘッダーなし → 422."""

    async def test_no_auth_header_returns_422(self, gate_ctx: GateTestCtx) -> None:
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/reject",
            json={"feedback_text": "要修正"},
        )
        assert resp.status_code == 422


class TestRejectGateNotFound:
    """TC-IT-ERG-HTTP-019: 存在しない gate → 404."""

    async def test_unknown_gate_returns_404(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 404


class TestRejectGateInvalidPathUuid:
    """TC-IT-ERG-HTTP-027: 不正 UUID パスパラメータ + valid Bearer + valid body → 422."""

    async def test_invalid_path_uuid_returns_422(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            "/api/gates/invalid-not-uuid/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 422

    async def test_invalid_path_uuid_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            "/api/gates/invalid-not-uuid/reject",
            json={"feedback_text": "要修正"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "validation_error"
