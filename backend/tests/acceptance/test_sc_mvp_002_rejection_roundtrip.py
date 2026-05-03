"""SC-MVP-002 受入テスト: INTERNAL_REVIEW 差し戻し → 再提出 → APPROVED 完走。

受入基準:
  #6: 差し戻し後 Stage 再実行 → deliverable 生成
  #18: REVIEWER REJECTED → Task が前段 WORK Stage に差し戻し
  #17: ラウンド 2 APPROVED → 次 Stage に進む / InternalReviewGate 履歴保持

ブラックボックス原則:
  - HTTP API のみ使用（DB 直接アクセス禁止）
  - Stage 実行は POST /api/tasks/{task_id}/dispatch 経由
  - InternalReviewGate 確認は GET /api/tasks/{id}/internal-review-gates 経由
"""

from __future__ import annotations

import pytest

from tests.acceptance.conftest import (
    AcceptanceCtx,
    poll_gate_with_verdict,
    poll_internal_review_gates,
)

pytestmark = pytest.mark.asyncio

# V モデルプリセット Stage IDs
_STAGE_1_ID = "00000001-0000-4000-8000-000000000001"  # 要件定義 (WORK)
_STAGE_2_ID = "00000001-0000-4000-8000-000000000002"  # 要件レビュー (INTERNAL_REVIEW)
_STAGE_3_ID = "00000001-0000-4000-8000-000000000003"  # 基本設計 (WORK)

# Agent 作成用ペイロード
_AGENT_PROVIDER = [{"provider_kind": "CLAUDE_CODE", "model": "claude-test", "is_default": True}]
_AGENT_PERSONA = {
    "display_name": "テストエージェント",
    "archetype": None,
    "prompt_body": "You are a test agent.",
}


# ---------------------------------------------------------------------------
# HTTP API ヘルパ
# ---------------------------------------------------------------------------


async def _create_empire(client) -> str:
    r = await client.post("/api/empires", json={"name": "テスト幕府"})
    assert r.status_code == 201, f"Empire 作成失敗: {r.status_code} {r.text}"
    return r.json()["id"]


async def _create_agent(client, empire_id: str, role: str, name: str) -> str:
    r = await client.post(
        f"/api/empires/{empire_id}/agents",
        json={
            "name": name,
            "persona": _AGENT_PERSONA,
            "role": role,
            "providers": _AGENT_PROVIDER,
            "skills": [],
        },
    )
    assert r.status_code == 201, f"Agent 作成失敗: {r.status_code} {r.text}"
    return r.json()["id"]


async def _create_room(client, empire_id: str) -> str:
    """Room を workflow_id なしで作成して room_id を返す。"""
    r = await client.post(
        f"/api/empires/{empire_id}/rooms",
        json={"name": "テスト開発室", "description": "受入テスト用 Room"},
    )
    assert r.status_code == 201, f"Room 作成失敗: {r.status_code} {r.text}"
    return r.json()["id"]


async def _assign_agent_to_room(client, room_id: str, agent_id: str, role: str) -> None:
    r = await client.post(
        f"/api/rooms/{room_id}/agents",
        json={"agent_id": agent_id, "role": role},
    )
    assert r.status_code == 201, f"Room Agent 割り当て失敗 role={role}: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# 複合セットアップヘルパ
# ---------------------------------------------------------------------------


