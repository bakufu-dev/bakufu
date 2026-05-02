"""SC-MVP-002 受入テスト: INTERNAL_REVIEW 差し戻し → 再提出 → APPROVED 完走。

受入基準:
  #6: 差し戻し後 Stage 再実行 → deliverable 生成
  #18: REVIEWER REJECTED → Task が前段 WORK Stage に差し戻し
  #17: ラウンド 2 APPROVED → 次 Stage に進む / InternalReviewGate 履歴保持

セットアップ戦略（§不可逆性回避）:
  SC-MVP-001 と同様に DB シード + mock workflow_repo のハイブリッド方式。
  全 Stage 実行は in-memory V モデル Workflow を返す mock workflow_repo を使用。
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.acceptance.conftest import AcceptanceCtx
from tests.acceptance.fake_llm_provider import FakeRoundBasedLLMProvider

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
# DB シードヘルパ
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


async def _seed_task_at_stage_1(
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


async def _build_vmodel_workflow_in_memory(workflow_id: str) -> object:
    """HTTP API が返した workflow_id を使って V モデル Workflow をメモリ上に構築する。"""
    from bakufu.application.presets.workflow_presets import WORKFLOW_PRESETS
    from bakufu.domain.workflow.workflow import Workflow

    preset = WORKFLOW_PRESETS["v-model"]
    return Workflow.model_validate(
        {
            "id": workflow_id,
            "name": preset.name,
            "stages": preset.stages,
            "transitions": preset.transitions,
            "entry_stage_id": preset.entry_stage_id,
        }
    )


# ---------------------------------------------------------------------------
# 複合セットアップヘルパ
# ---------------------------------------------------------------------------


async def _full_setup(client, session_factory) -> tuple[str, str, str, str, UUID, object]:
    """Empire + Room + V モデル Workflow + Agents + Task (IN_PROGRESS, Stage 1) 環境を構築する。

    §不可逆性 回避: Agent 割り当てを V モデル Workflow 作成の前に実施し、
    Task は DB に直接シードして Stage 1 に current_stage_id を設定する。

    Returns:
        (empire_id, room_id, workflow_id, leader_id, task_id_uuid, vmodel_workflow)
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
    task_id_uuid = await _seed_task_at_stage_1(session_factory, room_id_uuid, UUID(leader_id))

    # §不可逆性 回避: V モデル Workflow をメモリ上で構築
    vmodel_workflow = await _build_vmodel_workflow_in_memory(workflow_id)

    return empire_id, room_id, workflow_id, leader_id, task_id_uuid, vmodel_workflow


# ---------------------------------------------------------------------------
# Dispatch ヘルパ
# ---------------------------------------------------------------------------


