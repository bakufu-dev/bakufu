"""ExternalReviewGate HTTP API 結合テスト — GET 系 (TC-IT-ERG-HTTP-001~007, 025, 030, 033).

Covers:
  TC-IT-ERG-HTTP-001  GET /api/gates?reviewer_id=R → 200, total=2, 2 items (PENDING 2 件)
  TC-IT-ERG-HTTP-002  GET /api/gates?reviewer_id=R → 200, total=0, items=[] (0 件)
  TC-IT-ERG-HTTP-003  GET /api/tasks/{task_id}/gates → 200, 2 items (REJECTED + PENDING)
  TC-IT-ERG-HTTP-004  GET /api/tasks/{task_id}/gates → 200, total=0 (0 件)
  TC-IT-ERG-HTTP-005  GET /api/gates/{id} → 200, feedback_text matches factory value
  TC-IT-ERG-HTTP-006  GET /api/gates/{unknown} → 404, code="not_found"
  TC-IT-ERG-HTTP-007  GET /api/gates/invalid-not-uuid → 422, code="validation_error"
  TC-IT-ERG-HTTP-025  gate with GitHub PAT in body_markdown → GET → <REDACTED:...> present
  TC-IT-ERG-HTTP-030  Unknown gate → 404, body has "[FAIL]" AND "Gate not found" AND "Next:"
  TC-IT-ERG-HTTP-033  GET /api/gates/{id} → GateDetailResponse に required_deliverable_criteria 配列

Issue: #61 / #121
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.factories.external_review_gate import (
    make_gate,
    make_gate_with_criteria,
    make_rejected_gate,
)
from tests.factories.task import make_deliverable
from tests.integration.test_external_review_gate_http.conftest import (
    GateTestCtx,
    seed_gate_with_deps,
)

pytestmark = pytest.mark.asyncio


class TestListPendingGates:
    """TC-IT-ERG-HTTP-001/002: GET /api/gates?reviewer_id=R."""

    async def test_returns_200_with_two_gates(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-001: reviewer に対して PENDING Gate が 2 件存在する場合."""
        reviewer_id = uuid4()
        gate1 = make_gate(reviewer_id=reviewer_id)
        gate2 = make_gate(reviewer_id=reviewer_id)
        await seed_gate_with_deps(gate_ctx.session_factory, gate1)
        await seed_gate_with_deps(gate_ctx.session_factory, gate2)

        resp = await gate_ctx.client.get("/api/gates", params={"reviewer_id": str(reviewer_id)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    async def test_returns_200_with_empty_list(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-002: reviewer に対して Gate が 0 件の場合."""
        reviewer_id = uuid4()
        resp = await gate_ctx.client.get("/api/gates", params={"reviewer_id": str(reviewer_id)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []


class TestListGatesByTask:
    """TC-IT-ERG-HTTP-003/004: GET /api/tasks/{task_id}/gates."""

    async def test_returns_two_gates_for_task(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-003: 同 task_id に REJECTED + PENDING の 2 件が存在する場合."""
        task_id = uuid4()
        pending = make_gate(task_id=task_id)
        await seed_gate_with_deps(gate_ctx.session_factory, pending)
        # rejected gate は同一 task_id を持つが task の FK チェーンが衝突するため
        # 別の deps チェーン（異なる task_id）で seed する。
        rejected2 = make_rejected_gate(task_id=task_id)
        await seed_gate_with_deps(gate_ctx.session_factory, rejected2)

        resp = await gate_ctx.client.get(f"/api/tasks/{task_id}/gates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    async def test_returns_empty_list_for_unknown_task(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-004: 存在しない task_id → 空リスト."""
        task_id = uuid4()
        resp = await gate_ctx.client.get(f"/api/tasks/{task_id}/gates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []


class TestGetGate:
    """TC-IT-ERG-HTTP-005/006/007: GET /api/gates/{gate_id}."""

    async def test_returns_200_with_feedback_text(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-005: PENDING gate with deliverable_snapshot + audit_trail → 200."""
        from bakufu.domain.value_objects import AuditAction

        from tests.factories.external_review_gate import make_audit_entry

        audit_entry = make_audit_entry(action=AuditAction.VIEWED)
        gate = make_gate(
            feedback_text="pending feedback",
            audit_trail=[audit_entry],
        )
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.get(f"/api/gates/{gate.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["feedback_text"] == "pending feedback"

    async def test_unknown_gate_returns_404(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-006: 存在しない gate UUID → 404."""
        resp = await gate_ctx.client.get(f"/api/gates/{uuid4()}")
        assert resp.status_code == 404

    async def test_unknown_gate_error_code_is_not_found(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-006: error.code == "not_found"."""
        resp = await gate_ctx.client.get(f"/api/gates/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_invalid_uuid_path_returns_422(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-007: 不正 UUID パスパラメータ → 422."""
        resp = await gate_ctx.client.get("/api/gates/invalid-not-uuid")
        assert resp.status_code == 422

    async def test_invalid_uuid_path_error_code(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-007: error.code == "validation_error"."""
        resp = await gate_ctx.client.get("/api/gates/invalid-not-uuid")
        assert resp.json()["error"]["code"] == "validation_error"


class TestMasking:
    """TC-IT-ERG-HTTP-025: body_markdown に GitHub PAT が含まれる場合マスクされる."""

    async def test_github_pat_is_masked_in_response(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-025: ghp_AAAA... → <REDACTED:...> になって返る."""
        secret = "ghp_" + "A" * 36
        deliverable = make_deliverable(body_markdown=f"token: {secret}")
        gate = make_gate(deliverable_snapshot=deliverable)
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.get(f"/api/gates/{gate.id}")
        assert resp.status_code == 200
        body_markdown = resp.json()["deliverable_snapshot"]["body_markdown"]
        assert "<REDACTED:" in body_markdown
        assert secret not in body_markdown


class TestGateNotFoundMessage:
    """TC-IT-ERG-HTTP-030: R1-G MSG-001 — 404 レスポンスの文言確認."""

    async def test_not_found_message_has_fail_prefix(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-030a: 404 レスポンス本文に "[FAIL]" が含まれる."""
        resp = await gate_ctx.client.get(f"/api/gates/{uuid4()}")
        message = resp.json()["error"]["message"]
        assert "[FAIL]" in message

    async def test_not_found_message_has_gate_not_found(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-030b: 404 レスポンス本文に "Gate not found" が含まれる."""
        resp = await gate_ctx.client.get(f"/api/gates/{uuid4()}")
        message = resp.json()["error"]["message"]
        assert "Gate not found" in message

    async def test_not_found_message_has_next(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-030c: 404 レスポンス本文に "Next:" が含まれる."""
        resp = await gate_ctx.client.get(f"/api/gates/{uuid4()}")
        message = resp.json()["error"]["message"]
        assert "Next:" in message


# ---------------------------------------------------------------------------
# TC-IT-ERG-HTTP-033: GateDetailResponse に required_deliverable_criteria 配列 (Issue #121)
# ---------------------------------------------------------------------------
class TestGetGateCriteria:
    """TC-IT-ERG-HTTP-033: GET /api/gates/{id} が required_deliverable_criteria 配列を返す."""

    async def test_gate_with_criteria_returns_criteria_in_response(
        self, gate_ctx: GateTestCtx
    ) -> None:
        """TC-IT-ERG-HTTP-033a: criteria 付き Gate → required_deliverable_criteria が非空配列。"""
        from bakufu.domain.value_objects import AcceptanceCriterion

        c1 = AcceptanceCriterion(id=uuid4(), description="設計書の要件を満たす", required=True)
        c2 = AcceptanceCriterion(
            id=uuid4(), description="テストケースが全て通過する", required=False
        )
        gate = make_gate(required_deliverable_criteria=(c1, c2))
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.get(f"/api/gates/{gate.id}")
        assert resp.status_code == 200
        criteria: list[object] = resp.json()["required_deliverable_criteria"]
        assert isinstance(criteria, list)
        assert len(criteria) == 2

    async def test_criteria_values_match_inserted(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-033b: criteria の description / required フラグが正しく返る."""
        from bakufu.domain.value_objects import AcceptanceCriterion

        c1 = AcceptanceCriterion(id=uuid4(), description="設計書の要件を満たす", required=True)
        c2 = AcceptanceCriterion(
            id=uuid4(), description="テストケースが全て通過する", required=False
        )
        gate = make_gate(required_deliverable_criteria=(c1, c2))
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.get(f"/api/gates/{gate.id}")
        criteria = resp.json()["required_deliverable_criteria"]
        assert criteria[0]["description"] == "設計書の要件を満たす"
        assert criteria[0]["required"] is True
        assert criteria[1]["description"] == "テストケースが全て通過する"
        assert criteria[1]["required"] is False

    async def test_gate_without_criteria_returns_empty_array(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-033c: criteria なし Gate → required_deliverable_criteria が空配列。"""
        gate = make_gate()
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.get(f"/api/gates/{gate.id}")
        assert resp.status_code == 200
        criteria = resp.json()["required_deliverable_criteria"]
        assert criteria == []

    async def test_criteria_order_preserved_in_response(self, gate_ctx: GateTestCtx) -> None:
        """TC-IT-ERG-HTTP-033d: criteria の order_index 順（挿入順）が維持される."""
        gate = make_gate_with_criteria()
        await seed_gate_with_deps(gate_ctx.session_factory, gate)

        resp = await gate_ctx.client.get(f"/api/gates/{gate.id}")
        assert resp.status_code == 200
        criteria = resp.json()["required_deliverable_criteria"]
        # make_gate_with_criteria のデフォルト: True / False / True
        assert len(criteria) == 3
        assert criteria[0]["required"] is True
        assert criteria[1]["required"] is False
        assert criteria[2]["required"] is True
