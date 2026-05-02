"""StageExecutorService + StageWorker ユニットテスト（TC-UT-ME-101〜701）。

設計書: docs/features/stage-executor/application/test-design.md
対象: REQ-ME-001〜007 / MSG-ME-001〜004 / §確定 A〜H / 脅威 T1〜T4
Issue: #163 feat(M5-A): stage-executorサービス実装
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from bakufu.domain.value_objects import StageKind, TaskStatus
from bakufu.domain.value_objects.chat_result import ChatResult

from tests.factories.agent import make_agent
from tests.factories.llm_provider_error import (
    make_auth_error,
    make_empty_response_error,
    make_process_error,
    make_rate_limited_error,
    make_session_lost_error,
    make_timeout_error,
)
from tests.factories.room import make_room
from tests.factories.stub_llm_provider import make_stub_llm_provider, make_stub_llm_provider_raises
from tests.factories.task import make_blocked_task, make_in_progress_task, make_task
from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# 共通フィクスチャ・ユーティリティ
# ---------------------------------------------------------------------------

_SECRET_KEY = "sk-ant-api03-" + "A" * 40  # masking §確定H T1 用


@pytest.fixture(autouse=True)
def _init_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    """masking を初期化する（T1 検証に必要）。

    autouse: 全テストで masking.mask() が呼べる状態にする。
    デフォルトは API キーなし → マスキングは regex パターンのみ有効。
    """
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


def _make_mock_session() -> MagicMock:
    """``async with session.begin():`` をサポートするモックセッションを生成する。

    ``MagicMock().begin.return_value`` に ``__aenter__`` / ``__aexit__`` を設定して
    非同期コンテキストマネージャとして動作させる（test_deliverable_template_service.py 踏襲）。
    """
    mock_session = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _make_service(
    *,
    task_repo: AsyncMock | None = None,
    workflow_repo: AsyncMock | None = None,
    agent_repo: AsyncMock | None = None,
    room_repo: AsyncMock | None = None,
    session: MagicMock | None = None,
    llm_provider: object | None = None,
    internal_review_port: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
    enqueue_fn: MagicMock | None = None,
) -> object:
    """StageExecutorService を構築するファクトリ。

    省略した引数は適切なデフォルトモックで補う。
    """
    from bakufu.application.services.stage_executor_service import StageExecutorService

    return StageExecutorService(
        task_repo=task_repo if task_repo is not None else AsyncMock(),
        workflow_repo=workflow_repo if workflow_repo is not None else AsyncMock(),
        agent_repo=agent_repo if agent_repo is not None else AsyncMock(),
        room_repo=room_repo if room_repo is not None else AsyncMock(),
        session=session if session is not None else _make_mock_session(),
        llm_provider=llm_provider if llm_provider is not None else AsyncMock(),
        internal_review_port=(
            internal_review_port if internal_review_port is not None else AsyncMock()
        ),
        event_bus=event_bus if event_bus is not None else AsyncMock(),
        enqueue_fn=enqueue_fn if enqueue_fn is not None else MagicMock(),
    )


def _setup_work_stage_context(
    task_repo: AsyncMock,
    workflow_repo: AsyncMock,
    agent_repo: AsyncMock,
    room_repo: AsyncMock,
    *,
    stage_kind: StageKind = StageKind.WORK,
    with_next_stage: bool = False,
) -> tuple[object, object, object, object]:
    """WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW Stage のコンテキストを設定する。

    Returns:
        (task, stage, task_id, stage_id)
    """
    stage_id = uuid4()
    workflow_id = uuid4()
    room_id = uuid4()
    agent_id = uuid4()

    # notify_channels は EXTERNAL_REVIEW に必須（make_stage がデフォルトで設定）
    stage = make_stage(stage_id=stage_id, kind=stage_kind)

    if with_next_stage:
        next_stage_id = uuid4()
        next_stage = make_stage(stage_id=next_stage_id, kind=StageKind.WORK)
        transition = make_transition(from_stage_id=stage_id, to_stage_id=next_stage_id)
        workflow = make_workflow(
            workflow_id=workflow_id,
            stages=[stage, next_stage],
            transitions=[transition],
            entry_stage_id=stage_id,
        )
    else:
        workflow = make_workflow(
            workflow_id=workflow_id,
            stages=[stage],
            entry_stage_id=stage_id,
        )

    room = make_room(room_id=room_id, workflow_id=workflow_id)
    agent = make_agent(agent_id=agent_id)
    task = make_in_progress_task(
        current_stage_id=stage_id,
        room_id=room_id,
        assigned_agent_ids=[agent_id],
    )

    task_repo.find_by_id.return_value = task
    room_repo.find_by_id.return_value = room
    workflow_repo.find_by_id.return_value = workflow
    agent_repo.find_by_id.return_value = agent

    return task, stage, task.id, stage_id


# ---------------------------------------------------------------------------
# REQ-ME-001: WORK Stage LLM 実行
# ---------------------------------------------------------------------------


class TestDispatchStageWorkBranch:
    """TC-UT-ME-101〜107: dispatch_stage() WORK 分岐。"""

    async def test_tc_ut_me_101_llm_called_once(self) -> None:
        """TC-UT-ME-101: WORK Stage 正常系 — LLMProviderPort.chat() が 1 回呼ばれる。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()
        event_bus = AsyncMock()
        enqueue_fn = MagicMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        chat_result = ChatResult(response="test deliverable", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
            event_bus=event_bus,
            enqueue_fn=enqueue_fn,
        )

        from bakufu.application.services.stage_executor_service import StageExecutorService

        assert isinstance(service, StageExecutorService)

        await service.dispatch_stage(task_id, stage_id)

        llm_provider.chat.assert_awaited_once()
        task_repo.save.assert_awaited_once()

    async def test_tc_ut_me_102_session_id_equals_stage_id(self) -> None:
        """TC-UT-ME-102: §確定 D — chat() に渡される session_id が Stage ID の文字列に一致する。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        chat_result = ChatResult(response="result", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        call_kwargs = llm_provider.chat.call_args.kwargs
        assert call_kwargs["session_id"] == str(stage_id), (
            f"session_id={call_kwargs['session_id']!r} != stage_id={stage_id!r}"
        )

    async def test_tc_ut_me_103_deliverable_masked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-ME-103: T1 — deliverable は masking gateway 通過後に commit される。

        シークレットパターンを含む LLM 応答の body_markdown がマスクされることを確認。
        """
        from bakufu.infrastructure.security import masking

        monkeypatch.setenv("ANTHROPIC_API_KEY", _SECRET_KEY)
        masking.init()

        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        raw_response = f"Analysis complete. Key used: {_SECRET_KEY}"
        chat_result = ChatResult(response=raw_response, session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        # deliverables は dict[StageId, Deliverable]
        assert saved_task.deliverables, "deliverable が保存されていない"
        for deliverable in saved_task.deliverables.values():
            assert _SECRET_KEY not in deliverable.body_markdown, (
                f"シークレット原文が deliverable に混入している: {deliverable.body_markdown!r}"
            )

    async def test_tc_ut_me_104_next_stage_enqueue(self) -> None:
        """TC-UT-ME-104: 次 Stage あり → advance_to_next() + StageWorker.enqueue() が呼ばれる。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()
        enqueue_fn = MagicMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo, with_next_stage=True
        )

        # Workflow から next_stage_id を取得
        workflow = workflow_repo.find_by_id.return_value
        transition = workflow.transitions[0]
        next_stage_id = transition.to_stage_id

        chat_result = ChatResult(response="result", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
            enqueue_fn=enqueue_fn,
        )

        await service.dispatch_stage(task_id, stage_id)

        enqueue_fn.assert_called_once()
        _, enqueued_stage_id = enqueue_fn.call_args[0]
        assert enqueued_stage_id == next_stage_id, (
            f"次 Stage={next_stage_id} ではなく {enqueued_stage_id} がエンキューされた"
        )

    async def test_tc_ut_me_105_terminal_stage_complete(self) -> None:
        """TC-UT-ME-105: 終端 Stage → Task.complete() が呼ばれる。enqueue_fn は呼ばれない。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()
        enqueue_fn = MagicMock()

        # with_next_stage=False → 単一 Stage Workflow（次 Stage なし）
        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo, with_next_stage=False
        )

        chat_result = ChatResult(response="final result", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
            enqueue_fn=enqueue_fn,
        )

        await service.dispatch_stage(task_id, stage_id)

        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.DONE, (
            f"終端 Stage で DONE にならなかった: {saved_task.status}"
        )
        enqueue_fn.assert_not_called()

    async def test_tc_ut_me_106_subprocess_env_no_aws_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-ME-106: T2 — chat() 呼び出し引数に env dict / AWS_ACCESS_KEY_ID が含まれない。

        StageExecutorService は AWS_ACCESS_KEY_ID を chat() に渡さないことを確認する。
        （subprocess の環境変数フィルタリングは LLM provider 層の責務だが、
        Service がキーを伝達しないことを回帰防止として検証する。）
        """
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")

        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        chat_result = ChatResult(response="result", session_id=None)
        llm_provider = make_stub_llm_provider(responses=[chat_result])

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        call_kwargs = llm_provider.chat.call_args.kwargs
        # chat() に env / AWS_ACCESS_KEY_ID キーワード引数が含まれないことを確認
        assert "env" not in call_kwargs, f"chat() に env が渡されている: {call_kwargs}"
        assert "AWS_ACCESS_KEY_ID" not in call_kwargs, (
            f"chat() に AWS_ACCESS_KEY_ID が渡されている: {call_kwargs}"
        )

    async def test_tc_ut_me_107_fail_fast_not_in_progress(self) -> None:
        """TC-UT-ME-107: §確定 F — Task.status ≠ IN_PROGRESS → ValueError を raise。

        Option A 採用（ヘルスバーグ査読）: chat() は呼ばれない。ValueError が送出される。
        StageWorker の _dispatch_and_release が例外を捕捉して次キューアイテムへ進む。
        """
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        # DONE Task をロードさせる
        stage_id = uuid4()
        workflow_id = uuid4()
        room_id = uuid4()
        stage = make_stage(stage_id=stage_id, kind=StageKind.WORK)
        workflow = make_workflow(
            workflow_id=workflow_id, stages=[stage], entry_stage_id=stage_id
        )
        room = make_room(room_id=room_id, workflow_id=workflow_id)

        done_task = make_task(
            status=TaskStatus.DONE,
            current_stage_id=stage_id,
            room_id=room_id,
            assigned_agent_ids=[uuid4()],
        )

        task_repo.find_by_id.return_value = done_task
        room_repo.find_by_id.return_value = room
        workflow_repo.find_by_id.return_value = workflow

        llm_provider = AsyncMock()

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        # Fail Fast: status ≠ IN_PROGRESS → ValueError（§確定 F / Option A）
        with pytest.raises(ValueError, match="is not IN_PROGRESS"):
            await service.dispatch_stage(done_task.id, stage_id)

        llm_provider.chat.assert_not_called()
        task_repo.save.assert_not_called()


# ---------------------------------------------------------------------------
# REQ-ME-002: INTERNAL_REVIEW Stage 委譲
# ---------------------------------------------------------------------------


class TestDispatchStageInternalReview:
    """TC-UT-ME-201〜202: dispatch_stage() INTERNAL_REVIEW 分岐。"""

    async def test_tc_ut_me_201_internal_review_port_called(self) -> None:
        """TC-UT-ME-201: INTERNAL_REVIEW Stage → Port.execute() が 1 回呼ばれる。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()
        internal_review_port = AsyncMock()
        llm_provider = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo,
            workflow_repo,
            agent_repo,
            room_repo,
            stage_kind=StageKind.INTERNAL_REVIEW,
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            internal_review_port=internal_review_port,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        internal_review_port.execute.assert_awaited_once()
        llm_provider.chat.assert_not_called()

    async def test_tc_ut_me_202_port_exception_blocks_task_and_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-UT-ME-202: Port.execute() 例外 → Task.block() + MSG-ME-002 文言ログ。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()
        internal_review_port = AsyncMock()
        internal_review_port.execute.side_effect = RuntimeError("gate execution failed")

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo,
            workflow_repo,
            agent_repo,
            room_repo,
            stage_kind=StageKind.INTERNAL_REVIEW,
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            internal_review_port=internal_review_port,
        )

        with caplog.at_level(
            logging.ERROR, logger="bakufu.application.services.stage_executor_service"
        ):
            await service.dispatch_stage(task_id, stage_id)

        # Task.block() が呼ばれていること（save() に BLOCKED Task が渡される）
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.BLOCKED, (
            f"BLOCKED にならなかった: {saved_task.status}"
        )

        # MSG-ME-002 文言（静的照合）
        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any(
            "[FAIL] Internal review gate execution failed:" in msg for msg in error_messages
        ), f"MSG-ME-002 ログが見つからない。実際: {error_messages}"


