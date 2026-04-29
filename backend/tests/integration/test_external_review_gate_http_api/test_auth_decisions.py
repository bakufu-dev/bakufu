"""ExternalReviewGate HTTP API authorization and decision tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from .helpers import (
    RAW_SECRET,
    TOKEN,
    ExternalReviewGateHttpCtx,
    error_message,
    seed_gate,
)

pytestmark = pytest.mark.asyncio


async def test_reject_flow_exposes_feedback_in_task_history(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-005/012: reject 後の履歴で feedback を観測できる。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

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
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """TC-IT-ERG-HTTP-006/013: cancel 後は PENDING 一覧から消え履歴に残る。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

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


@pytest.mark.parametrize(
    ("action", "payload"),
    [
        ("approve", {"comment": RAW_SECRET}),
        ("reject", {"feedback_text": RAW_SECRET}),
        ("cancel", {"reason": RAW_SECRET}),
    ],
)
async def test_decision_responses_mask_secret_text_immediately(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    action: str,
    payload: dict[str, str],
) -> None:
    """TC-IT-ERG-HTTP-017: approve/reject/cancel の即時応答は保存後の masked 値を返す。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)
    response = await ctx.client.post(
        f"/api/gates/{ids['gate_id']}/{action}",
        headers=ctx.headers,
        json=payload,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert RAW_SECRET not in response.text
    assert "<REDACTED:GITHUB_PAT>" in body["feedback_text"]
    assert "<REDACTED:GITHUB_PAT>" in body["audit_trail"][-1]["comment"]


async def test_other_reviewer_cannot_read_or_decide_gate(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """subject と Gate reviewer が一致しなければ 403。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx, reviewer_id=uuid4())

    read = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
    assert read.status_code == 403
    assert error_message(read) == (
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
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
) -> None:
    """Bearer token と extra='forbid' の境界を確認する。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

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
    assert "Next: Fix the request parameters and retry." in error_message(injected)


async def test_bearer_token_configuration_boundaries(
    external_review_gate_http_ctx: ExternalReviewGateHttpCtx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IT-ERG-HTTP-016: token長、不一致、owner UUID不正は失敗する。"""
    ctx = external_review_gate_http_ctx
    ids = await seed_gate(ctx)

    ok = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
    assert ok.status_code == 200, ok.text

    monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", "short-token")
    short = await ctx.client.get(
        f"/api/gates/{ids['gate_id']}",
        headers={"Authorization": "Bearer short-token"},
    )
    assert short.status_code == 401

    monkeypatch.setenv("BAKUFU_OWNER_API_TOKEN", TOKEN)
    monkeypatch.setenv("BAKUFU_OWNER_ID", "not-a-uuid")
    bad_owner = await ctx.client.get(f"/api/gates/{ids['gate_id']}", headers=ctx.headers)
    assert bad_owner.status_code == 401
    assert TOKEN not in bad_owner.text
    assert "Authorization" not in bad_owner.text
