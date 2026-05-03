"""InternalReviewGate 結合テスト（TC-IT-IRG-A004〜A009）。

設計書: docs/features/internal-review-gate/application/test-design.md
対象:
  A004 — create_gate() べき等性
  A005 — GateRole 権限なし → UnauthorizedGateRoleError（T1）
  A006 — executor.execute() 並列 LLM 実行 → ALL_APPROVED
  A007 — executor.execute() LLM エラー → 例外再送出
  A008 — リトライ 1 回 → 成功 → Gate 確定
  A009 — 3 回全てツール未呼び出し → REJECTED 強制登録
Issue: #164 feat(M5-B): InternalReviewGate infrastructure実装

前提:
- DB: tmp_path ベースの SQLite（create_all_tables 実行済み）
- LLM: make_stub_llm_provider_with_tools()（実 subprocess 不使用）
- EventBus: InMemoryEventBus()
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.agent import make_agent
from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
from tests.factories.directive import make_directive
from tests.factories.empire import make_empire
from tests.factories.llm_provider_error import make_timeout_error
from tests.factories.room import make_room
from tests.factories.stub_llm_provider import (
    make_stub_llm_provider_with_tools,
    make_stub_llm_provider_with_tools_raises,
    make_text_chat_result,
    make_tool_call_chat_result,
)
from tests.factories.task import make_deliverable, make_in_progress_task
from tests.factories.workflow import make_stage, make_transition, make_workflow

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    """masking 初期化（MaskedText TypeDecorator 動作保証）。"""
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
    engine = make_test_engine(tmp_path / "irg_it_test.db")
    await create_all_tables(engine)
    sf = make_test_session_factory(engine)
    try:
        yield sf
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# シードヘルパー
# ---------------------------------------------------------------------------


async def _seed_irg_context(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    task_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID, UUID]:
    """Empire/Workflow(WORK_A→IR_B→WORK_C)/Room/Agent/Directive/Task をシードする。

    Returns:
        (empire_id, workflow_id, room_id, agent_id, task_id, work_stage_id, ir_stage_id)
    """
    from bakufu.domain.value_objects import StageKind
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
    work_stage_id = uuid4()
    ir_stage_id = uuid4()
    next_work_stage_id = uuid4()
    agent_id = uuid4()

    empire = make_empire()
    work_stage = make_stage(stage_id=work_stage_id, kind=StageKind.WORK, name="WORK_A")
    ir_stage = make_stage(
        stage_id=ir_stage_id, kind=StageKind.INTERNAL_REVIEW, name="INTERNAL_REVIEW_B"
    )
    next_work_stage = make_stage(stage_id=next_work_stage_id, kind=StageKind.WORK, name="WORK_C")
    transition_to_ir = make_transition(from_stage_id=work_stage_id, to_stage_id=ir_stage_id)
    transition_to_next = make_transition(from_stage_id=ir_stage_id, to_stage_id=next_work_stage_id)
    workflow = make_workflow(
        stages=[work_stage, ir_stage, next_work_stage],
        transitions=[transition_to_ir, transition_to_next],
        entry_stage_id=work_stage_id,
    )
    room = make_room(workflow_id=workflow.id, members=[])
    agent = make_agent(empire_id=empire.id, agent_id=agent_id)
    directive = make_directive(target_room_id=room.id, task_id=_task_id)

    # WORK_A が生成した成果物を持つ IN_PROGRESS Task（INTERNAL_REVIEW_B ステージ）
    deliverable = make_deliverable(
        stage_id=work_stage_id,
        body_markdown="# テスト成果物\n\n機能実装が完了しました。",
    )
    task = make_in_progress_task(
        task_id=_task_id,
        room_id=room.id,
        directive_id=directive.id,
        current_stage_id=ir_stage_id,
        assigned_agent_ids=[agent_id],
        deliverables={work_stage_id: deliverable},
    )

    async with session_factory() as session, session.begin():
        await SqliteEmpireRepository(session).save(empire)
        await SqliteWorkflowRepository(session).save(workflow)
        await SqliteRoomRepository(session).save(room, empire.id)
        await SqliteAgentRepository(session).save(agent)
        await SqliteDirectiveRepository(session).save(directive)
        await SqliteTaskRepository(session).save(task)

    return empire.id, workflow.id, room.id, agent_id, _task_id, work_stage_id, ir_stage_id


def _make_review_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> object:
    """InternalReviewService を InMemoryEventBus で構築する。"""
    from bakufu.application.services.internal_review_service import InternalReviewService
    from bakufu.infrastructure.event_bus import InMemoryEventBus
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (
        SqliteInternalReviewGateRepository,
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

    return InternalReviewService(
        session_factory=session_factory,
        gate_repo_factory=SqliteInternalReviewGateRepository,
        task_repo_factory=SqliteTaskRepository,
        workflow_repo_factory=SqliteWorkflowRepository,
        room_repo_factory=SqliteRoomRepository,
        event_bus=InMemoryEventBus(),
    )


def _make_executor(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    llm_provider: object,
    review_svc: object | None = None,
    agent_id: UUID | None = None,
) -> object:
    """InternalReviewGateExecutor を構築する。"""
    from bakufu.infrastructure.reviewers.internal_review_gate_executor import (
        InternalReviewGateExecutor,
    )

    svc = review_svc or _make_review_service(session_factory)
    return InternalReviewGateExecutor(
        review_svc=svc,
        llm_provider=llm_provider,
        agent_id=agent_id or uuid4(),
        session_factory=session_factory,
    )


async def _read_gate_pending(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
    stage_id: UUID,
) -> object:
    """InternalReviewGateRepository.find_by_task_and_stage() で PENDING Gate を読み取る。

    注意: §確定E により gate_decision='PENDING' の Gate のみを返す。
    決定済み（ALL_APPROVED / REJECTED）Gate は _read_gate_decided() を使うこと。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (
        SqliteInternalReviewGateRepository,
    )

    async with session_factory() as session, session.begin():
        return await SqliteInternalReviewGateRepository(session).find_by_task_and_stage(
            task_id, stage_id
        )


