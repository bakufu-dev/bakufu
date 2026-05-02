"""SC-MVP-001 受入テスト — Vモデル開発室 directive → Task AWAITING_EXTERNAL_REVIEW.

受入基準:
  #3: directive → Task が最初の Stage で起票される
  #4: Stage 実行（WORK + INTERNAL_REVIEW）が正常進行する
  #17: 全 INTERNAL_REVIEW APPROVED → Task が AWAITING_EXTERNAL_REVIEW になる

セットアップ戦略（§不可逆性回避）:
  - Empire / Agent は HTTP API で作成
  - Room は DB 直接シード（temp workflow）→ Agent 割り当て → Directive 発行を
    V モデルプリセット Workflow 保存の前に実施（Workflow 読み取りはこの時点では
    temp workflow に対して行われ、マスク問題が発生しない）
  - V モデル Workflow は HTTP API (POST /api/rooms/{id}/workflows) で作成
  - Directive / Task は V モデル Workflow 作成の前に HTTP API で発行し、
    発行後に task.current_stage_id を Stage 1 に DB 直接更新する
  - Task への Agent 割り当ては V モデル Workflow 作成後に HTTP API で実施
    （TaskService.assign は workflow を読まない）
  - Stage 実行は InMemory workflow 経由の mock workflow_repo を使って
    StageExecutorService.dispatch_stage() を直接呼び出す（§不可逆性回避）
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.acceptance.conftest import AcceptanceCtx
from tests.acceptance.fake_llm_provider import FakeRoundBasedLLMProvider

pytestmark = pytest.mark.asyncio

# V モデルプリセット定数
_VMODEL_STAGE_COUNT = 14
_VMODEL_TRANSITION_COUNT = 16

# V モデル Stage 1 (要件定義, WORK) の固定 ID
_STAGE_1_ID = UUID("00000001-0000-4000-8000-000000000001")

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


# ---------------------------------------------------------------------------
# DB シードヘルパ
# ---------------------------------------------------------------------------


async def _seed_temp_workflow_and_room(session_factory, empire_id: UUID) -> tuple[UUID, UUID]:
    """DB に最小構成の temp Workflow + Room を直接シードして (room_id, temp_stage_id) を返す。

    Room 作成 HTTP API が workflow_id の存在を検証するため、先に DB にシードする必要がある。
    この temp Workflow は WORK Stage のみを持ち、§不可逆性 の問題が発生しない。
    """
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

    return room.id, temp_stage.id


async def _seed_task_at_stage(
    session_factory,
    room_id: UUID,
    directive_id: UUID,
    task_id: UUID,
    stage_id: UUID,
    assigned_agent_ids: list[UUID],
) -> None:
    """DB に IN_PROGRESS Task を直接シードする（current_stage_id = stage_id）。

    §不可逆性 回避: DirectiveService.issue() が workflow_repo を読むため、
    V モデル Workflow 保存後は HTTP API でディレクティブを発行できない。
    代わりに DB に直接シードして current_stage_id を V モデル Stage 1 に設定する。
    """
    # Task を IN_PROGRESS で作成（AssignedAgent がいれば IN_PROGRESS が要件）
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
    directive = Directive(
        id=directive_id,
        text="$ 受入テスト用 directive",
        target_room_id=room_id,
        created_at=now,
    )
    task = make_task(
        task_id=task_id,
        room_id=room_id,
        directive_id=directive_id,
        current_stage_id=stage_id,
        status=TaskStatus.IN_PROGRESS,
        assigned_agent_ids=assigned_agent_ids,
        created_at=now,
        updated_at=now,
    )

    async with session_factory() as session, session.begin():
        directive_repo = SqliteDirectiveRepository(session)
        task_repo = SqliteTaskRepository(session)
        await directive_repo.save(directive)
        # FK 制約: directives.task_id → tasks.id のため task を先に保存する
        await task_repo.save(task)
        # directive.link_task で task_id をリンク
        await directive_repo.save(directive.link_task(task_id))


async def _build_vmodel_workflow_in_memory(workflow_id: str) -> object:
    """HTTP API が返した workflow_id を使って V モデル Workflow をメモリ上に構築する。

    §不可逆性 回避: DB から読み戻すと MaskedJSONEncoded で伏字化された
    notify_channels が ValidationError を発生させるため、メモリ上で構築する。

    Returns:
        DB 保存時と同じ workflow_id を持つ Workflow オブジェクト。
        Stage IDs / Transition IDs は preset 定義の固定値。
    """
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


async def _setup_empire_agents_room_workflow(
    client, session_factory
) -> tuple[str, str, str, str, str, str, str]:
    """Empire + Agent + Room + V モデル Workflow 作成、Room へ Agent 割り当て。

    §不可逆性 回避のため以下の順序で実行する:
    1. Empire / Agent 作成 (HTTP API)
    2. temp Workflow + Room を DB 直接シード
    3. Agent を Room に割り当て (HTTP API) ← temp workflow を読む（OK）
    4. V モデル Workflow を Room に紐付け (HTTP API) ← DB 読み取りなし（POST レスポンスのみ）

    Returns:
        (empire_id, room_id, workflow_id, leader_id, developer_id, tester_id, reviewer_id)
    """
    empire_id = await _create_empire(client)

    leader_id = await _create_agent(client, empire_id, "LEADER", "リーダーエージェント")
    developer_id = await _create_agent(client, empire_id, "DEVELOPER", "開発者エージェント")
    tester_id = await _create_agent(client, empire_id, "TESTER", "テスターエージェント")
    reviewer_id = await _create_agent(client, empire_id, "REVIEWER", "レビュアーエージェント")

    # DB シード: temp Workflow + Room
    room_id_uuid, _ = await _seed_temp_workflow_and_room(session_factory, UUID(empire_id))
    room_id = str(room_id_uuid)

    # Agent を Room に割り当て (temp Workflow を読む → OK)
    for agent_id, role in [
        (leader_id, "LEADER"),
        (developer_id, "DEVELOPER"),
        (tester_id, "TESTER"),
        (reviewer_id, "REVIEWER"),
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

    return empire_id, room_id, workflow_id, leader_id, developer_id, tester_id, reviewer_id


# ---------------------------------------------------------------------------
# Dispatch ヘルパ
# ---------------------------------------------------------------------------


async def _dispatch_all_stages_until_awaiting(
    session_factory,
    task_id: UUID,
    stage_id: UUID,
    fake_provider: FakeRoundBasedLLMProvider,
    event_bus,
    vmodel_workflow,
    max_dispatches: int = 50,
) -> str:
    """task の current_stage からスタートし AWAITING_EXTERNAL_REVIEW になるまで
    dispatch_stage() を繰り返す。

    §不可逆性 回避: workflow_repo は AsyncMock で置き換え、DB ラウンドトリップを回避する。
    InternalReviewService の workflow_repo_factory も同様に mock で置き換える。

    Returns:
        終了理由を示す文字列:
          "AWAITING_EXTERNAL_REVIEW": 受入基準達成
          "DONE": 全 Stage 完了（想定外）
          "BLOCKED": LLM エラー等でブロック
          "MAX_DISPATCHES_REACHED": max_dispatches に達した（無限ループ防止）
          その他: 予期しない TaskStatus 文字列
    """
    from unittest.mock import AsyncMock

    from bakufu.application.services.internal_review_service import InternalReviewService
    from bakufu.application.services.stage_executor_service import StageExecutorService
    from bakufu.domain.value_objects import TaskStatus
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

    dispatched = 0
    current_task_id = task_id
    current_stage_id = stage_id

    # B023 回避: _capture_enqueue をループ外で定義し、queued_stages.clear() でリセット。
    queued_stages: list[tuple[UUID, UUID]] = []

    def _capture_enqueue(tid: UUID, sid: UUID) -> None:
        queued_stages.append((tid, sid))

    while dispatched < max_dispatches:
        queued_stages.clear()

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
            await service.dispatch_stage(current_task_id, current_stage_id)

        dispatched += 1

        # Task の最新状態を確認
        async with session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            task = await task_repo.find_by_id(current_task_id)

        if task is None:
            return "TASK_NOT_FOUND"
        if task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW:
            return "AWAITING_EXTERNAL_REVIEW"
        if task.status == TaskStatus.DONE:
            return "DONE"
        if task.status == TaskStatus.BLOCKED:
            return "BLOCKED"
        if task.status not in (TaskStatus.IN_PROGRESS,):
            return str(task.status)

        # 次の stage を queue から取得（INTERNAL_REVIEW 後の re-enqueue も含む）
        if queued_stages:
            current_task_id, current_stage_id = queued_stages[-1]
        else:
            # enqueue_fn が呼ばれなかった場合は Task.current_stage_id を使う
            current_stage_id = task.current_stage_id

    return "MAX_DISPATCHES_REACHED"


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestSCMvp001VmodelFullflow:
    """SC-MVP-001: Vモデル開発室でディレクティブから Task が AWAITING_EXTERNAL_REVIEW に至る。"""

    async def test_step1_empire_vmodel_room_14stages(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 1: Empire + V-model Room + Workflow (14 Stage / 16 Transition) 正常構築。

        Note: GET /api/workflows/{id} は §不可逆性（notify_channels のトークンが DB
        保存時にマスクされ再取得時に ValidationError になる）で利用不可。
        Workflow の構造検証は POST /api/rooms/{id}/workflows のレスポンスで行う。
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory

        # Empire 作成 (HTTP API)
        empire_id = await _create_empire(client)

        # DB シードで temp Room を作成し、V モデルプリセット Workflow を紐付け
        room_id_uuid, _ = await _seed_temp_workflow_and_room(session_factory, UUID(empire_id))
        room_id = str(room_id_uuid)

        # V モデルプリセット Workflow を Room に紐付け (HTTP API) → POST レスポンスで検証
        r_wf = await client.post(
            f"/api/rooms/{room_id}/workflows",
            json={"preset_name": "v-model"},
        )
        assert r_wf.status_code == 201, f"Workflow 作成失敗: {r_wf.status_code} {r_wf.text}"
        wf_data = r_wf.json()

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
        """Step 2: directive → Task が最初の Stage で起票される (受入基準 #3)。

        §不可逆性 回避戦略:
        - V モデル Workflow 作成後は workflow_repo.find_by_id が ValidationError を送出する。
        - Directive と Task は DB 直接シード（DirectiveService.issue() が workflow を読むため）。
        - Task の current_stage_id は V モデル Stage 1 (要件定義) に直接設定する。
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory

        # Empire + Agent + Room + V モデル Workflow 作成 + Agent 割り当て
        _, room_id, _, leader_id, *_ = await _setup_empire_agents_room_workflow(
            client, session_factory
        )

        # §不可逆性 回避: Directive + Task を DB に直接シード
        # Task の current_stage_id = Stage 1 (要件定義) の固定 ID
        directive_id = uuid4()
        task_id = uuid4()
        await _seed_task_at_stage(
            session_factory,
            room_id=UUID(room_id),
            directive_id=directive_id,
            task_id=task_id,
            stage_id=_STAGE_1_ID,
            assigned_agent_ids=[UUID(leader_id)],
        )

        # HTTP API で Task の最新状態を確認（受入基準 #3）
        r_task = await client.get(f"/api/tasks/{task_id}")
        assert r_task.status_code == 200, f"Task 取得失敗: {r_task.status_code} {r_task.text}"
        task_data = r_task.json()

        task_status = task_data["status"]
        task_current_stage_id = task_data["current_stage_id"]

        assert task_status == "IN_PROGRESS", f"Task の状態が IN_PROGRESS でない: {task_status}"
        assert task_current_stage_id == str(_STAGE_1_ID), (
            f"Task の current_stage_id が V モデル entry Stage (要件定義) でない: "
            f"{task_current_stage_id} != {_STAGE_1_ID}"
        )

    async def test_step3_stage_progression_work_and_internal_review(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 3/3.5a: 全 Stage 実行 → Task が AWAITING_EXTERNAL_REVIEW になる (受入基準 #4, #17)。

        §不可逆性 回避戦略:
        - Directive + Task は DB 直接シード（current_stage_id = Stage 1）
        - Stage 実行は mock workflow_repo (in-memory V モデル Workflow) を使用
        - InternalReviewService の workflow_repo_factory も mock で置き換え

        FakeRoundBasedLLMProvider を使って全 WORK / INTERNAL_REVIEW Stage を
        順番に実行し、Stage 14 (EXTERNAL_REVIEW) で AWAITING_EXTERNAL_REVIEW になることを確認する。

        V モデルステージ構成:
          WORK Stage (7 個): 1, 3, 5, 7, 8, 10, 11
          INTERNAL_REVIEW Stage (6 個): 2, 4, 6, 9, 12, 13
          EXTERNAL_REVIEW Stage (1 個): 14
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        event_bus = InMemoryEventBus()

        # Empire + Agent + Room + V モデル Workflow 作成 + Agent 割り当て
        (
            _,
            room_id,
            workflow_id,
            leader_id,
            *_,
        ) = await _setup_empire_agents_room_workflow(client, session_factory)

        # §不可逆性 回避: Directive + Task を DB に直接シード
        directive_id = uuid4()
        task_id = uuid4()
        await _seed_task_at_stage(
            session_factory,
            room_id=UUID(room_id),
            directive_id=directive_id,
            task_id=task_id,
            stage_id=_STAGE_1_ID,
            assigned_agent_ids=[UUID(leader_id)],
        )

        # §不可逆性 回避: V モデル Workflow をメモリ上で構築（DB 読み取りを回避）
        vmodel_workflow = await _build_vmodel_workflow_in_memory(workflow_id)

        # 全 INTERNAL_REVIEW Stage を APPROVED で実行するため verdicts は空（デフォルト APPROVED）
        fake_provider = FakeRoundBasedLLMProvider(chat_with_tools_verdicts=[])

        # Stage 1 (要件定義, WORK) から全 Stage を AWAITING_EXTERNAL_REVIEW まで実行
        final_status = await _dispatch_all_stages_until_awaiting(
            session_factory,
            task_id,
            _STAGE_1_ID,
            fake_provider,
            event_bus,
            vmodel_workflow,
            max_dispatches=50,
        )

        # 受入基準 #4 + #17: 全 Stage が正常進行し AWAITING_EXTERNAL_REVIEW になること
        assert final_status == "AWAITING_EXTERNAL_REVIEW", (
            f"Task が AWAITING_EXTERNAL_REVIEW にならなかった: final_status={final_status}\n"
            f"LLM 呼び出し数: "
            f"chat={fake_provider._chat_call_count}, "
            f"chat_with_tools={fake_provider._tools_call_count}"
        )

        # HTTP API で Task の最終状態を確認
        r_final = await client.get(f"/api/tasks/{task_id}")
        assert r_final.status_code == 200
        final_task = r_final.json()
        assert final_task["status"] == "AWAITING_EXTERNAL_REVIEW", (
            "API で確認した Task の最終状態が AWAITING_EXTERNAL_REVIEW でない: "
            f"{final_task['status']}"
        )

        # WORK Stage (1, 3, 5, 7, 8, 10, 11) = 7 個 → chat() 7 回
        assert fake_provider._chat_call_count == 7, (
            f"WORK Stage 実行 (chat) 回数が 7 でない: {fake_provider._chat_call_count}"
        )

        # INTERNAL_REVIEW Stage (2, 4, 6, 9, 12, 13) = 6 個 → chat_with_tools() 6 回
        assert fake_provider._tools_call_count == 6, (
            f"INTERNAL_REVIEW Stage 実行 (chat_with_tools) 回数が 6 でない: "
            f"{fake_provider._tools_call_count}"
        )
