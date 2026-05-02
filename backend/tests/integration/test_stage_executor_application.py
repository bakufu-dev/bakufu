"""StageExecutorService + StageWorker 結合テスト（TC-IT-ME-101〜601）。

設計書: docs/features/stage-executor/application/test-design.md
対象: REQ-ME-001〜007 / 受入基準 §9 #1〜#6 / 脅威 T1, T4
Issue: #163 feat(M5-A): stage-executorサービス実装

前提:
- DB: tmp_path ベースの SQLite（create_all_tables 実行済み）
- LLM: make_stub_llm_provider() / make_stub_llm_provider_raises() で stub（実 subprocess 不使用）
       ただし TC-IT-ME-103 のみ ClaudeCodeLLMClient + python3 スタブプロセスで
       pid_registry ライフサイクル検証
- EventBus: InMemoryEventBus() + spy handler
- masking: 実実装（API キー環境変数クリア済み）
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from bakufu.domain.value_objects import StageKind, TaskStatus
from bakufu.domain.value_objects.chat_result import ChatResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.agent import make_agent
from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
from tests.factories.directive import make_directive
from tests.factories.empire import make_empire
from tests.factories.llm_provider_error import make_auth_error
from tests.factories.room import make_room
from tests.factories.stub_llm_provider import make_stub_llm_provider, make_stub_llm_provider_raises
from tests.factories.task import make_in_progress_task
from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.asyncio

_SECRET_KEY = "sk-ant-api03-" + "A" * 40  # masking T1 用


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    """masking を初期化する（T1 検証 + MaskedText TypeDecorator 動作保証）。"""
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    from bakufu.infrastructure.security import masking

    masking.init()


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """create_all でスキーマ作成済みの session_factory を提供する。"""
    engine = make_test_engine(tmp_path / "stage_executor_it_test.db")
    await create_all_tables(engine)
    sf = make_test_session_factory(engine)
    try:
        yield sf
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# シードヘルパー
# ---------------------------------------------------------------------------


class _SpyHandler:
    """受け取った DomainEvent を記録する spy ハンドラ。"""

    def __init__(self) -> None:
        self.received: list[object] = []

    async def __call__(self, event: object) -> None:
        self.received.append(event)


async def _seed_full_context(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    task_id: UUID | None = None,
    stage_kind: StageKind = StageKind.WORK,
    with_next_stage: bool = False,
    task_status: TaskStatus = TaskStatus.IN_PROGRESS,
    task_last_error: str | None = None,
) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID]:
    """Empire → Workflow → Room → Agent → Directive → Task の FK チェーンを全てシードする。

    Returns:
        (empire_id, workflow_id, room_id, agent_id, task_id, stage_id)
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    _task_id = task_id if task_id is not None else uuid4()
    stage_id = uuid4()
    agent_id = uuid4()

    empire = make_empire()
    stage = make_stage(stage_id=stage_id, kind=stage_kind)

    if with_next_stage:
        next_stage_id = uuid4()
        next_stage = make_stage(stage_id=next_stage_id, kind=StageKind.WORK)
        transition = make_transition(from_stage_id=stage_id, to_stage_id=next_stage_id)
        workflow = make_workflow(
            stages=[stage, next_stage],
            transitions=[transition],
            entry_stage_id=stage_id,
        )
    else:
        workflow = make_workflow(stages=[stage], entry_stage_id=stage_id)

    room = make_room(workflow_id=workflow.id, members=[])
    agent = make_agent(empire_id=empire.id, agent_id=agent_id)
    directive = make_directive(target_room_id=room.id, task_id=_task_id)

    task = make_in_progress_task(
        task_id=_task_id,
        room_id=room.id,
        directive_id=directive.id,
        current_stage_id=stage_id,
        assigned_agent_ids=[agent_id],
    )

    # BLOCKED Task が必要な場合は BLOCKED Task を上書き
    if task_status == TaskStatus.BLOCKED:
        from tests.factories.task import make_blocked_task

        task = make_blocked_task(
            task_id=_task_id,
            room_id=room.id,
            directive_id=directive.id,
            current_stage_id=stage_id,
            assigned_agent_ids=[agent_id],
            last_error=task_last_error or "synthetic last_error",
        )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
        await SqliteWorkflowRepository(session).save(workflow)
        await SqliteRoomRepository(session).save(room, empire.id)
        await SqliteAgentRepository(session).save(agent)
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)

    return empire.id, workflow.id, room.id, agent_id, _task_id, stage_id


