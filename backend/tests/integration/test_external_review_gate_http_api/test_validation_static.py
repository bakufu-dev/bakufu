"""ExternalReviewGate HTTP API validation and static-contract tests."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from .helpers import ExternalReviewGateHttpCtx, error_message, seed_gate

pytestmark = pytest.mark.asyncio


async def test_validation_errors_include_next_guidance(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-009: UUID/query/body validation は Next 行を返す。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

    bad_uuid = await ctx.client.get("/api/gates/not-a-uuid", headers=ctx.headers)
    assert bad_uuid.status_code == 422
    assert "Next: Fix the request parameters and retry." in error_message(bad_uuid)

    bad_decision = await ctx.client.get("/api/gates?decision=APPROVED", headers=ctx.headers)
    assert bad_decision.status_code == 422
    assert "Next: Fix the request parameters and retry." in error_message(bad_decision)

    empty_feedback = await ctx.client.post(
        f"/api/gates/{ids['gate_id']}/reject",
        headers=ctx.headers,
        json={"feedback_text": ""},
    )
    assert empty_feedback.status_code == 422
    assert "Next: Fix the request parameters and retry." in error_message(empty_feedback)


async def test_already_decided_gate_returns_conflict(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """PENDING 以外への再判断は 409。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

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
    assert error_message(second) == (
        "External review gate has already been decided.\n"
        "Next: Open the task gate history and review the latest pending gate."
    )


async def test_unknown_gate_returns_not_found_with_next_guidance(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-UT-ERG-HTTP-011相当: not_found handler の2行文言を HTTP で固定する。"""
    ctx = external_review_gate_http_ctx

    response = await ctx.client.get(f"/api/gates/{uuid4()}", headers=ctx.headers)

    assert response.status_code == 404
    assert error_message(response) == (
        "External review gate not found.\nNext: Refresh the gate list and select an existing gate."
    )


async def test_csrf_origin_guard_rejects_state_changes(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-014: 不許可 Origin の状態変更 POST は 403。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)
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
        assert error_message(response) == "CSRF check failed: Origin not allowed."


async def test_openapi_inventory_contains_only_six_external_review_gate_apis(
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


async def test_no_outbound_http_client_is_introduced() -> None:
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
