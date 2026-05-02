"""SC-MVP-001 受入テスト — Vモデル開発室 directive → Task DONE.

受入基準:
  #3: directive → Task が最初の Stage で起票される
  #4: Stage 実行（WORK + INTERNAL_REVIEW）が正常進行する
  #7: 全 Stage 完了 → status=DONE（ExternalReviewGate 承認後）
  #17: 全 INTERNAL_REVIEW APPROVED → Task が AWAITING_EXTERNAL_REVIEW になる

ブラックボックス原則:
  - HTTP API のみ使用（DB 直接アクセス禁止）
  - Stage 実行は POST /api/tasks/{task_id}/dispatch 経由
  - 状態確認は HTTP API ポーリング
"""

from __future__ import annotations

import pytest

from tests.acceptance.conftest import (
    AcceptanceCtx,
    poll_task_status,
)

pytestmark = pytest.mark.asyncio

# V モデルプリセット定数
_VMODEL_STAGE_COUNT = 14
_VMODEL_TRANSITION_COUNT = 16

# Agent 作成用ペイロードテンプレート
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
    """Empire を HTTP API で作成して empire_id を返す。"""
    r = await client.post("/api/empires", json={"name": "テスト幕府"})
    assert r.status_code == 201, f"Empire 作成失敗: {r.status_code} {r.text}"
    return r.json()["id"]


async def _create_agent(client, empire_id: str, role: str, name: str) -> str:
    """Agent を Empire に採用して agent_id を返す。"""
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
    assert r.status_code == 201, f"Agent 作成失敗 role={role}: {r.status_code} {r.text}"
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
    """Agent を Room に割り当てる。"""
    r = await client.post(
        f"/api/rooms/{room_id}/agents",
        json={"agent_id": agent_id, "role": role},
    )
    assert r.status_code == 201, f"Room Agent 割り当て失敗 role={role}: {r.status_code} {r.text}"


async def _attach_vmodel_workflow(client, room_id: str) -> dict:
    """V モデルプリセット Workflow を Room に紐付けて workflow dict を返す。"""
    r = await client.post(
        f"/api/rooms/{room_id}/workflows",
        json={"preset_name": "v-model"},
    )
    assert r.status_code == 201, f"Workflow 作成失敗: {r.status_code} {r.text}"
    return r.json()


async def _create_directive(client, room_id: str) -> tuple[str, str]:
    """Directive を発行して (directive_id, task_id) を返す。"""
    r = await client.post(
        f"/api/rooms/{room_id}/directives",
        json={"text": "受入テスト用 directive"},
    )
    assert r.status_code == 201, f"Directive 作成失敗: {r.status_code} {r.text}"
    data = r.json()
    return data["directive"]["id"], data["task"]["id"]


async def _assign_agents_to_task(client, task_id: str, agent_ids: list[str]) -> dict:
    """Task に Agent を割り当てて task dict を返す。"""
    r = await client.post(
        f"/api/tasks/{task_id}/assign",
        json={"agent_ids": agent_ids},
    )
    assert r.status_code == 200, f"Task Agent 割り当て失敗: {r.status_code} {r.text}"
    return r.json()


async def _dispatch_task(client, task_id: str) -> dict:
    """Task を StageWorker にキューして task dict を返す。"""
    r = await client.post(f"/api/tasks/{task_id}/dispatch")
    assert r.status_code == 200, f"Task dispatch 失敗: {r.status_code} {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# 複合セットアップヘルパ
# ---------------------------------------------------------------------------


async def _setup_empire_agents_room_workflow(
    client,
) -> tuple[str, str, str, str, str, str, str]:
    """Empire + Agent + Room + V モデル Workflow 作成、Room へ Agent 割り当て。

    HTTP API のみ使用（ブラックボックス原則準拠）。
    順序:
    1. Empire / Agent 作成 (HTTP API)
    2. Room 作成（workflow_id なし）(HTTP API)
    3. Agent を Room に割り当て (HTTP API)
    4. V モデル Workflow を Room に紐付け (HTTP API)

    Returns:
        (empire_id, room_id, workflow_id, leader_id, developer_id, tester_id, reviewer_id)
    """
    empire_id = await _create_empire(client)

    leader_id = await _create_agent(client, empire_id, "LEADER", "リーダーエージェント")
    developer_id = await _create_agent(client, empire_id, "DEVELOPER", "開発者エージェント")
    tester_id = await _create_agent(client, empire_id, "TESTER", "テスターエージェント")
    reviewer_id = await _create_agent(client, empire_id, "REVIEWER", "レビュアーエージェント")

    # Room 作成（workflow_id なし）
    room_id = await _create_room(client, empire_id)

    # Agent を Room に割り当て（workflow なし → matching check スキップ）
    for agent_id, role in [
        (leader_id, "LEADER"),
        (developer_id, "DEVELOPER"),
        (tester_id, "TESTER"),
        (reviewer_id, "REVIEWER"),
    ]:
        await _assign_agent_to_room(client, room_id, agent_id, role)

    # V モデルプリセット Workflow を Room に紐付け
    wf_data = await _attach_vmodel_workflow(client, room_id)
    workflow_id = wf_data["id"]

    return empire_id, room_id, workflow_id, leader_id, developer_id, tester_id, reviewer_id


