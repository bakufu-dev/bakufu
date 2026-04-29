"""ExternalReviewGate HTTP API read-flow integration tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from .helpers import (
    RAW_SECRET,
    ExternalReviewGateHttpCtx,
    action_names,
    seed_gate,
    seed_gate_for_existing_task,
    seed_gate_with_awaiting_approved_transition,
)

pytestmark = pytest.mark.asyncio


async def test_list_returns_only_authenticated_reviewer_pending_gates(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-001: reviewer の PENDING 一覧を HTTP だけで観測する。"""
    ctx = external_review_gate_http_ctx
    first = await seed_gate(ctx)
    task_id = UUID(first["task_id"])
    stage_id = UUID(first["stage_id"])
    second = await seed_gate_for_existing_task(ctx, task_id=task_id, stage_id=stage_id)
    await seed_gate_for_existing_task(
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
    assert RAW_SECRET not in response.text


async def test_task_history_returns_only_authenticated_reviewer_gates(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-002: Task 履歴は subject の Gate だけを返す。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

    response = await ctx.client.get(f"/api/tasks/{ids['task_id']}/gates", headers=ctx.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == ids["gate_id"]


async def test_reviewer_flow_uses_public_http_only(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-004/011: 承認で Task が APPROVED 遷移先へ進む。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate_with_awaiting_approved_transition(ctx)

    listed = await ctx.client.get("/api/gates", headers=ctx.headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == ids["gate_id"]
    assert RAW_SECRET not in listed.text

    before_task = await ctx.client.get(f"/api/tasks/{ids['task_id']}")
    assert before_task.status_code == 200, before_task.text
    assert before_task.json()["status"] == "AWAITING_EXTERNAL_REVIEW"
    assert before_task.json()["current_stage_id"] == ids["review_stage_id"]

    viewed = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
    assert viewed.status_code == 200, viewed.text
    assert action_names(viewed.json()) == ["VIEWED"]

    approved = await ctx.client.post(
        f"/api/gates/{ids['gate_id']}/approve",
        headers=ctx.headers,
        json={"comment": "承認します"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["decision"] == "APPROVED"
    assert action_names(approved.json()) == ["VIEWED", "APPROVED"]

    advanced_task = await ctx.client.get(f"/api/tasks/{ids['task_id']}")
    assert advanced_task.status_code == 200, advanced_task.text
    assert advanced_task.json()["status"] == "IN_PROGRESS"
    assert advanced_task.json()["current_stage_id"] == ids["approved_stage_id"]

    history = await ctx.client.get(f"/api/tasks/{ids['task_id']}/gates", headers=ctx.headers)
    assert history.status_code == 200, history.text
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["decision"] == "APPROVED"


async def test_repository_restored_redacted_values_are_not_unmasked(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-010: HTTP は Repository 復元値を復号しない。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

    response = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)

    assert response.status_code == 200, response.text
    assert RAW_SECRET not in response.text
    assert "<REDACTED:" in response.text