# ---------------------------------------------------------------------------
# REQ-ME-003: EXTERNAL_REVIEW Stage 遷移
# ---------------------------------------------------------------------------


class TestDispatchStageExternalReview:
    """TC-UT-ME-301: dispatch_stage() EXTERNAL_REVIEW 分岐。"""

    async def test_tc_ut_me_301_external_review_requested(self) -> None:
        """TC-UT-ME-301: EXTERNAL_REVIEW Stage → Task.request_external_review() が呼ばれる。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()
        llm_provider = AsyncMock()
        internal_review_port = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo,
            workflow_repo,
            agent_repo,
            room_repo,
            stage_kind=StageKind.EXTERNAL_REVIEW,
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
            internal_review_port=internal_review_port,
        )

        await service.dispatch_stage(task_id, stage_id)

        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW, (
            f"AWAITING_EXTERNAL_REVIEW にならなかった: {saved_task.status}"
        )
        llm_provider.chat.assert_not_called()
        internal_review_port.execute.assert_not_called()


# ---------------------------------------------------------------------------
# REQ-ME-004: LLM エラー 5 分類 + EmptyResponse → BLOCKED
# ---------------------------------------------------------------------------


class TestLLMErrorHandling:
    """TC-UT-ME-401〜409: LLMProviderError 5 分類 + EmptyResponse の処理。"""

    async def test_tc_ut_me_401_auth_error_immediate_block(self) -> None:
        """TC-UT-ME-401: LLMProviderAuthError → 即 BLOCKED（リトライなし）。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        exc = make_auth_error()
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        # chat() が 1 回のみ呼ばれている（リトライなし）
        assert llm_provider.chat.await_count == 1, (
            f"AuthError で chat() が {llm_provider.chat.await_count} 回呼ばれた（期待: 1 回）"
        )
        # BLOCKED に遷移している
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.BLOCKED

    async def test_tc_ut_me_402_msg_me_001_log_text(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-UT-ME-402: MSG-ME-001 — "[FAIL] Stage execution failed:" と
        "bakufu admin retry-task" が ERROR ログに出る。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        exc = make_auth_error()
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        with caplog.at_level(
            logging.ERROR, logger="bakufu.application.services.stage_executor_service"
        ):
            await service.dispatch_stage(task_id, stage_id)

        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("[FAIL] Stage execution failed:" in msg for msg in error_messages), (
            f"MSG-ME-001 '[FAIL] Stage execution failed:' が見つからない: {error_messages}"
        )
        assert any("bakufu admin retry-task" in msg for msg in error_messages), (
            f"MSG-ME-001 'bakufu admin retry-task' が見つからない: {error_messages}"
        )

    async def test_tc_ut_me_403_session_lost_retry_success(self) -> None:
        """TC-UT-ME-403: LLMProviderSessionLostError → 1 回リトライ → 成功。

        chat() が 2 回呼ばれる。Task.block() は呼ばれない。
        """
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        # 1 回目: SessionLost → 2 回目: 成功
        llm_provider = AsyncMock()
        llm_provider.chat = AsyncMock(
            side_effect=[
                make_session_lost_error(),
                ChatResult(response="retry result", session_id=None),
            ]
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        assert llm_provider.chat.await_count == 2, (
            f"chat() が {llm_provider.chat.await_count} 回呼ばれた（期待: 2 回）"
        )
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status != TaskStatus.BLOCKED, (
            "SessionLost → リトライ成功なのに BLOCKED になっている"
        )

    async def test_tc_ut_me_404_session_lost_retry_fail_blocks(self) -> None:
        """TC-UT-ME-404: LLMProviderSessionLostError → 1 回リトライ → 失敗 → BLOCKED。

        chat() が 2 回呼ばれる。
        """
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        # 1 回目: SessionLost → 2 回目: も SessionLost
        llm_provider = AsyncMock()
        llm_provider.chat = AsyncMock(
            side_effect=[
                make_session_lost_error(),
                make_session_lost_error(),
            ]
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        assert llm_provider.chat.await_count == 2, (
            f"chat() が {llm_provider.chat.await_count} 回呼ばれた（期待: 2 回）"
        )
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.BLOCKED

    async def test_tc_ut_me_405_rate_limited_backoff_3_success(self) -> None:
        """TC-UT-ME-405: LLMProviderRateLimitedError → backoff 3 回 → 成功。

        chat() が 4 回呼ばれる（初回 + backoff 3 回）。
        asyncio.sleep はパッチして実際の待機時間をスキップ。
        """
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        # 1 回目: RateLimited → 2: RateLimited → 3: RateLimited → 4: 成功
        llm_provider = AsyncMock()
        llm_provider.chat = AsyncMock(
            side_effect=[
                make_rate_limited_error(),
                make_rate_limited_error(),
                make_rate_limited_error(),
                ChatResult(response="rate limit gone", session_id=None),
            ]
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        with patch(
            "bakufu.application.services.stage_executor_service._error_handler.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await service.dispatch_stage(task_id, stage_id)

        assert llm_provider.chat.await_count == 4, (
            f"chat() が {llm_provider.chat.await_count} 回呼ばれた（期待: 4 回）"
        )
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status != TaskStatus.BLOCKED

    async def test_tc_ut_me_406_last_error_masked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-ME-406: T1 — last_error は masking gateway 通過済み。

        シークレットを含む AuthError メッセージが last_error に raw で保存されない。
        """
        from bakufu.infrastructure.security import masking

        monkeypatch.setenv("ANTHROPIC_API_KEY", _SECRET_KEY)
        masking.init()

        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        # エラーメッセージにシークレットを含める
        exc = make_auth_error(message=f"auth failed with key {_SECRET_KEY}")
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.last_error is not None
        assert _SECRET_KEY not in saved_task.last_error, (
            f"シークレット原文が last_error に含まれている: {saved_task.last_error!r}"
        )

    async def test_tc_ut_me_407_process_error_immediate_block(self) -> None:
        """TC-UT-ME-407: LLMProviderProcessError → 即 BLOCKED（Unknown catch-all）。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        exc = make_process_error()
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        assert llm_provider.chat.await_count == 1
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.BLOCKED

    async def test_tc_ut_me_408_empty_response_immediate_block(self) -> None:
        """TC-UT-ME-408: LLMProviderEmptyResponseError → 即 BLOCKED（独立保持、リトライなし）。"""
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        exc = make_empty_response_error()
        llm_provider = make_stub_llm_provider_raises(exc=exc)

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        assert llm_provider.chat.await_count == 1
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.BLOCKED

    async def test_tc_ut_me_409_timeout_merges_to_session_lost_retry(self) -> None:
        """TC-UT-ME-409: LLMProviderTimeoutError → SessionLost 相当 1 回リトライ。

        §確定 H: Timeout は SessionLost に合流する。chat() が 2 回呼ばれる。
        """
        task_repo = AsyncMock()
        workflow_repo = AsyncMock()
        agent_repo = AsyncMock()
        room_repo = AsyncMock()

        _task, _stage, task_id, stage_id = _setup_work_stage_context(
            task_repo, workflow_repo, agent_repo, room_repo
        )

        # 1 回目: Timeout → 2 回目: 成功
        llm_provider = AsyncMock()
        llm_provider.chat = AsyncMock(
            side_effect=[
                make_timeout_error(),
                ChatResult(response="retry after timeout", session_id=None),
            ]
        )

        service = _make_service(
            task_repo=task_repo,
            workflow_repo=workflow_repo,
            agent_repo=agent_repo,
            room_repo=room_repo,
            llm_provider=llm_provider,
        )

        await service.dispatch_stage(task_id, stage_id)

        assert llm_provider.chat.await_count == 2, (
            f"Timeout リトライで chat() が {llm_provider.chat.await_count} 回呼ばれた（期待: 2 回）"
        )
        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status != TaskStatus.BLOCKED


# ---------------------------------------------------------------------------
# REQ-ME-005: BLOCKED Task retry エントリポイント
# ---------------------------------------------------------------------------


class TestRetryBlockedTask:
    """TC-UT-ME-501〜503: retry_blocked_task() のフェイルファスト + 正常系。"""

    async def test_tc_ut_me_501_retry_blocked_normal(self) -> None:
        """TC-UT-ME-501: 正常系 — Task.unblock_retry() + enqueue() が呼ばれる。"""
        task_repo = AsyncMock()
        event_bus = AsyncMock()
        enqueue_fn = MagicMock()

        blocked_task = make_blocked_task()
        task_repo.find_by_id.return_value = blocked_task

        service = _make_service(
            task_repo=task_repo,
            event_bus=event_bus,
            enqueue_fn=enqueue_fn,
        )

        await service.retry_blocked_task(blocked_task.id)

        task_repo.save.assert_awaited_once()
        saved_task = task_repo.save.call_args[0][0]
        assert saved_task.status == TaskStatus.IN_PROGRESS, (
            f"unblock_retry 後が IN_PROGRESS にならなかった: {saved_task.status}"
        )
        enqueue_fn.assert_called_once()

    async def test_tc_ut_me_502_msg_me_003_not_blocked(self) -> None:
        """TC-UT-ME-502: §確定 F — Task.status ≠ BLOCKED → MSG-ME-003 ValueError。"""
        task_repo = AsyncMock()

        in_progress_task = make_in_progress_task()
        task_repo.find_by_id.return_value = in_progress_task

        service = _make_service(task_repo=task_repo)

        with pytest.raises(ValueError) as exc_info:
            await service.retry_blocked_task(in_progress_task.id)

        error_text = str(exc_info.value)
        assert "[FAIL] Task" in error_text, f"MSG-ME-003 '[FAIL] Task' が含まれない: {error_text}"
        assert "is not BLOCKED" in error_text, (
            f"MSG-ME-003 'is not BLOCKED' が含まれない: {error_text}"
        )

    async def test_tc_ut_me_503_msg_me_004_task_not_found(self) -> None:
        """TC-UT-ME-503: Task 不在 → MSG-ME-004 ValueError。"""
        task_repo = AsyncMock()
        task_repo.find_by_id.return_value = None

        service = _make_service(task_repo=task_repo)

        with pytest.raises(ValueError) as exc_info:
            await service.retry_blocked_task(uuid4())

        error_text = str(exc_info.value)
        assert "[FAIL] Task" in error_text, f"MSG-ME-004 '[FAIL] Task' が含まれない: {error_text}"
        assert "not found" in error_text, (
            f"MSG-ME-004 'not found' が含まれない: {error_text}"
        )


# ---------------------------------------------------------------------------
# REQ-ME-006: StageWorker 並行数制御
# ---------------------------------------------------------------------------


class TestStageWorker:
    """TC-UT-ME-601〜603: StageWorker enqueue → dispatch サイクル + Semaphore 制御。"""

    def _make_mock_session_factory(self) -> MagicMock:
        """async with session_factory() as session: をサポートするモックを生成する。"""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        # begin() も async with で使えるようにする（_build_service 内部で使用される場合）
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        session_factory = MagicMock()
        session_factory.return_value = mock_session
        return session_factory

    async def test_tc_ut_me_601_enqueue_triggers_dispatch(self) -> None:
        """TC-UT-ME-601: enqueue() → dispatch_stage() が 1 回呼ばれる。"""
        from bakufu.infrastructure.worker.stage_worker import StageWorker

        task_id = uuid4()
        stage_id = uuid4()
        dispatch_called = asyncio.Event()

        session_factory = self._make_mock_session_factory()
        mock_service = AsyncMock()

        async def _mark_called(t: object, s: object) -> None:
            dispatch_called.set()

        mock_service.dispatch_stage.side_effect = _mark_called

        worker = StageWorker(
            session_factory=session_factory,
            llm_provider=AsyncMock(),
            event_bus=AsyncMock(),
            max_concurrent=1,
        )
        worker._build_service = MagicMock(return_value=mock_service)

        worker.start()
        worker.enqueue(task_id, stage_id)

        try:
            await asyncio.wait_for(dispatch_called.wait(), timeout=2.0)
        finally:
            await worker.stop()

        mock_service.dispatch_stage.assert_awaited_once_with(task_id, stage_id)

    async def test_tc_ut_me_602_semaphore_released_after_dispatch(self) -> None:
        """TC-UT-ME-602: §確定 A — dispatch 完了後に Semaphore が release される。"""
        from bakufu.infrastructure.worker.stage_worker import StageWorker

        task_id = uuid4()
        stage_id = uuid4()
        dispatch_done = asyncio.Event()

        session_factory = self._make_mock_session_factory()
        mock_service = AsyncMock()

        async def _dispatch_and_signal(t: object, s: object) -> None:
            dispatch_done.set()

        mock_service.dispatch_stage.side_effect = _dispatch_and_signal

        worker = StageWorker(
            session_factory=session_factory,
            llm_provider=AsyncMock(),
            event_bus=AsyncMock(),
            max_concurrent=1,
        )
        worker._build_service = MagicMock(return_value=mock_service)

        initial_semaphore_value = worker._semaphore._value

        worker.start()
        worker.enqueue(task_id, stage_id)

        await asyncio.wait_for(dispatch_done.wait(), timeout=2.0)
        # dispatch が完了したら semaphore は release されるはず
        # 少し待って _dispatch_and_release の finally が走るのを待つ
        await asyncio.sleep(0.05)

        await worker.stop()

        assert worker._semaphore._value == initial_semaphore_value, (
            f"Semaphore が release されていない: _value={worker._semaphore._value}, "
            f"initial={initial_semaphore_value}"
        )

    async def test_tc_ut_me_603_semaphore_released_on_exception(self) -> None:
        """TC-UT-ME-603: dispatch_stage() 例外 → Semaphore release（リーク防止）。"""
        from bakufu.infrastructure.worker.stage_worker import StageWorker

        task_id = uuid4()
        stage_id = uuid4()
        dispatch_done = asyncio.Event()

        session_factory = self._make_mock_session_factory()
        mock_service = AsyncMock()

        async def _raise_and_signal(t: object, s: object) -> None:
            dispatch_done.set()
            raise RuntimeError("synthetic dispatch error for TC-UT-ME-603")

        mock_service.dispatch_stage.side_effect = _raise_and_signal

        worker = StageWorker(
            session_factory=session_factory,
            llm_provider=AsyncMock(),
            event_bus=AsyncMock(),
            max_concurrent=1,
        )
        worker._build_service = MagicMock(return_value=mock_service)

        initial_semaphore_value = worker._semaphore._value

        worker.start()
        worker.enqueue(task_id, stage_id)

        await asyncio.wait_for(dispatch_done.wait(), timeout=2.0)
        await asyncio.sleep(0.05)

        await worker.stop()

        # 例外後も Semaphore は release されている（ロック状態でない）
        assert worker._semaphore._value == initial_semaphore_value, (
            f"例外後 Semaphore がリークしている: _value={worker._semaphore._value}, "
            f"initial={initial_semaphore_value}"
        )


# ---------------------------------------------------------------------------
# REQ-ME-007: InternalReviewGateExecutorPort 定義
# ---------------------------------------------------------------------------


class TestInternalReviewGateExecutorPort:
    """TC-UT-ME-701: InternalReviewGateExecutorPort が typing.Protocol / runtime_checkable。"""

    async def test_tc_ut_me_701_protocol_runtime_checkable(self) -> None:
        """TC-UT-ME-701: Port を実装した stub が isinstance チェックを通過する。

        Protocol が @runtime_checkable デコレータを持つことを確認（§確定 G）。
        """
        from typing import Protocol

        from bakufu.application.ports.internal_review_gate_executor_port import (
            InternalReviewGateExecutorPort,
        )

        # Protocol のサブクラスであることを確認
        assert issubclass(InternalReviewGateExecutorPort, Protocol), (
            "InternalReviewGateExecutorPort が typing.Protocol ではない"
        )

        # runtime_checkable デコレータが付いていることを確認
        assert hasattr(InternalReviewGateExecutorPort, "__protocol_attrs__") or hasattr(
            InternalReviewGateExecutorPort, "_is_protocol"
        ), "runtime_checkable が付いていない"

        # execute メソッドを持つ stub が isinstance を通過する
        class _StubPort:
            async def execute(
                self,
                task_id: object,
                stage_id: object,
                required_gate_roles: frozenset,  # type: ignore[type-arg]
            ) -> None:
                pass

        stub = _StubPort()
        assert isinstance(stub, InternalReviewGateExecutorPort), (
            "execute() メソッドを持つ stub が isinstance チェックを通過しない"
        )