async def _dispatch_single_stage(
    session_factory,
    task_id: UUID,
    stage_id: UUID,
    fake_provider: FakeRoundBasedLLMProvider,
    event_bus,
    vmodel_workflow,
) -> tuple[str, UUID]:
    """単一 Stage を dispatch_stage() で実行し、(task_status, next_enqueued_stage_id) を返す。

    §不可逆性 回避: workflow_repo と workflow_repo_factory を mock で置き換え。

    Returns:
        (task_status_str, next_stage_id):
            next_stage_id は enqueue_fn に渡された stage_id。
            enqueue されなかった場合は task.current_stage_id。
    """
    from unittest.mock import AsyncMock

    from bakufu.application.services.internal_review_service import InternalReviewService
    from bakufu.application.services.stage_executor_service import StageExecutorService
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
        SqliteInternalReviewGateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.infrastructure.reviewers.internal_review_gate_executor import (
        InternalReviewGateExecutor,
    )

    # §不可逆性 回避: DB 読み取りを行わず in-memory workflow を返す mock
    mock_workflow_repo = AsyncMock()
    mock_workflow_repo.find_by_id = AsyncMock(return_value=vmodel_workflow)

    def _fake_workflow_repo_factory(session):
        return mock_workflow_repo

    queued_stages: list[tuple[UUID, UUID]] = []

    def _capture_enqueue(tid: UUID, sid: UUID) -> None:
        queued_stages.append((tid, sid))

    async with session_factory() as session:
        review_svc = InternalReviewService(
            session_factory=session_factory,
            gate_repo_factory=SqliteInternalReviewGateRepository,
            task_repo_factory=SqliteTaskRepository,
            workflow_repo_factory=_fake_workflow_repo_factory,
            room_repo_factory=SqliteRoomRepository,
            event_bus=event_bus,
        )
        internal_review_executor = InternalReviewGateExecutor(
            review_svc=review_svc,
            llm_provider=fake_provider,
            agent_id=uuid4(),
            session_factory=session_factory,
        )
        service = StageExecutorService(
            task_repo=SqliteTaskRepository(session),
            workflow_repo=mock_workflow_repo,
            agent_repo=SqliteAgentRepository(session),
            room_repo=SqliteRoomRepository(session),
            session=session,
            llm_provider=fake_provider,
            internal_review_port=internal_review_executor,
            event_bus=event_bus,
            enqueue_fn=_capture_enqueue,
        )
        await service.dispatch_stage(task_id, stage_id)

    # Task の最新状態を取得
    async with session_factory() as session:
        task_repo = SqliteTaskRepository(session)
        task = await task_repo.find_by_id(task_id)

    assert task is not None
    next_stage_id = queued_stages[-1][1] if queued_stages else task.current_stage_id
    return str(task.status), next_stage_id


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestSCMvp002RejectionRoundtrip:
    """SC-MVP-002: INTERNAL_REVIEW 差し戻し → 再提出 → APPROVED 完走。"""

    async def test_step2_reviewer_rejected_task_returns_to_prev_stage(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 2: REVIEWER REJECTED → Task が前段 WORK Stage に差し戻し (受入基準 #18)。

        シナリオ:
        1. Stage 1 (要件定義, WORK) を dispatch → chat() で deliverable 生成
        2. Stage 2 (要件レビュー, INTERNAL_REVIEW) を REJECTED で dispatch
        → Task.current_stage_id が Stage 1 (要件定義) に戻ること
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        event_bus = InMemoryEventBus()

        _, _, _, _, task_id, vmodel_workflow = await _full_setup(client, session_factory)

        # Stage 1 (WORK / 要件定義) を APPROVED で dispatch
        all_approved_provider = FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[])
        _, next_s1 = await _dispatch_single_stage(
            session_factory, task_id, _STAGE_1_ID, all_approved_provider, event_bus, vmodel_workflow
        )
        # Stage 1 完了後は Stage 2 (要件レビュー) へ enqueue されるはず
        assert next_s1 == _STAGE_2_ID, f"Stage 1 完了後に Stage 2 にキューされなかった: {next_s1}"

        # Stage 2 (INTERNAL_REVIEW / 要件レビュー) を REJECTED で dispatch
        rejected_provider = FakeRoundBasedLLMProvider(chat_with_tools_verdicts=["REJECTED"])
        status_after_s2, _ = await _dispatch_single_stage(
            session_factory, task_id, _STAGE_2_ID, rejected_provider, event_bus, vmodel_workflow
        )

        # 受入基準 #18: REJECTED 後 Task は IN_PROGRESS のまま前段 Stage 1 に差し戻し
        assert status_after_s2 == "IN_PROGRESS", (
            f"REJECTED 後の Task ステータスが IN_PROGRESS でない: {status_after_s2}"
        )

        # Task の current_stage_id が Stage 1 に戻っていること
        async with session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            task = await task_repo.find_by_id(task_id)
        assert task is not None
        assert task.current_stage_id == _STAGE_1_ID, (
            f"REJECTED 後の current_stage_id が Stage 1 ({_STAGE_1_ID}) でない: "
            f"{task.current_stage_id}"
        )

    async def test_step3_agent_reruns_after_rejection(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 3: 差し戻し後 Stage 再実行 → deliverable 生成 (受入基準 #6)。

        シナリオ:
        1. Stage 1 → Stage 2 (REJECTED) → Task が Stage 1 に差し戻し
        2. Stage 1 を再実行 → 2 回目の chat() が呼ばれて deliverable が生成される
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        event_bus = InMemoryEventBus()

        _, _, _, _, task_id, vmodel_workflow = await _full_setup(client, session_factory)

        # ラウンド 1: Stage 1 → Stage 2 (REJECTED) → Stage 1 に差し戻し
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_1_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[]),
            event_bus,
            vmodel_workflow,
        )
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_2_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=["REJECTED"]),
            event_bus,
            vmodel_workflow,
        )

        # ラウンド 2: Stage 1 再実行
        rerun_provider = FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[])
        status_after_rerun, next_after_rerun = await _dispatch_single_stage(
            session_factory, task_id, _STAGE_1_ID, rerun_provider, event_bus, vmodel_workflow
        )

        # 受入基準 #6: 差し戻し後 Stage 再実行 → deliverable 生成（chat() が 1 回呼ばれた）
        assert rerun_provider._chat_call_count == 1, (
            f"Stage 1 再実行で chat() が 1 回呼ばれなかった: {rerun_provider._chat_call_count}"
        )
        assert status_after_rerun == "IN_PROGRESS", (
            f"Stage 1 再実行後の Task ステータスが IN_PROGRESS でない: {status_after_rerun}"
        )
        # 再実行後は Stage 2 (要件レビュー) にキューされているはず
        assert next_after_rerun == _STAGE_2_ID, (
            f"Stage 1 再実行後に Stage 2 にキューされなかった: {next_after_rerun}"
        )

    async def test_step4_round2_approved_advances_to_next(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 4: ラウンド 2 APPROVED → 次 Stage に進む (受入基準 #17)。

        シナリオ:
        1. Stage 1 → Stage 2 (REJECTED) → Stage 1 に差し戻し
        2. Stage 1 再実行 → Stage 2 (APPROVED)
        → Task.current_stage_id が Stage 3 (基本設計) になること
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        event_bus = InMemoryEventBus()

        _, _, _, _, task_id, vmodel_workflow = await _full_setup(client, session_factory)

        # ラウンド 1: Stage 1 → Stage 2 (REJECTED) → Stage 1 に差し戻し
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_1_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[]),
            event_bus,
            vmodel_workflow,
        )
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_2_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=["REJECTED"]),
            event_bus,
            vmodel_workflow,
        )

        # ラウンド 2: Stage 1 再実行 → Stage 2 (APPROVED)
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_1_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[]),
            event_bus,
            vmodel_workflow,
        )
        status_after_round2, _ = await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_2_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=["APPROVED"]),
            event_bus,
            vmodel_workflow,
        )

        # 受入基準 #17: APPROVED → 次 Stage (基本設計) に進む
        assert status_after_round2 == "IN_PROGRESS", (
            f"ラウンド 2 APPROVED 後の Task ステータスが IN_PROGRESS でない: {status_after_round2}"
        )

        # Task の current_stage_id が Stage 3 (基本設計) になっていること
        async with session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            task = await task_repo.find_by_id(task_id)
        assert task is not None
        assert task.current_stage_id == _STAGE_3_ID, (
            f"ラウンド 2 APPROVED 後の current_stage_id が Stage 3 ({_STAGE_3_ID}) でない: "
            f"{task.current_stage_id}"
        )

    async def test_step5_gate_history_preserved(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 5: InternalReviewGate 履歴 (REJECTED + ALL_APPROVED) 両方保持 (受入基準 #6)。

        シナリオ:
        1. Stage 2 (REJECTED) → Gate 1 が REJECTED で確定
        2. Stage 1 再実行 → Stage 2 (APPROVED) → Gate 2 が ALL_APPROVED で確定
        → find_all_by_task_id で 2 件の Gate 履歴が確認できること
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus
        from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
            SqliteInternalReviewGateRepository,
        )

        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        event_bus = InMemoryEventBus()

        _, _, _, _, task_id, vmodel_workflow = await _full_setup(client, session_factory)

        # ラウンド 1: Stage 1 → Stage 2 (REJECTED)
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_1_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[]),
            event_bus,
            vmodel_workflow,
        )
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_2_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=["REJECTED"]),
            event_bus,
            vmodel_workflow,
        )

        # ラウンド 2: Stage 1 再実行 → Stage 2 (APPROVED)
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_1_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[]),
            event_bus,
            vmodel_workflow,
        )
        await _dispatch_single_stage(
            session_factory,
            task_id,
            _STAGE_2_ID,
            FakeRoundBasedLLMProvider(chat_with_tools_verdicts=["APPROVED"]),
            event_bus,
            vmodel_workflow,
        )

        # InternalReviewGate 履歴を確認: 2 件 (REJECTED + ALL_APPROVED)
        async with session_factory() as session:
            gate_repo = SqliteInternalReviewGateRepository(session)
            gates = await gate_repo.find_all_by_task_id(task_id)

        assert len(gates) == 2, (
            f"InternalReviewGate 履歴が 2 件でない: {len(gates)} 件\n"
            f"Gates: {[(str(g.gate_decision), str(g.stage_id)[:8]) for g in gates]}"
        )

        gate_decisions = {str(g.gate_decision) for g in gates}
        assert "REJECTED" in gate_decisions, f"REJECTED Gate が履歴にない: {gate_decisions}"
        assert "ALL_APPROVED" in gate_decisions, f"ALL_APPROVED Gate が履歴にない: {gate_decisions}"
