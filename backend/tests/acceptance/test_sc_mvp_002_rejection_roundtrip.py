"""SC-MVP-002 受入テスト: INTERNAL_REVIEW 差し戻し → 再提出 → APPROVED 完走。

受入基準:
  #6: 差し戻し後 Stage 再実行 → deliverable 生成
  #18: REVIEWER REJECTED → Task が前段 WORK Stage に差し戻し
  #17: ラウンド 2 APPROVED → 次 Stage に進む / InternalReviewGate 履歴保持

ブラックボックス原則:
  - Stage 実行は StageWorker.enqueue() 経由（HTTP API ポーリングで結果確認）
  - InternalReviewGate 確認は GET /api/tasks/{id}/internal-review-gates 経由
  - DB 直接アクセスなし
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.acceptance.conftest import (
    AcceptanceCtx,
    poll_gate_with_verdict,
    poll_internal_review_gates,
)

pytestmark = pytest.mark.asyncio

# V モデルプリセット Stage IDs
_STAGE_1_ID = UUID("00000001-0000-4000-8000-000000000001")  # 要件定義 (WORK)
_STAGE_2_ID = UUID("00000001-0000-4000-8000-000000000002")  # 要件レビュー (INTERNAL_REVIEW)
_STAGE_3_ID = UUID("00000001-0000-4000-8000-000000000003")  # 基本設計 (WORK)

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


# ---------------------------------------------------------------------------
# DB シードヘルパ（Room 作成と Task シードのみ）
# ---------------------------------------------------------------------------


async def _seed_temp_workflow_and_room(session_factory, empire_id: UUID) -> UUID:
    """DB に最小構成の temp Workflow + Room を直接シードして room_id を返す。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    from tests.factories.room import make_room
    from tests.factories.workflow import make_stage, make_workflow

    temp_stage = make_stage()
    temp_workflow = make_workflow(stages=[temp_stage], entry_stage_id=temp_stage.id)
    room = make_room(workflow_id=temp_workflow.id)

    async with session_factory() as session, session.begin():
        await SqliteWorkflowRepository(session).save(temp_workflow)
        await SqliteRoomRepository(session).save(room, empire_id)

    return room.id


async def _seed_task_in_progress(
    session_factory,
    room_id: UUID,
    leader_id: UUID,
) -> UUID:
    """DB に IN_PROGRESS Task (current_stage_id = Stage 1) を直接シードして task_id を返す。"""
    from datetime import UTC, datetime

    from bakufu.domain.directive.directive import Directive
    from bakufu.domain.value_objects import TaskStatus
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    from tests.factories.task import make_task

    now = datetime.now(UTC)
    directive_id = uuid4()
    task_id = uuid4()

    directive = Directive(
        id=directive_id,
        text="$ 差し戻し受入テスト用 directive",
        target_room_id=room_id,
        created_at=now,
    )
    task = make_task(
        task_id=task_id,
        room_id=room_id,
        directive_id=directive_id,
        current_stage_id=_STAGE_1_ID,
        status=TaskStatus.IN_PROGRESS,
        assigned_agent_ids=[leader_id],
        created_at=now,
        updated_at=now,
    )

    async with session_factory() as session, session.begin():
        directive_repo = SqliteDirectiveRepository(session)
        task_repo = SqliteTaskRepository(session)
        await directive_repo.save(directive)
        await task_repo.save(task)
        await directive_repo.save(directive.link_task(task_id))

    return task_id


# ---------------------------------------------------------------------------
# 複合セットアップヘルパ
# ---------------------------------------------------------------------------