async def _setup_task_in_progress(client, room_id: str, leader_id: str) -> str:
    """Directive → Task → Assign → IN_PROGRESS な task_id を返す（HTTP API のみ）。"""
    _, task_id = await _create_directive(client, room_id)
    await _assign_agents_to_task(client, task_id, [leader_id])
    return task_id


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestSCMvp001VmodelFullflow:
    """SC-MVP-001: Vモデル開発室 — directive → Task AWAITING_EXTERNAL_REVIEW → DONE。

    受入基準 #3 / #4 / #7 / #17 を検証する。
    """

    async def test_step1_empire_vmodel_room_14stages(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 1: Empire + V-model Room + Workflow (14 Stage / 16 Transition) 正常構築。"""
        client = acceptance_ctx.client

        # Empire 作成 → Room 作成（workflow なし）→ Workflow 紐付け
        empire_id = await _create_empire(client)
        room_id = await _create_room(client, empire_id)
        wf_data = await _attach_vmodel_workflow(client, room_id)

        stage_count = len(wf_data["stages"])
        transition_count = len(wf_data["transitions"])

        assert stage_count == _VMODEL_STAGE_COUNT, (
            f"V モデルプリセットの Stage 数が期待値 {_VMODEL_STAGE_COUNT} と異なる: {stage_count}"
        )
        assert transition_count == _VMODEL_TRANSITION_COUNT, (
            f"V モデルプリセットの Transition 数が期待値 {_VMODEL_TRANSITION_COUNT} と異なる: "
            f"{transition_count}"
        )

        # Stage 14 (EXTERNAL_REVIEW / リリース前承認) が存在することを確認
        stage_by_name = {s["name"]: s["kind"] for s in wf_data["stages"]}
        assert "リリース前承認" in stage_by_name, (
            f"Stage 14 リリース前承認 が存在しない。Stage 名一覧: {list(stage_by_name.keys())}"
        )
        assert stage_by_name["リリース前承認"] == "EXTERNAL_REVIEW", (
            f"Stage 14 の kind が EXTERNAL_REVIEW でない: {stage_by_name['リリース前承認']}"
        )

        # Transition 16 (Stage 13 → Stage 14, APPROVED) が存在することを確認
        stage_id_by_name = {s["name"]: s["id"] for s in wf_data["stages"]}
        stage13_id = stage_id_by_name.get("リリース承認")
        stage14_id = stage_id_by_name.get("リリース前承認")
        assert stage13_id is not None and stage14_id is not None

        transition_16 = next(
            (
                t
                for t in wf_data["transitions"]
                if t["from_stage_id"] == stage13_id
                and t["to_stage_id"] == stage14_id
                and t["condition"] == "APPROVED"
            ),
            None,
        )
        transitions_summary = [
            (t["from_stage_id"][:8], t["to_stage_id"][:8], t["condition"])
            for t in wf_data["transitions"]
        ]
        assert transition_16 is not None, (
            f"Transition 16 (Stage 13 → Stage 14, APPROVED) が存在しない。"
            f"Transitions: {transitions_summary}"
        )

    async def test_step2_directive_creates_task(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 2: directive → Task が最初の Stage で起票される (受入基準 #3)。"""
        client = acceptance_ctx.client

        # Empire + Agent + Room + V モデル Workflow 作成 + Agent 割り当て
        _, room_id, workflow_id, leader_id, *_ = await _setup_empire_agents_room_workflow(client)

        # Directive 発行 → Task 起票 (受入基準 #3)
        _, task_id = await _create_directive(client, room_id)
        task_data = await _assign_agents_to_task(client, task_id, [leader_id])

        # V モデル Workflow の entry_stage_id (Stage 1) を取得
        r_wf = await client.get(f"/api/workflows/{workflow_id}")
        assert r_wf.status_code == 200, f"Workflow 取得失敗: {r_wf.status_code}"
        entry_stage_id = r_wf.json()["entry_stage_id"]

        assert task_data["status"] == "IN_PROGRESS", (
            f"Task の状態が IN_PROGRESS でない: {task_data['status']}"
        )
        assert task_data["current_stage_id"] == entry_stage_id, (
            f"Task の current_stage_id が V モデル entry Stage でない: "
            f"{task_data['current_stage_id']} != {entry_stage_id}"
        )

    async def test_step3_stage_progression_work_and_internal_review(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 3: 全 Stage 実行 → Task が AWAITING_EXTERNAL_REVIEW (受入基準 #4, #17)。

        HTTP API のみ使用（ブラックボックス原則準拠）。
        POST /api/tasks/{task_id}/dispatch 経由で Stage を開始し、
        HTTP API ポーリングで AWAITING_EXTERNAL_REVIEW を確認。
        """
        client = acceptance_ctx.client

        # 全 INTERNAL_REVIEW Stage を APPROVED で実行（verdicts 空 = 全 APPROVED）
        acceptance_ctx.fake_llm.reset(verdicts=None)

        _, room_id, _, leader_id, *_ = await _setup_empire_agents_room_workflow(client)
        task_id = await _setup_task_in_progress(client, room_id, leader_id)

        # Stage を dispatch（HTTP API）
        await _dispatch_task(client, task_id)

        # AWAITING_EXTERNAL_REVIEW になるまでポーリング（受入基準 #4 + #17）
        final_task = await poll_task_status(
            client,
            task_id,
            expected={"AWAITING_EXTERNAL_REVIEW", "DONE", "BLOCKED"},
            timeout=60.0,
        )

        assert final_task["status"] == "AWAITING_EXTERNAL_REVIEW", (
            "Task が AWAITING_EXTERNAL_REVIEW にならなかった: "
            f"status={final_task['status']}\n"
            f"LLM 呼び出し数: "
            f"chat={acceptance_ctx.fake_llm.chat_call_count}, "
            f"chat_with_tools={acceptance_ctx.fake_llm.tools_call_count}"
        )

        # WORK Stage (1, 3, 5, 7, 8, 10, 11) = 7 個 → chat() 7 回
        assert acceptance_ctx.fake_llm.chat_call_count == 7, (
            f"WORK Stage 実行 (chat) 回数が 7 でない: {acceptance_ctx.fake_llm.chat_call_count}"
        )

        # INTERNAL_REVIEW Stage (2, 4, 6, 9, 12, 13) = 6 個 → chat_with_tools() 6 回
        assert acceptance_ctx.fake_llm.tools_call_count == 6, (
            f"INTERNAL_REVIEW Stage 実行 (chat_with_tools) 回数が 6 でない: "
            f"{acceptance_ctx.fake_llm.tools_call_count}"
        )

    async def test_step4_external_review_gate_approve_completes_task(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 4: ExternalReviewGate 承認 → Task DONE (受入基準 #7)。

        Authorization ヘッダーは Task に割り当てられた leader_id（Finding 1 対応）。
        """
        client = acceptance_ctx.client

        acceptance_ctx.fake_llm.reset(verdicts=None)

        _, room_id, _, leader_id, *_ = await _setup_empire_agents_room_workflow(client)
        task_id = await _setup_task_in_progress(client, room_id, leader_id)

        # Stage を dispatch して AWAITING_EXTERNAL_REVIEW に到達
        await _dispatch_task(client, task_id)
        await poll_task_status(
            client,
            task_id,
            expected={"AWAITING_EXTERNAL_REVIEW"},
            timeout=60.0,
        )

        # ExternalReviewGate を取得（受入基準 #17: 自動生成されているはず）
        r_gates = await client.get(f"/api/tasks/{task_id}/gates")
        assert r_gates.status_code == 200, f"Gates 取得失敗: {r_gates.status_code}"
        gates = r_gates.json()["items"]
        assert len(gates) > 0, "ExternalReviewGate が自動生成されていない（受入基準 #17 違反）"

        pending_gates = [g for g in gates if g["decision"] == "PENDING"]
        assert len(pending_gates) > 0, f"PENDING な ExternalReviewGate がない: {gates}"
        gate_id = pending_gates[0]["id"]

        # ExternalReviewGate を承認（leader_id が reviewer_id として設定されている）
        r_approve = await client.post(
            f"/api/gates/{gate_id}/approve",
            headers={"Authorization": f"Bearer {leader_id}"},
            json={"comment": "受入テスト: 承認"},
        )
        assert r_approve.status_code == 200, (
            f"Gate 承認失敗: {r_approve.status_code} {r_approve.text}"
        )

        # Task が DONE になるまで待機（受入基準 #7）
        final_task = await poll_task_status(
            client,
            task_id,
            expected={"DONE", "BLOCKED"},
            timeout=30.0,
        )

        assert final_task["status"] == "DONE", (
            f"ExternalReviewGate 承認後も Task が DONE にならない: {final_task['status']}"
        )
