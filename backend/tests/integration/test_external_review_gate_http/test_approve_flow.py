"""ExternalReviewGate HTTP API 結合テスト — 承認フロー (TC-IT-ERG-HTTP-008~013, 026, 029, 031, 032).

Covers:
  TC-IT-ERG-HTTP-008  PENDING gate, 正しい reviewer, comment="LGTM" → 200, APPROVED
  TC-IT-ERG-HTTP-009  Unknown gate → approve → 404, code="not_found"
  TC-IT-ERG-HTTP-010  No Authorization header → 422 (http_error_422)
  TC-IT-ERG-HTTP-011  Wrong reviewer_id → 403, code="forbidden"
  TC-IT-ERG-HTTP-012  APPROVED gate (already decided), same reviewer → 409, code="conflict"
  TC-IT-ERG-HTTP-013  Authorization: Bearer not-a-uuid → 422
  TC-IT-ERG-HTTP-026  POST /api/gates/invalid-not-uuid/approve + valid Bearer → 422
  TC-IT-ERG-HTTP-029  APPROVED gate, approve again → 409 MSG 確認
  TC-IT-ERG-HTTP-031  PENDING gate, wrong reviewer → 403 MSG 確認
  TC-IT-ERG-HTTP-032  No auth header → 422 MSG 確認

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


class TestApproveGateSuccess:
    """TC-IT-ERG-HTTP-008: 正常承認フロー."""

    async def test_approve_returns_200(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 200

    async def test_approve_decision_is_approved(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["decision"] == "APPROVED"

    async def test_approve_decided_at_is_not_none(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["decided_at"] is not None

    async def test_approve_audit_trail_has_approved_entry(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        audit_trail = resp.json()["audit_trail"]
        assert len(audit_trail) == 1
        assert audit_trail[0]["action"] == "APPROVED"


class TestApproveGateNotFound:
    """TC-IT-ERG-HTTP-009: 存在しない gate → 404."""

    async def test_unknown_gate_returns_404(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 404

    async def test_unknown_gate_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "not_found"


class TestApproveGateNoAuthHeader:
    """TC-IT-ERG-HTTP-010: Authorization ヘッダーなし → 422."""

    async def test_no_auth_header_returns_422(self, gate_ctx: GateTestCtx) -> None:
        # Authorization ヘッダーの検証は gate lookup より前に行われるため、
        # gate を DB にシードする必要はない。
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
        )
        assert resp.status_code == 422

    async def test_no_auth_header_error_code(self, gate_ctx: GateTestCtx) -> None:
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
        )
        assert resp.json()["error"]["code"] == "http_error_422"


class TestApproveGateWrongReviewer:
    """TC-IT-ERG-HTTP-011: 異なる reviewer_id → 403."""

    async def test_wrong_reviewer_returns_403(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        assert resp.status_code == 403

    async def test_wrong_reviewer_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "forbidden"


class TestApproveGateAlreadyDecided:
    """TC-IT-ERG-HTTP-012: 既に APPROVED な gate に approve → 409."""

    async def test_already_approved_returns_409(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 409

    async def test_already_approved_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "conflict"


class TestApproveGateInvalidBearerToken:
    """TC-IT-ERG-HTTP-013: Bearer トークンが UUID でない → 422."""

    async def test_invalid_bearer_returns_422(self, gate_ctx: GateTestCtx) -> None:
        # Bearer 検証はリクエストデコード時に行われるため、gate は不要。
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": "Bearer not-a-uuid"},
        )
        assert resp.status_code == 422


class TestApproveGateInvalidPathUuid:
    """TC-IT-ERG-HTTP-026: 不正 UUID パスパラメータ + valid Bearer → 422."""

    async def test_invalid_path_uuid_returns_422(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            "/api/gates/invalid-not-uuid/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.status_code == 422

    async def test_invalid_path_uuid_error_code(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        resp = await gate_ctx.client.post(
            "/api/gates/invalid-not-uuid/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        assert resp.json()["error"]["code"] == "validation_error"


class TestApproveGateAlreadyDecidedMessage:
    """TC-IT-ERG-HTTP-029: R1-G MSG-002 — 409 レスポンスの文言確認."""

    async def test_already_decided_message_has_fail_prefix(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        message = resp.json()["error"]["message"]
        assert "[FAIL]" in message

    async def test_already_decided_message_has_finalized(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        message = resp.json()["error"]["message"]
        assert "Gate decision is already finalized" in message

    async def test_already_decided_message_has_next(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {reviewer_id}"},
        )
        message = resp.json()["error"]["message"]
        assert "Next:" in message


class TestApproveGateWrongReviewerMessage:
    """TC-IT-ERG-HTTP-031: R1-G MSG-003 — 403 レスポンスの文言確認."""

    async def test_forbidden_message_has_fail_prefix(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        message = resp.json()["error"]["message"]
        assert "[FAIL]" in message

    async def test_forbidden_message_has_not_authorized(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        message = resp.json()["error"]["message"]
        assert "Not authorized" in message

    async def test_forbidden_message_has_next(self, gate_ctx: GateTestCtx) -> None:
        reviewer_id = uuid4()
        wrong_reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.post(
            f"/api/gates/{gate.id}/approve",
            json={"comment": "LGTM"},
            headers={"Authorization": f"Bearer {wrong_reviewer_id}"},
        )
        message = resp.json()["error"]["message"]
        assert "Next:" in message


class TestApproveGateNoAuthMessage:
    """TC-IT-ERG-HTTP-032: R1-G MSG-004 — 422 no-auth レスポンスの文言確認."""

    async def test_no_auth_message_has_fail_prefix(self, gate_ctx: GateTestCtx) -> None:
        # Authorization ヘッダー検証は gate lookup より前に行われる。
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
        )
        message = resp.json()["error"]["message"]
        assert "[FAIL]" in message

    async def test_no_auth_message_has_authorization(self, gate_ctx: GateTestCtx) -> None:
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
        )
        message = resp.json()["error"]["message"]
        assert "Authorization" in message

    async def test_no_auth_message_has_next(self, gate_ctx: GateTestCtx) -> None:
        resp = await gate_ctx.client.post(
            f"/api/gates/{uuid4()}/approve",
            json={"comment": "LGTM"},
        )
        message = resp.json()["error"]["message"]
        assert "Next:" in message