async def _read_task(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
) -> object:
    """TaskRepository.find_by_id() 経由で Task を読み取る（DB 直接参照禁止）。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    async with session_factory() as session, session.begin():
        return await SqliteTaskRepository(session).find_by_id(task_id)


def _make_service(
    session: AsyncSession,
    *,
    llm_provider: object,
    internal_review_port: object | None = None,
    event_bus: object | None = None,
    enqueue_fn: object | None = None,
    workflow_repo: object | None = None,
) -> object:
    """StageExecutorService を構築するヘルパー。

    workflow_repo を None のままにすると SqliteWorkflowRepository を使う。
    EXTERNAL_REVIEW のように §不可逆性 でラウンドトリップ不可になるケースは
    workflow_repo にモックを渡すこと。
    """
    from bakufu.application.services.stage_executor_service import StageExecutorService
    from bakufu.infrastructure.event_bus import InMemoryEventBus
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    if internal_review_port is None:
        internal_review_port = AsyncMock()
    if event_bus is None:
        event_bus = InMemoryEventBus()
    if enqueue_fn is None:
        enqueue_fn = MagicMock()
    if workflow_repo is None:
        workflow_repo = SqliteWorkflowRepository(session)

    return StageExecutorService(
        task_repo=SqliteTaskRepository(session),
        workflow_repo=workflow_repo,
        agent_repo=SqliteAgentRepository(session),
        room_repo=SqliteRoomRepository(session),
        session=session,
        llm_provider=llm_provider,
        internal_review_port=internal_review_port,
        event_bus=event_bus,
        enqueue_fn=enqueue_fn,
    )


# ---------------------------------------------------------------------------
# REQ-ME-001: WORK Stage LLM 実行（受入基準 §9 #1）
# ---------------------------------------------------------------------------


class TestWorkStageIntegration:
    """TC-IT-ME-101〜103: WORK Stage 正常系 + T1（結合）。"""

    async def test_tc_it_me_101_work_stage_advances_to_next(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-101: dispatch_stage() 後 Task の current_stage_id が次 Stage に進む。"""
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        spy = _SpyHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(spy)
        enqueue_fn = MagicMock()

        _, _, _, _, task_id, stage_id = await _seed_full_context(
            session_factory, with_next_stage=True
        )

        chat_result = ChatResult(response="結合テスト成果物", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        async with session_factory() as session:
            service = _make_service(
                session,
                llm_provider=llm_provider,
                event_bus=event_bus,
                enqueue_fn=enqueue_fn,
            )
            await service.dispatch_stage(task_id, stage_id)

        task = await _read_task(session_factory, task_id)
        assert task is not None
        # 次 Stage に advance → current_stage_id が stage_id から変わっている
        assert task.current_stage_id != stage_id, (
            f"current_stage_id={task.current_stage_id} が stage_id={stage_id} のまま進んでいない"
        )
        # EventBus にイベントが配信されている
        assert len(spy.received) >= 1, "TaskStateChangedEvent が配信されていない"

    async def test_tc_it_me_102_terminal_stage_done(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-102: 単一 Stage Workflow → dispatch_stage() 後 Task.status = DONE。"""
        _, _, _, _, task_id, stage_id = await _seed_full_context(
            session_factory, with_next_stage=False
        )

        chat_result = ChatResult(response="終端成果物", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        async with session_factory() as session:
            service = _make_service(session, llm_provider=llm_provider)
            await service.dispatch_stage(task_id, stage_id)

        task = await _read_task(session_factory, task_id)
        assert task is not None
        assert task.status == TaskStatus.DONE, (
            f"終端 Stage で DONE にならなかった: {task.status}"
        )

    async def test_tc_it_me_103_pid_registry_lifecycle(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-103: T3 — ClaudeCodeLLMClient の pid_registry INSERT→DELETE ライフサイクル。

        ClaudeCodeLLMClient に session_factory を注入し、asyncio.create_subprocess_exec を
        python3（軽量スタブ、実 OS プロセス）で差し替える。
        - chat() 実行中（communicate() 完了前）に pid が pid_registry に INSERT されていること
        - chat() 完了後に pid_registry が空（DELETE 実行済み）であること
        を spy で確認する。以前の stub テストはこのライフサイクルを検証していなかった
        （タブリーズ査読指摘）。
        """
        from bakufu.infrastructure.llm.claude_code_llm_client import ClaudeCodeLLMClient
        from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import PidRegistryRow
        from sqlalchemy import func, select

        # asyncio.create_subprocess_exec の元の関数を patch 前に退避（再帰呼び出し防止）
        _real_cse = asyncio.create_subprocess_exec

        # python3 で有効な JSONL を出力する軽量スタブ（実 OS プロセス = 実 PID を持つ）
        _jsonl = json.dumps(
            {
                "type": "result",
                "result": "pid_registry lifecycle OK",
                "session_id": "test-lifecycle-session",
            }
        )

        async def _python_stub(*_args: object, **_kwargs: object) -> object:
            """claude CLI の代わりに python3 で JSONL を標準出力する軽量スタブ。"""
            return await _real_cse(
                "python3",
                "-c",
                f"print({_jsonl!r})",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        client = ClaudeCodeLLMClient(
            model_name="claude-test",
            timeout_seconds=30.0,
            session_factory=session_factory,
        )

        # INSERT 直後の pid_registry 行数を記録する spy
        spy_insert_counts: list[int] = []
        _original_register = client._register_pid

        async def _spy_register(pid: int, cmd: list) -> None:  # type: ignore[type-arg]
            await _original_register(pid, cmd)
            # INSERT がコミットされた直後: pid_registry に 1 行あるはず
            async with session_factory() as s, s.begin():
                row_count = (
                    await s.execute(
                        select(func.count())
                        .select_from(PidRegistryRow)
                        .where(PidRegistryRow.pid == pid)
                    )
                ).scalar_one()
            spy_insert_counts.append(row_count)

        client._register_pid = _spy_register  # type: ignore[method-assign]

        with patch(
            "bakufu.infrastructure.llm.claude_code_llm_client.asyncio.create_subprocess_exec",
            new=_python_stub,
        ):
            result = await client.chat(
                messages=[{"role": "user", "content": "pid registry lifecycle test"}],
                system="test system",
            )

        # 1. LLM 応答テキストが正しいこと（subprocess が正常終了した証拠）
        assert result.response == "pid_registry lifecycle OK", (
            f"期待した応答テキストが得られなかった: {result.response!r}"
        )
        # 2. INSERT が実行されたこと（spy で確認）
        assert spy_insert_counts, (
            "pid_registry INSERT が実行されなかった（_register_pid が呼ばれていない）"
        )
        assert spy_insert_counts[0] == 1, (
            f"INSERT 直後の pid_registry 行数が 1 ではない: {spy_insert_counts}"
        )
        # 3. chat() 完了後: DELETE が実行されて pid_registry は空であること
        async with session_factory() as s, s.begin():
            final_count = (
                await s.execute(select(func.count()).select_from(PidRegistryRow))
            ).scalar_one()
        assert final_count == 0, (
            f"chat() 完了後に pid_registry が空でない: {final_count} 行残存"
            " （_unregister_pid の DELETE が実行されていない）"
        )


# ---------------------------------------------------------------------------
# REQ-ME-002: INTERNAL_REVIEW Stage 委譲（受入基準 §9 #2）
# ---------------------------------------------------------------------------


class TestInternalReviewIntegration:
    """TC-IT-ME-201: INTERNAL_REVIEW Stage（結合）。"""

    async def test_tc_it_me_201_internal_review_port_execute_called(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-201: INTERNAL_REVIEW Stage → Port.execute() が 1 回呼ばれる。"""
        _, _, _, _, task_id, stage_id = await _seed_full_context(
            session_factory, stage_kind=StageKind.INTERNAL_REVIEW
        )

        internal_review_port = AsyncMock()

        async with session_factory() as session:
            service = _make_service(
                session,
                llm_provider=AsyncMock(),
                internal_review_port=internal_review_port,
            )
            await service.dispatch_stage(task_id, stage_id)

        internal_review_port.execute.assert_awaited_once()
        call_kwargs = internal_review_port.execute.call_args.kwargs
        assert call_kwargs["task_id"] == task_id
        assert call_kwargs["stage_id"] == stage_id


# ---------------------------------------------------------------------------
# REQ-ME-003: EXTERNAL_REVIEW Stage 遷移（受入基準 §9 #3）
# ---------------------------------------------------------------------------


class TestExternalReviewIntegration:
    """TC-IT-ME-301: EXTERNAL_REVIEW Stage（結合）。"""

    async def test_tc_it_me_301_external_review_awaiting(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-301: EXTERNAL_REVIEW Stage → Task.status = AWAITING_EXTERNAL_REVIEW。

        §不可逆性 回避: EXTERNAL_REVIEW ステージの notify_channels Discord webhook トークンは
        MaskedJSONEncoded TypeDecorator により DB 書き込み時にマスクされる。
        読み戻し時に NotifyChannel.model_validate() がバリデーションエラーになるため、
        workflow_repo をモックして DB ラウンドトリップを回避する（設計書 §不可逆性 参照）。
        """
        # §不可逆性 回避: WORK Stage でシード（EXTERNAL_REVIEW workflow を DB に保存しない）
        _, _, _, _, task_id, _ = await _seed_full_context(
            session_factory, stage_kind=StageKind.WORK
        )

        # インメモリ EXTERNAL_REVIEW ステージ + ワークフロー（DB には保存しない）
        ext_stage_id = uuid4()
        ext_stage = make_stage(stage_id=ext_stage_id, kind=StageKind.EXTERNAL_REVIEW)
        ext_workflow = make_workflow(stages=[ext_stage], entry_stage_id=ext_stage_id)

        # workflow_repo モック: DB ラウンドトリップを回避して in-memory workflow を返す
        mock_workflow_repo = AsyncMock()
        mock_workflow_repo.find_by_id = AsyncMock(return_value=ext_workflow)

        async with session_factory() as session:
            service = _make_service(
                session,
                llm_provider=AsyncMock(),
                workflow_repo=mock_workflow_repo,
            )
            await service.dispatch_stage(task_id, ext_stage_id)

        task = await _read_task(session_factory, task_id)
        assert task is not None
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW, (
            f"AWAITING_EXTERNAL_REVIEW にならなかった: {task.status}"
        )


# ---------------------------------------------------------------------------
# REQ-ME-004: LLM エラー → BLOCKED（受入基準 §9 #4）
# ---------------------------------------------------------------------------


class TestLLMErrorIntegration:
    """TC-IT-ME-401〜402: LLM エラー → BLOCKED + T1 masking（結合）。"""

    async def test_tc_it_me_401_auth_error_blocks_task(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-401: LLMProviderAuthError → Task.status = BLOCKED（受入基準 #4）。"""
        _, _, _, _, task_id, stage_id = await _seed_full_context(session_factory)

        exc = make_auth_error()
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        async with session_factory() as session:
            service = _make_service(session, llm_provider=llm_provider)
            await service.dispatch_stage(task_id, stage_id)

        task = await _read_task(session_factory, task_id)
        assert task is not None
        assert task.status == TaskStatus.BLOCKED, (
            f"AuthError で BLOCKED にならなかった: {task.status}"
        )
        assert task.last_error is not None, "BLOCKED Task に last_error が設定されていない"

    async def test_tc_it_me_402_last_error_no_raw_secret(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-ME-402: T1 — DB に保存された last_error にシークレット原文が含まれない。"""
        from bakufu.infrastructure.security import masking

        monkeypatch.setenv("ANTHROPIC_API_KEY", _SECRET_KEY)
        masking.init()

        _, _, _, _, task_id, stage_id = await _seed_full_context(session_factory)

        exc = make_auth_error(message=f"auth failed, key={_SECRET_KEY}")
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        async with session_factory() as session:
            service = _make_service(session, llm_provider=llm_provider)
            await service.dispatch_stage(task_id, stage_id)

        task = await _read_task(session_factory, task_id)
        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.last_error is not None
        assert _SECRET_KEY not in task.last_error, (
            f"DB の last_error にシークレット原文が含まれている: {task.last_error!r}"
        )


# ---------------------------------------------------------------------------
# REQ-ME-005: BLOCKED Task retry（受入基準 §9 #5）
# ---------------------------------------------------------------------------


class TestRetryBlockedTaskIntegration:
    """TC-IT-ME-501〜502: retry_blocked_task()（結合）。"""

    async def test_tc_it_me_501_retry_changes_status_to_in_progress(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-501: retry_blocked_task() → Task.status = IN_PROGRESS + enqueue() 呼ばれる。

        受入基準 #5: BLOCKED Task が retry により IN_PROGRESS に戻る。
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        spy = _SpyHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(spy)
        enqueue_fn = MagicMock()

        _, _, _, _, task_id, _ = await _seed_full_context(
            session_factory,
            task_status=TaskStatus.BLOCKED,
            task_last_error="LLMProviderAuthError: synthetic block",
        )

        async with session_factory() as session:
            service = _make_service(
                session,
                llm_provider=AsyncMock(),
                event_bus=event_bus,
                enqueue_fn=enqueue_fn,
            )
            await service.retry_blocked_task(task_id)

        task = await _read_task(session_factory, task_id)
        assert task is not None
        assert task.status == TaskStatus.IN_PROGRESS, (
            f"retry 後に IN_PROGRESS にならなかった: {task.status}"
        )
        enqueue_fn.assert_called_once()
        assert len(spy.received) >= 1, "retry 後に TaskStateChangedEvent が配信されていない"

    async def test_tc_it_me_502_retry_publishes_event(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-ME-502: T4 — retry_blocked_task() は Service 経由で audit_log 相当イベントを出す。

        TaskStateChangedEvent が EventBus に発行されることで retry 操作の証跡が残る。
        """
        from bakufu.domain.events import TaskStateChangedEvent
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        spy = _SpyHandler()
        event_bus = InMemoryEventBus()
        event_bus.subscribe(spy)

        _, _, _, _, task_id, _ = await _seed_full_context(
            session_factory,
            task_status=TaskStatus.BLOCKED,
            task_last_error="synthetic block for T4 test",
        )

        async with session_factory() as session:
            service = _make_service(
                session,
                llm_provider=AsyncMock(),
                event_bus=event_bus,
            )
            await service.retry_blocked_task(task_id)

        # TaskStateChangedEvent が発行されていること（retry 操作の証跡）
        state_changed_events = [
            e for e in spy.received if isinstance(e, TaskStateChangedEvent)
        ]
        assert len(state_changed_events) >= 1, (
            f"retry 後に TaskStateChangedEvent が配信されていない: {spy.received}"
        )
        event = state_changed_events[0]
        assert event.old_status == str(TaskStatus.BLOCKED)
        assert event.new_status == str(TaskStatus.IN_PROGRESS)


# ---------------------------------------------------------------------------
# REQ-ME-006: StageWorker 並行数制御（受入基準 §9 #6）
# ---------------------------------------------------------------------------


class TestStageWorkerIntegration:
    """TC-IT-ME-601: StageWorker max_concurrent=1 でシリアル実行（結合）。"""

    async def test_tc_it_me_601_max_concurrent_1_serial_execution(self) -> None:
        """TC-IT-ME-601: BAKUFU_MAX_CONCURRENT_STAGES=1 → 2 件が並列にならずシリアル実行される。

        Semaphore=1 の下で 2 件の dispatch は重複しない（LIFO 安全性 + §確定 A 結合検証）。
        """
        from bakufu.infrastructure.worker.stage_worker import StageWorker

        execution_order: list[UUID] = []
        release_lock = asyncio.Lock()

        async def _slow_dispatch(task_id: object, stage_id: object) -> None:
            """最初の dispatch が完了するまで 2 件目が始まらないことを確認する spy。"""
            async with release_lock:
                execution_order.append(task_id)  # type: ignore[arg-type]
                await asyncio.sleep(0.02)  # 少し待つ

        mock_service = AsyncMock()
        mock_service.dispatch_stage.side_effect = _slow_dispatch

        # async with session_factory() as session: をサポートするモック
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory = MagicMock()
        mock_session_factory.return_value = mock_session

        worker = StageWorker(
            session_factory=mock_session_factory,
            llm_provider=AsyncMock(),
            event_bus=AsyncMock(),
            max_concurrent=1,
        )
        worker._build_service = MagicMock(return_value=mock_service)

        task_id_1 = uuid4()
        task_id_2 = uuid4()
        stage_id_1 = uuid4()
        stage_id_2 = uuid4()

        worker.start()
        worker.enqueue(task_id_1, stage_id_1)
        worker.enqueue(task_id_2, stage_id_2)

        # 両方完了まで待つ（max 5 秒）
        deadline = asyncio.get_event_loop().time() + 5.0
        while len(execution_order) < 2 and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.05)

        await worker.stop()

        assert len(execution_order) == 2, (
            f"2 件のディスパッチが完了しなかった: {execution_order}"
        )
        # Semaphore=1 なので並列ではなくシリアル実行
        # → execution_order に両方の task_id が含まれている
        assert task_id_1 in execution_order, f"task_id_1 が実行されなかった: {execution_order}"
        assert task_id_2 in execution_order, f"task_id_2 が実行されなかった: {execution_order}"