async def _read_gate_decided(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
    stage_id: UUID,
) -> object:
    """find_all_by_task_id() で決定済みを含む Gate を読み取る（§確定E 対応）。

    find_by_task_and_stage は PENDING のみ返す。ALL_APPROVED / REJECTED は
    find_all_by_task_id() で取得し stage_id でフィルタする。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (
        SqliteInternalReviewGateRepository,
    )

    async with session_factory() as session, session.begin():
        gates = await SqliteInternalReviewGateRepository(session).find_all_by_task_id(task_id)
    for gate in gates:
        if gate.stage_id == stage_id:
            return gate
    return None


# ---------------------------------------------------------------------------
# TC-IT-IRG-A004: create_gate() のべき等性
# ---------------------------------------------------------------------------


class TestCreateGateIdempotency:
    """TC-IT-IRG-A004: create_gate() — 既存 PENDING Gate の重複生成防止（§確定 F）。"""

    async def test_create_gate_twice_returns_same_gate(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-IRG-A004: 同一引数で 2 回 create_gate() → 同一 Gate（id 一致）。"""
        _, _, _, _, task_id, _, ir_stage_id = await _seed_irg_context(session_factory)

        svc = _make_review_service(session_factory)
        gate1 = await svc.create_gate(task_id, ir_stage_id, frozenset({"reviewer"}))
        gate2 = await svc.create_gate(task_id, ir_stage_id, frozenset({"reviewer"}))

        assert gate1 is not None
        assert gate2 is not None
        # 同一 Gate が返る（id が一致）
        assert gate1.id == gate2.id

        # DB にも 1 件だけ存在する（PENDING 状態）
        persisted = await _read_gate_pending(session_factory, task_id, ir_stage_id)
        assert persisted is not None
        assert persisted.id == gate1.id


# ---------------------------------------------------------------------------
# TC-IT-IRG-A005: GateRole 権限なし → UnauthorizedGateRoleError（T1）
# ---------------------------------------------------------------------------


class TestSubmitVerdictUnauthorizedRole:
    """TC-IT-IRG-A005: submit_verdict() — GateRole 詐称防止（T1）。"""

    async def test_submit_verdict_with_unauthorized_role_raises(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-IRG-A005: required={"security"} Gate に "intruder" → UnauthorizedGateRoleError。"""
        from bakufu.application.exceptions.gate_exceptions import UnauthorizedGateRoleError
        from bakufu.domain.value_objects import VerdictDecision

        _, _, _, agent_id, task_id, _, ir_stage_id = await _seed_irg_context(session_factory)

        svc = _make_review_service(session_factory)
        gate = await svc.create_gate(task_id, ir_stage_id, frozenset({"security"}))
        assert gate is not None

        with pytest.raises(UnauthorizedGateRoleError) as exc_info:
            await svc.submit_verdict(
                gate_id=gate.id,
                role="intruder",  # required_gate_roles にない role
                agent_id=agent_id,
                decision=VerdictDecision.APPROVED,
                comment="不正提出",
            )

        # MSG-IRG-A002 のキーワードを含む
        assert "intruder" in str(exc_info.value) or "GateRole" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-IT-IRG-A006: executor.execute() — 並列 LLM 実行 → ALL_APPROVED
# ---------------------------------------------------------------------------


class TestExecutorParallelLLMAllApproved:
    """TC-IT-IRG-A006: executor.execute() — 並列 LLM 実行 → Gate が ALL_APPROVED に遷移。"""

    async def test_execute_parallel_llm_all_approved(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-IRG-A006: 2 GateRole × APPROVED → Gate が ALL_APPROVED に遷移。"""
        _, _, _, _, task_id, _, ir_stage_id = await _seed_irg_context(session_factory)

        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_tool_call_chat_result("APPROVED", "コードに問題なし"),
                make_tool_call_chat_result("APPROVED", "セキュリティ問題なし"),
            ]
        )
        executor = _make_executor(session_factory, llm_provider=llm)

        await executor.execute(task_id, ir_stage_id, frozenset({"reviewer", "security"}))

        # Gate が ALL_APPROVED に遷移した（決定済みゲートは find_all で取得）
        gate = await _read_gate_decided(session_factory, task_id, ir_stage_id)
        assert gate is not None
        from bakufu.domain.value_objects import GateDecision

        assert gate.gate_decision == GateDecision.ALL_APPROVED

        # chat_with_tools() が 2 回呼ばれた（並列）
        assert llm.chat_with_tools.call_count == 2


