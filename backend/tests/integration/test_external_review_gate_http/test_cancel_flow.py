"""ExternalReviewGate HTTP API 結合テスト — キャンセルフロー (TC-IT-ERG-HTTP-020~024, 028).

Covers:
  TC-IT-ERG-HTTP-020  PENDING gate, 正しい reviewer, reason="" → 200, CANCELLED
  TC-IT-ERG-HTTP-021  Unknown gate → 404
  TC-IT-ERG-HTTP-022  Wrong reviewer → 403
  TC-IT-ERG-HTTP-023  APPROVED gate (already decided), cancel → 409
  TC-IT-ERG-HTTP-024  No Authorization header → 422
  TC-IT-ERG-HTTP-028  POST /api/gates/invalid-not-uuid/cancel + valid Bearer → 422

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


class TestCancelGateSuccess:
    """TC-IT-ERG-HTTP-020: 正常キャンセルフロー (reason="" は有効)."""

    async def test_cancel_returns_200(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 200

    async def test_cancel_decision_is_cancelled(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["decision"] == "CANCELLED"


class TestCancelGateNotFound:
    """TC-IT-ERG-HTTP-021: 存在しない gate → 404."""

    async def test_unknown_gate_returns_404(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 404


class TestCancelGateWrongReviewer:
    """TC-IT-ERG-HTTP-022: 異なる reviewer_id → 403."""

    async def test_wrong_reviewer_returns_403(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        assert resp.status_code == 403


class TestCancelGateAlreadyDecided:
    """TC-IT-ERG-HTTP-023: APPROVED gate に cancel → 409."""

    async def test_already_approved_returns_409(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 409


class TestCancelGateNoAuthHeader:
    """TC-IT-ERG-HTTP-024: Authorization ヘッダーなし → 422."""

    async def test_no_auth_header_returns_422(self, gate_ctx: GateTestCtx) -> None:
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/cancel",
            json={"reason": ""},
        )
        assert resp.status_code == 422


class TestCancelGateInvalidPathUuid:
    """TC-IT-ERG-HTTP-028: 不正 UUID パスパラメータ + valid Bearer → 422."""

    async def test_invalid_path_uuid_returns_422(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            "/api/gates/invalid-not-uuid/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 422

    async def test_invalid_path_uuid_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            "/api/gates/invalid-not-uuid/cancel",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "validation_error"
