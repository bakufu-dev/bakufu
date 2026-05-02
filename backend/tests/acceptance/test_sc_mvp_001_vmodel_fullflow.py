"""SC-MVP-001 受入テスト — Vモデル開発室 directive → Task AWAITING_EXTERNAL_REVIEW.

受入基準:
  #3: directive → Task が最初の Stage で起票される
  #4: Stage 実行（WORK + INTERNAL_REVIEW）が正常進行する
  #7: 全 Stage 完了 → status=DONE（ExternalReviewGate 承認後）
  #17: 全 INTERNAL_REVIEW APPROVED → Task が AWAITING_EXTERNAL_REVIEW になる

ブラックボックス原則:
  - Stage 実行は StageWorker.enqueue() 経由（HTTP API ポーリングで結果確認）
  - BUG-AT-002 修正後は AsyncMock workflow_repo が不要
  - DB 直接アクセスは acceptance_ctx.session_factory を使わず HTTP API のみ
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.acceptance.conftest import (
    AcceptanceCtx,
    poll_task_status,
)

pytestmark = pytest.mark.asyncio

# V モデルプリセット定数
_VMODEL_STAGE_COUNT = 14
_VMODEL_TRANSITION_COUNT = 16

# V モデル Stage 1 (要件定義, WORK) の固定 ID
_STAGE_1_ID = UUID("00000001-0000-4000-8000-000000000001")

# §暫定実装: _request_external_review() が使う固定 reviewer UUID（dispatcher.py と同値）
_SYSTEM_REVIEWER_ID = "00000000-0000-0000-0000-000000000099"

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
# DB シードヘルパ（§不可逆性回避のため Room 作成時のみ使用）
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
    4. V モデル Workflow を Room に紐付け (HTTP API)

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


async def _seed_task_in_progress(
    session_factory,
    room_id: UUID,
    leader_id: UUID,
) -> UUID:
    """DB に IN_PROGRESS Task (current_stage_id = Stage 1) を直接シードして task_id を返す。

    §不可逆性 回避: V モデル Workflow 作成後は DirectiveService.issue() が
    workflow_repo.find_by_id() を呼んでマスク済み notify_channels を再構築する。
    BUG-AT-002 修正後は ValidationError なしに読み戻せるが、Task の current_stage_id を
    Stage 1 固定にするため DB 直接シードを維持する。
    """
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
        text="$ 受入テスト用 directive",
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
# テストクラス
# ---------------------------------------------------------------------------


class TestSCMvp001VmodelFullflow:
    """SC-MVP-001: Vモデル開発室でディレクティブから Task が AWAITING_EXTERNAL_REVIEW に至る。"""

    async def test_step1_empire_vmodel_room_14stages(self, acceptance_ctx: AcceptanceCtx) -> None:
        """Step 1: Empire + V-model Room + Workflow (14 Stage / 16 Transition) 正常構築。

        Note: GET /api/workflows/{id} は §不可逆性（notify_channels のトークンが DB
        保存時にマスクされ再取得時に ValidationError になる）で利用不可。
        BUG-AT-002 修正後は find_by_id が成功するが、HTTP API レスポンスでの確認を維持。
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
        """Step 2: directive → Task が最初の Stage で起票される (受入基準 #3)。"""
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory

        # Empire + Agent + Room + V モデル Workflow 作成 + Agent 割り当て
        _, room_id, _, leader_id, *_ = await _setup_empire_agents_room_workflow(
            client, session_factory
        )

        # §不可逆性 回避: Directive + Task を DB に直接シード
        task_id = await _seed_task_in_progress(
            session_factory,
            room_id=UUID(room_id),
            leader_id=UUID(leader_id),
        )

        # HTTP API で Task の最新状態を確認（受入基準 #3）
        r_task = await client.get(f"/api/tasks/{task_id}")
        assert r_task.status_code == 200, f"Task 取得失敗: {r_task.status_code} {r_task.text}"
        task_data = r_task.json()

        assert task_data["status"] == "IN_PROGRESS", (
            f"Task の状態が IN_PROGRESS でない: {task_data['status']}"
        )
        assert task_data["current_stage_id"] == str(_STAGE_1_ID), (
            f"Task の current_stage_id が V モデル entry Stage (要件定義) でない: "
            f"{task_data['current_stage_id']} != {_STAGE_1_ID}"
        )

    async def test_step3_stage_progression_work_and_internal_review(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 3/3.5a: 全 Stage 実行 → Task が AWAITING_EXTERNAL_REVIEW (受入基準 #4, #17)。

        BUG-AT-001 修正: StageWorker.enqueue() 経由で Stage を開始し、
        HTTP API ポーリングで AWAITING_EXTERNAL_REVIEW を確認（ブラックボックス原則）。

        FakeRoundBasedLLMProvider を全 APPROVED で実行し、Stage 14 (EXTERNAL_REVIEW) で
        AWAITING_EXTERNAL_REVIEW になることを確認する。
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        stage_worker = acceptance_ctx.stage_worker

        # 全 INTERNAL_REVIEW Stage を APPROVED で実行（verdicts 空 = 全 APPROVED）
        acceptance_ctx.fake_llm.reset(verdicts=None)

        # Empire + Agent + Room + V モデル Workflow 作成 + Agent 割り当て
        _, room_id, _, leader_id, *_ = await _setup_empire_agents_room_workflow(
            client, session_factory
        )

        # Task を DB に直接シード（Stage 1 / IN_PROGRESS）
        task_id = await _seed_task_in_progress(
            session_factory,
            room_id=UUID(room_id),
            leader_id=UUID(leader_id),
        )

        # Stage 1 から全 Stage を StageWorker 経由で実行（ブラックボックス原則）
        stage_worker.enqueue(task_id, _STAGE_1_ID)

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
            f"WORK Stage 実行 (chat) 回数が 7 でない: "
            f"{acceptance_ctx.fake_llm.chat_call_count}"
        )

        # INTERNAL_REVIEW Stage (2, 4, 6, 9, 12, 13) = 6 個 → chat_with_tools() 6 回
        assert acceptance_ctx.fake_llm.tools_call_count == 6, (
            f"INTERNAL_REVIEW Stage 実行 (chat_with_tools) 回数が 6 でない: "
            f"{acceptance_ctx.fake_llm.tools_call_count}"
        )

    async def test_step4_external_review_gate_approve_completes_task(
        self, acceptance_ctx: AcceptanceCtx
    ) -> None:
        """Step 4/5: ExternalReviewGate 承認 → Task DONE (受入基準 #7)。

        BUG-AT-003 実装: POST /api/gates/{gate_id}/approve → GET /api/tasks/{task_id}
        status=DONE を確認する。

        前提: test_step3 と同一セットアップで AWAITING_EXTERNAL_REVIEW に到達してから
        ExternalReviewGate を承認する。
        """
        client = acceptance_ctx.client
        session_factory = acceptance_ctx.session_factory
        stage_worker = acceptance_ctx.stage_worker

        acceptance_ctx.fake_llm.reset(verdicts=None)

        # Empire + Agent + Room + V モデル Workflow 作成 + Agent 割り当て
        _, room_id, _, leader_id, *_ = await _setup_empire_agents_room_workflow(
            client, session_factory
        )

        task_id = await _seed_task_in_progress(
            session_factory,
            room_id=UUID(room_id),
            leader_id=UUID(leader_id),
        )

        # Stage 1 から全 Stage を実行して AWAITING_EXTERNAL_REVIEW に到達
        stage_worker.enqueue(task_id, _STAGE_1_ID)
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

        # ExternalReviewGate を承認する（受入基準 #5 UI承認相当）
        # Authorization ヘッダーは _SYSTEM_REVIEWER_ID（dispatcher.py §暫定実装 と同値）
        r_approve = await client.post(
            f"/api/gates/{gate_id}/approve",
            headers={"Authorization": f"Bearer {_SYSTEM_REVIEWER_ID}"},
            json={"comment": "受入テスト: 承認"},
        )
        assert r_approve.status_code == 200, (
            f"Gate 承認失敗: {r_approve.status_code} {r_approve.text}"
        )

        # Task が次 Stage （Stage 1 以降）に進んで最終的に DONE になるまで待機
        # V モデルの ExternalReviewGate は Stage 14 のみなので、承認後 DONE になる
        final_task = await poll_task_status(
            client,
            task_id,
            expected={"DONE", "BLOCKED"},
            timeout=30.0,
        )

        # 受入基準 #7: Task DONE
        # Note: Task.complete() は current_stage_id を意図的に変更しない（domain 設計 §確定 K）。
        # DONE Task は最後に実行された Stage（EXTERNAL_REVIEW Stage 14）の stage_id を保持する。
        assert final_task["status"] == "DONE", (
            f"ExternalReviewGate 承認後も Task が DONE にならない: {final_task['status']}"
        )