# ---------------------------------------------------------------------------
# TC-IT-IRG-A007: executor.execute() — LLM エラー → 例外再送出
# ---------------------------------------------------------------------------


class TestExecutorLLMError:
    """TC-IT-IRG-A007: executor.execute() — LLM エラー → TimeoutError 再送出（§確定 B）。"""

    async def test_execute_llm_timeout_reraises(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-IRG-A007: mock LLM が LLMProviderTimeoutError → execute() で再送出される。"""
        from bakufu.domain.exceptions.llm_provider import LLMProviderTimeoutError

        _, _, _, _, task_id, _, ir_stage_id = await _seed_irg_context(session_factory)

        timeout_exc = make_timeout_error()
        llm = make_stub_llm_provider_with_tools_raises(exc=timeout_exc)
        executor = _make_executor(session_factory, llm_provider=llm)

        with pytest.raises(LLMProviderTimeoutError):
            await executor.execute(task_id, ir_stage_id, frozenset({"reviewer"}))


# ---------------------------------------------------------------------------
# TC-IT-IRG-A008: retry → success → Gate 確定
# ---------------------------------------------------------------------------


class TestExecutorRetrySuccess:
    """TC-IT-IRG-A008: execute() — 初回ツール未呼び出し → 再指示後成功 → Gate が ALL_APPROVED。"""

    async def test_execute_retry_then_approved(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """TC-IT-IRG-A008: 1 回目テキスト → 2 回目 APPROVED → 2 回 / Gate ALL_APPROVED。"""
        _, _, _, _, task_id, _, ir_stage_id = await _seed_irg_context(session_factory)

        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                # 1 回目: ツール未呼出
                make_text_chat_result("コードを確認しました。問題はありません。"),
                make_tool_call_chat_result("APPROVED", "再指示後にOK"),  # 2 回目: 成功
            ]
        )
        executor = _make_executor(session_factory, llm_provider=llm)

        await executor.execute(task_id, ir_stage_id, frozenset({"reviewer"}))

        # chat_with_tools() が 2 回呼ばれた
        assert llm.chat_with_tools.call_count == 2

        # Gate が ALL_APPROVED に遷移した（決定済みゲートは find_all で取得）
        gate = await _read_gate_decided(session_factory, task_id, ir_stage_id)
        assert gate is not None
        from bakufu.domain.value_objects import GateDecision

        assert gate.gate_decision == GateDecision.ALL_APPROVED


# ---------------------------------------------------------------------------
# TC-IT-IRG-A009: 3 回全てツール未呼び出し → REJECTED 強制登録
# ---------------------------------------------------------------------------


class TestExecutorAllRetriesFailForcedRejected:
    """TC-IT-IRG-A009: execute() — 3 回全てツール未呼出 → REJECTED 強制登録（§確定 D）。"""

    async def test_execute_all_retries_fail_forced_rejected(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-IRG-A009: 3 回テキスト → 3 回呼出 / Gate REJECTED / [SYSTEM] comment。"""
        _, _, _, _, task_id, _, ir_stage_id = await _seed_irg_context(session_factory)

        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_text_chat_result("1回目テキスト"),
                make_text_chat_result("2回目テキスト"),
                make_text_chat_result("3回目テキスト"),
            ]
        )
        executor = _make_executor(session_factory, llm_provider=llm)

        with caplog.at_level(
            logging.WARNING,
            logger="bakufu.infrastructure.reviewers.internal_review_gate_executor",
        ):
            await executor.execute(task_id, ir_stage_id, frozenset({"reviewer"}))

        # chat_with_tools() が 3 回呼ばれた（初回 + 再指示 2 回）
        assert llm.chat_with_tools.call_count == 3

        # Gate が REJECTED に遷移した（決定済みゲートは find_all で取得）
        gate = await _read_gate_decided(session_factory, task_id, ir_stage_id)
        assert gate is not None
        from bakufu.domain.value_objects import GateDecision, VerdictDecision

        assert gate.gate_decision == GateDecision.REJECTED

        # REJECTED Verdict の comment に "[SYSTEM]" が含まれる
        rejected_verdict = next(
            (v for v in gate.verdicts if v.decision == VerdictDecision.REJECTED),
            None,
        )
        assert rejected_verdict is not None
        assert "[SYSTEM]" in rejected_verdict.comment

        # audit_log に event=tool_not_called_all_retries が記録される
        assert "tool_not_called_all_retries" in caplog.text
        assert "retry_count=3" in caplog.text
