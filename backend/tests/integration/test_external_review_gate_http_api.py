"""ExternalReviewGate HTTP API integration tests."""

from __future__ import annotations

import ast
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio

_TOKEN = "owner-api-token-32-bytes-minimum-value"
_RAW_SECRET = "GITHUB_PAT=ghp_" + "A" * 36


class ExternalReviewGateHttpCtx:
    """ExternalReviewGate HTTP API integration context."""

    def __init__(
        self,
        client: AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        reviewer_id: UUID,
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.reviewer_id = reviewer_id

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {_TOKEN}"}


@pytest_asyncio.fixture
async def external_review_gate_http_ctx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[ExternalReviewGateHttpCtx]:
    """実 SQLite と実 FastAPI app を配線する。"""
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    reviewer_id = uuid4()
    monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", _TOKEN)
    monkeypatch.setenv("BAKUFU_OWNER_ID", str(reviewer_id))

    app = create_app()
    engine = make_test_engine(tmp_path / "test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ExternalReviewGateHttpCtx(client, session_factory, reviewer_id)

    await engine.dispose()


async def _seed_gate(
    ctx: ExternalReviewGateHttpCtx,
    *,
    reviewer_id: UUID | None = None,
) -> dict[str, str]:
    """Repository 経由で Gate 事前条件を保存する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    from tests.factories.directive import make_directive
    from tests.factories.external_review_gate import make_gate
    from tests.factories.task import make_deliverable, make_task
    from tests.integration.test_room_http_api.helpers import (
        _create_empire,
        _create_room,
        _seed_workflow,
    )

    task_id = uuid4()
    stage_id = uuid4()
    directive_id = uuid4()
    unique_suffix = uuid4().hex[:12]
    empire = await _create_empire(ctx.client, name=f"ERG-{unique_suffix}")
    workflow = await _seed_workflow(ctx.session_factory)
    room = await _create_room(
        ctx.client,
        str(empire["id"]),
        str(workflow.id),  # type: ignore[attr-defined]
        name=f"ERG Room {unique_suffix}",
    )
    directive = make_directive(
        directive_id=directive_id,
        target_room_id=UUID(str(room["id"])),
        task_id=task_id,
    )
    task = make_task(
        task_id=task_id,
        room_id=UUID(str(room["id"])),
        directive_id=directive_id,
        current_stage_id=stage_id,
    )
    gate = make_gate(
        task_id=task_id,
        stage_id=stage_id,
        reviewer_id=reviewer_id or ctx.reviewer_id,
        deliverable_snapshot=make_deliverable(
            stage_id=stage_id,
            body_markdown=_RAW_SECRET,
        ),
    )
    async with ctx.session_factory() as session, session.begin():
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)
        await SqliteExternalReviewGateRepository(session).save(gate)
    return {"gate_id": str(gate.id), "task_id": str(task_id), "stage_id": str(stage_id)}


async def _seed_gate_for_existing_task(
    ctx: ExternalReviewGateHttpCtx,
    *,
    task_id: UUID,
    stage_id: UUID,
    reviewer_id: UUID | None = None,
) -> dict[str, str]:
    """既存 Task に追加 Gate だけを保存する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (  # noqa: E501
        SqliteExternalReviewGateRepository,
    )

    from tests.factories.external_review_gate import make_gate
    from tests.factories.task import make_deliverable

    gate = make_gate(
        task_id=task_id,
        stage_id=stage_id,
        reviewer_id=reviewer_id or ctx.reviewer_id,
        deliverable_snapshot=make_deliverable(
            stage_id=stage_id,
            body_markdown=_RAW_SECRET,
        ),
    )
    async with ctx.session_factory() as session, session.begin():
        await SqliteExternalReviewGateRepository(session).save(gate)
    return {"gate_id": str(gate.id), "task_id": str(task_id), "stage_id": str(stage_id)}


class TestExternalReviewGateHttpApi:
    async def test_list_returns_only_authenticated_reviewer_pending_gates(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-001: reviewer の PENDING 一覧を HTTP だけで観測する。"""
        ctx = external_review_gate_http_ctx
        first = await _seed_gate(ctx)
        task_id = UUID(first["task_id"])
        stage_id = UUID(first["stage_id"])
        second = await _seed_gate_for_existing_task(ctx, task_id=task_id, stage_id=stage_id)
        await _seed_gate_for_existing_task(
            ctx,
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=uuid4(),
        )

        response = await ctx.client.get("/api/gates", headers=ctx.headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 2
        assert {item["id"] for item in body["items"]} == {first["gate_id"], second["gate_id"]}
        assert _RAW_SECRET not in response.text

    async def test_task_history_returns_only_authenticated_reviewer_gates(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-002: Task 履歴は subject の Gate だけを返す。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        response = await ctx.client.get(f"/api/tasks/{ids['task_id']}/gates", headers=ctx.headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == ids["gate_id"]

    async def test_reviewer_flow_uses_public_http_only(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """一覧、詳細閲覧、承認、履歴を HTTP レスポンスだけで観測する。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        listed = await ctx.client.get("/api/gates", headers=ctx.headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == ids["gate_id"]
        assert _RAW_SECRET not in listed.text

        viewed = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert viewed.status_code == 200, viewed.text
        assert _action_names(viewed.json()) == ["VIEWED"]

        approved = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/approve",
            headers=ctx.headers,
            json={"comment": "承認します"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["decision"] == "APPROVED"
        assert _action_names(approved.json()) == ["VIEWED", "APPROVED"]

        history = await ctx.client.get(
            f"/api/tasks/{ids['task_id']}/gates",
            headers=ctx.headers,
        )
        assert history.status_code == 200, history.text
        assert history.json()["total"] == 1
        assert history.json()["items"][0]["decision"] == "APPROVED"

    async def test_reject_flow_exposes_feedback_in_task_history(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-005/012: reject 後の履歴で feedback を観測できる。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        rejected = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/reject",
            headers=ctx.headers,
            json={"feedback_text": "根拠が足りない"},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["decision"] == "REJECTED"
        assert rejected.json()["feedback_text"] == "根拠が足りない"

        history = await ctx.client.get(f"/api/tasks/{ids['task_id']}/gates", headers=ctx.headers)
        assert history.status_code == 200, history.text
        assert history.json()["items"][0]["decision"] == "REJECTED"
        assert history.json()["items"][0]["feedback_text"] == "根拠が足りない"

    async def test_cancel_flow_removes_gate_from_pending_list_and_keeps_history(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-006/013: cancel 後は PENDING 一覧から消え履歴に残る。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        cancelled = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/cancel",
            headers=ctx.headers,
            json={"reason": "レビュー不要"},
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["decision"] == "CANCELLED"

        listed = await ctx.client.get("/api/gates", headers=ctx.headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 0

        history = await ctx.client.get(f"/api/tasks/{ids['task_id']}/gates", headers=ctx.headers)
        assert history.status_code == 200, history.text
        assert history.json()["items"][0]["decision"] == "CANCELLED"

    async def test_other_reviewer_cannot_read_or_decide_gate(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """subject と Gate reviewer が一致しなければ 403。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx, reviewer_id=uuid4())

        read = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert read.status_code == 403
        assert _error_message(read) == (
            "Reviewer is not authorized for this gate.\n"
            "Next: Sign in as the assigned reviewer for this gate."
        )

        for action, payload in (
            ("approve", {"comment": None}),
            ("reject", {"feedback_text": "直して"}),
            ("cancel", {"reason": "取消"}),
        ):
            decided = await ctx.client.post(
                f"/api/gates/{ids['gate_id']}/{action}",
                headers=ctx.headers,
                json=payload,
            )
            assert decided.status_code == 403

    async def test_authentication_and_property_injection_are_rejected(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """Bearer token と extra='forbid' の境界を確認する。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        missing = await ctx.client.get(f"/api/gates/{ids['gate_id']}")
        assert missing.status_code == 401

        invalid = await ctx.client.get(
            f"/api/gates/{ids['gate_id']}",
            headers={"Authorization": "Bearer wrong-token-value-that-is-long-enough"},
        )
        assert invalid.status_code == 401
        assert "wrong-token-value" not in invalid.text
        assert "Authorization" not in invalid.text

        spoofed = await ctx.client.get(
            f"/api/gates/{ids['gate_id']}",
            headers={"X-Reviewer-Id": str(ctx.reviewer_id)},
        )
        assert spoofed.status_code == 401

        injected = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/reject",
            headers=ctx.headers,
            json={"feedback_text": "直して", "actor_id": str(ctx.reviewer_id)},
        )
        assert injected.status_code == 422
        assert "Next: Fix the request parameters and retry." in _error_message(injected)

    async def test_validation_errors_include_next_guidance(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-009: UUID/query/body validation は Next 行を返す。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        bad_uuid = await ctx.client.get("/api/gates/not-a-uuid", headers=ctx.headers)
        assert bad_uuid.status_code == 422
        assert "Next: Fix the request parameters and retry." in _error_message(bad_uuid)

        bad_decision = await ctx.client.get(
            "/api/gates?decision=APPROVED",
            headers=ctx.headers,
        )
        assert bad_decision.status_code == 422
        assert "Next: Fix the request parameters and retry." in _error_message(bad_decision)

        empty_feedback = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/reject",
            headers=ctx.headers,
            json={"feedback_text": ""},
        )
        assert empty_feedback.status_code == 422
        assert "Next: Fix the request parameters and retry." in _error_message(empty_feedback)

    async def test_already_decided_gate_returns_conflict(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """PENDING 以外への再判断は 409。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        first = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/cancel",
            headers=ctx.headers,
            json={"reason": "取り消し"},
        )
        assert first.status_code == 200, first.text

        second = await ctx.client.post(
            f"/api/gates/{ids['gate_id']}/approve",
            headers=ctx.headers,
            json={"comment": "再承認"},
        )
        assert second.status_code == 409
        assert _error_message(second) == (
            "External review gate has already been decided.\n"
            "Next: Open the task gate history and review the latest pending gate."
        )

    async def test_unknown_gate_returns_not_found_with_next_guidance(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-UT-ERG-HTTP-011相当: not_found handler の2行文言を HTTP で固定する。"""
        ctx = external_review_gate_http_ctx

        response = await ctx.client.get(f"/api/gates/{uuid4()}", headers=ctx.headers)

        assert response.status_code == 404
        assert _error_message(response) == (
            "External review gate not found.\n"
            "Next: Refresh the gate list and select an existing gate."
        )

    async def test_repository_restored_redacted_values_are_not_unmasked(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-010: HTTP は Repository 復元値を復号しない。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        response = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)

        assert response.status_code == 200, response.text
        assert _RAW_SECRET not in response.text
        assert "<REDACTED:" in response.text

    async def test_csrf_origin_guard_rejects_state_changes(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-IT-ERG-HTTP-014: 不許可 Origin の状態変更 POST は 403。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)
        headers = {**ctx.headers, "Origin": "http://evil.example.com"}

        for action, payload in (
            ("approve", {"comment": "承認"}),
            ("reject", {"feedback_text": "差し戻し"}),
            ("cancel", {"reason": "取消"}),
        ):
            response = await ctx.client.post(
                f"/api/gates/{ids['gate_id']}/{action}",
                headers=headers,
                json=payload,
            )
            assert response.status_code == 403
            assert _error_message(response) == "CSRF check failed: Origin not allowed."

    async def test_bearer_token_configuration_boundaries(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-ERG-HTTP-016: token長、不一致、owner UUID不正は失敗する。"""
        ctx = external_review_gate_http_ctx
        ids = await _seed_gate(ctx)

        ok = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert ok.status_code == 200, ok.text

        monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", "short-token")
        short = await ctx.client.get(
            f"/api/gates/{ids['gate_id']}",
            headers={"Authorization": "Bearer short-token"},
        )
        assert short.status_code == 401

        monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", _TOKEN)
        monkeypatch.setenv("BAKUFU_OWNER_ID", "not-a-uuid")
        bad_owner = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
        assert bad_owner.status_code == 401
        assert _TOKEN not in bad_owner.text
        assert "Authorization" not in bad_owner.text

    async def test_openapi_inventory_contains_only_six_external_review_gate_apis(
        self,
        external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    ) -> None:
        """TC-STATIC-ERG-HTTP-002: API 棚卸しは 6 endpoint に固定する。"""
        ctx = external_review_gate_http_ctx

        response = await ctx.client.get("/openapi.json")

        assert response.status_code == 200, response.text
        paths = response.json()["paths"]
        external_gate_operations = {
            f"{method.upper()} {path}"
            for path, methods in paths.items()
            for method, spec in methods.items()
            if "external-review-gate" in spec.get("tags", [])
        }
        assert external_gate_operations == {
            "GET /api/gates",
            "GET /api/gates/{gate_id}",
            "POST /api/gates/{gate_id}/approve",
            "POST /api/gates/{gate_id}/reject",
            "POST /api/gates/{gate_id}/cancel",
            "GET /api/tasks/{task_id}/gates",
        }

    async def test_no_outbound_http_client_is_introduced(self) -> None:
        """TC-STATIC-ERG-HTTP-001: 外部 URL fetch / HTTP client import は存在しない。"""
        source_files = [
            Path("backend/src/bakufu/interfaces/http/routers/external_review_gates.py"),
            Path("backend/src/bakufu/interfaces/http/schemas/external_review_gate.py"),
            Path("backend/src/bakufu/application/services/external_review_gate_service.py"),
        ]
        forbidden = {"httpx", "requests", "urllib", "aiohttp"}
        violations: list[str] = []

        for source_file in source_files:
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".", maxsplit=1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom):
                    names = {(node.module or "").split(".", maxsplit=1)[0]}
                else:
                    continue
                for name in names & forbidden:
                    violations.append(f"{source_file}:{node.lineno}: {name}")

        assert violations == []


def _action_names(body: dict[str, Any]) -> list[str]:
    return [entry["action"] for entry in body["audit_trail"]]


def _error_message(response: Any) -> str:
    return str(response.json()["error"]["message"])