async def _full_setup(client) -> tuple[str, str, str, str, str]:
    """Empire + Room + V モデル Workflow + Agents + Task (IN_PROGRESS, Stage 1) 環境を構築。

    HTTP API のみ使用（ブラックボックス原則準拠）。

    Returns:
        (empire_id, room_id, workflow_id, leader_id, task_id)
    """
    empire_id = await _create_empire(client)
    leader_id = await _create_agent(client, empire_id, "LEADER", "リーダー")
    reviewer_id = await _create_agent(client, empire_id, "REVIEWER", "レビュアー")
    developer_id = await _create_agent(client, empire_id, "DEVELOPER", "開発者")
    tester_id = await _create_agent(client, empire_id, "TESTER", "テスター")

    # Room 作成（workflow なし）→ Agent 割り当て → Workflow 紐付け
    room_id = await _create_room(client, empire_id)
    for agent_id, role in [
        (leader_id, "LEADER"),
        (reviewer_id, "REVIEWER"),
        (developer_id, "DEVELOPER"),
        (tester_id, "TESTER"),
    ]:
        await _assign_agent_to_room(client, room_id, agent_id, role)

    r_wf = await client.post(
        f"/api/rooms/{room_id}/workflows",
        json={"preset_name": "v-model"},
    )
    assert r_wf.status_code == 201, f"Workflow 作成失敗: {r_wf.status_code} {r_wf.text}"
    workflow_id = r_wf.json()["id"]

    # Directive → Task (PENDING) → Assign → IN_PROGRESS
    r_dir = await client.post(
        f"/api/rooms/{room_id}/directives",
        json={"text": "差し戻し受入テスト用 directive"},
    )
    assert r_dir.status_code == 201, f"Directive 作成失敗: {r_dir.status_code} {r_dir.text}"
    task_id = r_dir.json()["task"]["id"]

    r_assign = await client.post(
        f"/api/tasks/{task_id}/assign",
        json={"agent_ids": [leader_id]},
    )
    assert r_assign.status_code == 200, f"Task assign 失敗: {r_assign.status_code} {r_assign.text}"

    return empire_id, room_id, workflow_id, leader_id, task_id


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestSCMvp002RejectionRoundtrip:
    """SC-MVP-002: INTERNAL_REVIEW 差し戻し → 再提出 → APPROVED 完走。"""

    async def test_step2_reviewer_rejected_task_returns_to_prev_stage(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 2: REVIEWER REJECTED → InternalReviewGate に REJECTED 記録 (受入基準 #18)。"""
        client = acceptance_ctx.client

        # verdicts = ["REJECTED"] で Stage 2 が REJECTED → Stage 1 に差し戻し
        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, leader_id, task_id = await _full_setup(client)

        # dispatch で Stage 1 から開始（HTTP API）
        r_dispatch = await client.post(f"/api/tasks/{task_id}/dispatch")
        assert r_dispatch.status_code == 200

        # REJECTED Gate が現れるまで待機（受入基準 #18）
        rejected_gate = await poll_gate_with_verdict(
            client,
            task_id,
            verdict="REJECTED",
            timeout=30.0,
            owner_id=leader_id,
        )
        assert rejected_gate["gate_decision"] == "REJECTED", (
            f"REJECTED Gate が記録されていない: {rejected_gate}"
        )

        # Task ステータスが IN_PROGRESS であることを確認
        r_task = await client.get(f"/api/tasks/{task_id}")
        task_data = r_task.json()
        assert task_data["status"] == "IN_PROGRESS", (
            f"REJECTED 後の Task ステータスが IN_PROGRESS でない: {task_data['status']}"
        )

    async def test_step3_agent_reruns_after_rejection(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 3: 差し戻し後 Stage 再実行 → deliverable 生成 (受入基準 #6)。"""
        client = acceptance_ctx.client

        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, leader_id, task_id = await _full_setup(client)

        # dispatch で Stage 1 から開始
        r_dispatch = await client.post(f"/api/tasks/{task_id}/dispatch")
        assert r_dispatch.status_code == 200

        # 2 ラウンド目の APPROVED Gate が現れるまで待機
        await poll_gate_with_verdict(
            client,
            task_id,
            verdict="ALL_APPROVED",
            timeout=30.0,
            owner_id=leader_id,
        )

        # 受入基準 #6: Stage 1 が 2 回実行された（chat() 2 回以上）
        assert acceptance_ctx.fake_llm.chat_call_count >= 2, (
            f"Stage 1 再実行で chat() が 2 回以上呼ばれなかった: "
            f"{acceptance_ctx.fake_llm.chat_call_count}"
        )

    async def test_step4_round2_approved_advances_to_next(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 4: ラウンド 2 APPROVED → 次 Stage に進む (受入基準 #17)。"""
        client = acceptance_ctx.client

        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, leader_id, task_id = await _full_setup(client)

        # dispatch で Stage 1 から開始
        r_dispatch = await client.post(f"/api/tasks/{task_id}/dispatch")
        assert r_dispatch.status_code == 200

        # ALL_APPROVED Gate が現れたら Stage 3 以降に進んでいるはず
        await poll_gate_with_verdict(
            client,
            task_id,
            verdict="ALL_APPROVED",
            timeout=30.0,
            owner_id=leader_id,
        )

        # ALL_APPROVED 後、_handle_all_approved() が Task を Stage 3 に進める。
        # Gate 保存と Task 更新は別セッション（Phase 2）のため、
        # Task が Stage 3 以降に遷移するまでポーリングして待機する（受入基準 #17）。
        import asyncio

        deadline = asyncio.get_event_loop().time() + 10.0
        task_data: dict = {}
        while asyncio.get_event_loop().time() < deadline:
            r_task = await client.get(f"/api/tasks/{task_id}")
            task_data = r_task.json()
            # Stage 1/2 を抜けた、または AWAITING_EXTERNAL_REVIEW になったら終了
            if task_data["current_stage_id"] not in {_STAGE_1_ID, _STAGE_2_ID}:
                break
            if task_data["status"] == "AWAITING_EXTERNAL_REVIEW":
                break
            await asyncio.sleep(0.05)

        assert task_data.get("status") in {"IN_PROGRESS", "AWAITING_EXTERNAL_REVIEW"}, (
            f"ラウンド 2 APPROVED 後の Task ステータスが不正: {task_data.get('status')}"
        )
        assert (
            task_data.get("current_stage_id") not in {_STAGE_1_ID, _STAGE_2_ID}
            or task_data.get("status") == "AWAITING_EXTERNAL_REVIEW"
        ), (
            f"ラウンド 2 APPROVED 後も Stage 1/2 に留まっている: "
            f"current_stage_id={task_data.get('current_stage_id')}"
        )

    async def test_step5_gate_history_preserved(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 5: InternalReviewGate 履歴 (REJECTED + ALL_APPROVED) 両方保持 (受入基準 #6)。"""
        client = acceptance_ctx.client

        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, leader_id, task_id = await _full_setup(client)

        # dispatch で Stage 1 から開始
        r_dispatch = await client.post(f"/api/tasks/{task_id}/dispatch")
        assert r_dispatch.status_code == 200

        # InternalReviewGate が 2 件（REJECTED + ALL_APPROVED）になるまで待機
        gates = await poll_internal_review_gates(
            client,
            task_id,
            min_count=2,
            timeout=30.0,
            owner_id=leader_id,
        )

        assert len(gates) >= 2, (
            f"InternalReviewGate 履歴が 2 件未満: {len(gates)} 件\n"
            f"Gates: {[(g['gate_decision'], g['stage_id'][:8]) for g in gates]}"
        )

        gate_decisions = {g["gate_decision"] for g in gates}
        assert "REJECTED" in gate_decisions, f"REJECTED Gate が履歴にない: {gate_decisions}"
        assert "ALL_APPROVED" in gate_decisions, f"ALL_APPROVED Gate が履歴にない: {gate_decisions}"