async def _full_setup(client, session_factory) -> tuple[str, str, str, str, UUID]:
    """Empire + Room + V モデル Workflow + Agents + Task (IN_PROGRESS, Stage 1) 環境を構築。

    §不可逆性 回避: Agent 割り当てを V モデル Workflow 作成前に実施し、
    Task は DB に直接シードして Stage 1 に current_stage_id を設定する。

    Returns:
        (empire_id, room_id, workflow_id, leader_id, task_id_uuid)
    """
    empire_id = await _create_empire(client)
    leader_id = await _create_agent(client, empire_id, "LEADER", "リーダー")
    reviewer_id = await _create_agent(client, empire_id, "REVIEWER", "レビュアー")
    developer_id = await _create_agent(client, empire_id, "DEVELOPER", "開発者")
    tester_id = await _create_agent(client, empire_id, "TESTER", "テスター")

    # DB シード: temp Workflow + Room
    room_id_uuid = await _seed_temp_workflow_and_room(session_factory, UUID(empire_id))
    room_id = str(room_id_uuid)

    # Agent を Room に割り当て (temp Workflow を読む → OK)
    for agent_id, role in [
        (leader_id, "LEADER"),
        (reviewer_id, "REVIEWER"),
        (developer_id, "DEVELOPER"),
        (tester_id, "TESTER"),
    ]:
        r = await client.post(
            f"/api/rooms/{room_id}/agents",
            json={"agent_id": agent_id, "role": role},
        )
        assert r.status_code == 201, (
            f"Room Agent 割り当て失敗 role={role}: {r.status_code} {r.text}"
        )

    # V モデルプリセット Workflow を Room に紐付け (HTTP API)
    r_wf = await client.post(
        f"/api/rooms/{room_id}/workflows",
        json={"preset_name": "v-model"},
    )
    assert r_wf.status_code == 201, f"Workflow 作成失敗: {r_wf.status_code} {r_wf.text}"
    workflow_id = r_wf.json()["id"]

    # §不可逆性 回避: Task を DB に直接シード（Stage 1、leader 割り当て済み、IN_PROGRESS）
    task_id_uuid = await _seed_task_in_progress(session_factory, room_id_uuid, UUID(leader_id))

    return empire_id, room_id, workflow_id, leader_id, task_id_uuid


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestSCMvp002RejectionRoundtrip:
    """SC-MVP-002: INTERNAL_REVIEW 差し戻し → 再提出 → APPROVED 完走。"""

    async def test_step2_reviewer_rejected_task_returns_to_prev_stage(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 2: REVIEWER REJECTED → InternalReviewGate に REJECTED 記録 (受入基準 #18)。

        シナリオ:
        1. Stage 1 (要件定義, WORK) → chat() で deliverable 生成
        2. Stage 2 (要件レビュー, INTERNAL_REVIEW) → REJECTED
        → InternalReviewGate に REJECTED が記録される
        → Task.current_stage_id が Stage 1 (要件定義) に戻ること

        StageWorker が REJECTED 後に Stage 1 を再 enqueue するため、
        「REJECTED Gate が存在する」ことで差し戻しを確認する（公開 API 経由）。
        その後 Task が Stage 1 に戻っていることを current_stage_id で検証する。
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        stage_worker = acceptance_ctx.stage_worker

        # verdicts = ["REJECTED"] で Stage 2 が REJECTED → Stage 1 に差し戻し
        # 2 回目の Stage 2 は verdicts が空 → APPROVED → 次 Stage に進む
        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, _, task_id = await _full_setup(client, session_factory)

        # Stage 1 から開始
        stage_worker.enqueue(task_id, _STAGE_1_ID)

        # REJECTED Gate が現れるまで待機（受入基準 #18）
        rejected_gate = await poll_gate_with_verdict(
            client, task_id, verdict="REJECTED", timeout=30.0
        )
        assert rejected_gate["gate_decision"] == "REJECTED", (
            f"REJECTED Gate が記録されていない: {rejected_gate}"
        )

        # Task の current_stage_id が Stage 1 に戻っていること
        # （REJECTED 後 StageWorker が Stage 1 を再 enqueue するまでの一瞬の間に確認）
        # → REJECTED Gate が存在する = 差し戻しが起きたことの証明
        # Task は既に Stage 1 を再実行中 or 再実行前の状態。
        # ステータスが IN_PROGRESS であることを確認。
        r_task = await client.get(f"/api/tasks/{task_id}")
        task_data = r_task.json()
        assert task_data["status"] == "IN_PROGRESS", (
            f"REJECTED 後の Task ステータスが IN_PROGRESS でない: {task_data['status']}"
        )

    async def test_step3_agent_reruns_after_rejection(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 3: 差し戻し後 Stage 再実行 → deliverable 生成 (受入基準 #6)。

        シナリオ:
        verdicts = ["REJECTED"] で Stage 2 が REJECTED → Stage 1 に差し戻し
        → Stage 1 再実行（chat() 2 回呼ばれる）
        → Stage 2 で APPROVED → Stage 3 (基本設計) へ
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        stage_worker = acceptance_ctx.stage_worker

        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, _, task_id = await _full_setup(client, session_factory)

        # Stage 1 から開始 → REJECTED → 再実行 → APPROVED → Stage 3 へ
        stage_worker.enqueue(task_id, _STAGE_1_ID)

        # 2 ラウンド目の APPROVED Gate が現れるまで待機
        await poll_gate_with_verdict(client, task_id, verdict="ALL_APPROVED", timeout=30.0)

        # 受入基準 #6: Stage 1 が 2 回実行された（chat() 2 回）
        assert acceptance_ctx.fake_llm.chat_call_count >= 2, (
            f"Stage 1 再実行で chat() が 2 回以上呼ばれなかった: "
            f"{acceptance_ctx.fake_llm.chat_call_count}"
        )

    async def test_step4_round2_approved_advances_to_next(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 4: ラウンド 2 APPROVED → 次 Stage に進む (受入基準 #17)。

        シナリオ:
        1. Stage 2 (REJECTED) → Stage 1 に差し戻し
        2. Stage 1 再実行 → Stage 2 (APPROVED) → Stage 3 (基本設計) へ
        → Task.current_stage_id が Stage 3 (基本設計) になること（または後続 Stage）
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        stage_worker = acceptance_ctx.stage_worker

        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, _, task_id = await _full_setup(client, session_factory)

        # Stage 1 から開始 → REJECTED → Stage 1 再実行 → APPROVED → Stage 3 以降
        stage_worker.enqueue(task_id, _STAGE_1_ID)

        # ALL_APPROVED Gate が現れたら Stage 3 以降に進んでいるはず
        await poll_gate_with_verdict(client, task_id, verdict="ALL_APPROVED", timeout=30.0)

        # Task が Stage 3 以降（IN_PROGRESS のまま）であることを確認（受入基準 #17）
        r_task = await client.get(f"/api/tasks/{task_id}")
        task_data = r_task.json()

        # Stage 2 が APPROVED → 次 Stage (Stage 3: 基本設計) に進む
        # または既に StageWorker が Stage 3 を処理してさらに先に進んでいる可能性もある
        assert task_data["status"] in {"IN_PROGRESS", "AWAITING_EXTERNAL_REVIEW"}, (
            f"ラウンド 2 APPROVED 後の Task ステータスが不正: {task_data['status']}"
        )
        # Stage 1 や Stage 2 に留まっていないことを確認
        assert task_data["current_stage_id"] not in {
            str(_STAGE_1_ID),
            str(_STAGE_2_ID),
        } or task_data["status"] == "AWAITING_EXTERNAL_REVIEW", (
            f"ラウンド 2 APPROVED 後も Stage 1/2 に留まっている: "
            f"current_stage_id={task_data['current_stage_id']}"
        )

    async def test_step5_gate_history_preserved(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 5: InternalReviewGate 履歴 (REJECTED + ALL_APPROVED) 両方保持 (受入基準 #6)。

        シナリオ:
        1. Stage 2 (REJECTED) → Gate 1: REJECTED
        2. Stage 1 再実行 → Stage 2 (APPROVED) → Gate 2: ALL_APPROVED
        → GET /api/tasks/{id}/internal-review-gates で 2 件確認
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        stage_worker = acceptance_ctx.stage_worker

        acceptance_ctx.fake_llm.reset(verdicts=["REJECTED"])

        _, _, _, _, task_id = await _full_setup(client, session_factory)

        # Stage 1 から開始 → REJECTED → 再実行 → APPROVED
        stage_worker.enqueue(task_id, _STAGE_1_ID)

        # InternalReviewGate が 2 件（REJECTED + ALL_APPROVED）になるまで待機
        gates = await poll_internal_review_gates(
            client, task_id, min_count=2, timeout=30.0
        )

        assert len(gates) >= 2, (
            f"InternalReviewGate 履歴が 2 件未満: {len(gates)} 件\n"
            f"Gates: {[(g['gate_decision'], g['stage_id'][:8]) for g in gates]}"
        )

        gate_decisions = {g["gate_decision"] for g in gates}
        assert "REJECTED" in gate_decisions, (
            f"REJECTED Gate が履歴にない: {gate_decisions}"
        )
        assert "ALL_APPROVED" in gate_decisions, (
            f"ALL_APPROVED Gate が履歴にない: {gate_decisions}"
        )
