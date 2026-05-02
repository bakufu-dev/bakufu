"""受入テスト共通フィクスチャ。

全テストはインプロセス SQLite + 完全なアプリケーションスタック（HTTP API + StageWorker）で動作する。
LLM 呼び出しは DelegateFakeLLMProvider で代替する。
Stage 実行は StageWorker.enqueue() + HTTP ポーリングで制御する（ブラックボックス原則準拠）。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.acceptance.fake_llm_provider import FakeRoundBasedLLMProvider

if TYPE_CHECKING:
    from bakufu.infrastructure.worker.stage_worker import StageWorker

pytestmark = pytest.mark.asyncio

_POLL_INTERVAL = 0.05  # 秒
_POLL_TIMEOUT = 30.0  # 秒


class DelegateFakeLLMProvider:
    """テストごとに verdicts を動的に切り替えられる fake LLM プロキシ。

    StageWorker に注入し、各テストが ``reset()`` を呼んで
    FakeRoundBasedLLMProvider を差し替える。
    """

    provider: str = "fake-acceptance"

    def __init__(self) -> None:
        self._inner: FakeRoundBasedLLMProvider = FakeRoundBasedLLMProvider()

    def reset(self, verdicts: list[str] | None = None) -> None:
        """テスト開始時に呼んで verdicts を初期化する。"""
        self._inner = FakeRoundBasedLLMProvider(chat_with_tools_verdicts=verdicts)

    @property
    def chat_call_count(self) -> int:
        return self._inner._chat_call_count

    @property
    def tools_call_count(self) -> int:
        return self._inner._tools_call_count

    async def chat(self, messages, system, use_tools=False, agent_name="", session_id=None):
        return await self._inner.chat(messages, system, use_tools, agent_name, session_id)

    async def chat_with_tools(self, messages, system, tools, session_id=None):
        return await self._inner.chat_with_tools(messages, system, tools, session_id)


@dataclass
class AcceptanceCtx:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    stage_worker: StageWorker
    fake_llm: DelegateFakeLLMProvider


@pytest_asyncio.fixture
async def acceptance_ctx(tmp_path: Path) -> AsyncIterator[AcceptanceCtx]:
    """受入テスト用 client + session_factory + StageWorker + fake LLM。"""
    from bakufu.application.services.internal_review_service import InternalReviewService
    from bakufu.infrastructure.event_bus import InMemoryEventBus
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
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
    from bakufu.infrastructure.reviewers.internal_review_gate_executor import (
        InternalReviewGateExecutor,
    )
    from bakufu.infrastructure.security import masking as masking_mod
    from bakufu.infrastructure.worker.stage_worker import StageWorker
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    masking_mod.init()
    # dev_tasks_router（dispatch エンドポイント）が登録されるよう test 環境を明示する
    os.environ.setdefault("BAKUFU_ENV", "test")
    app = create_app()
    engine = make_test_engine(tmp_path / "acceptance_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    event_bus = InMemoryEventBus()
    fake_llm = DelegateFakeLLMProvider()

    # StageWorker を fake_llm で起動（ブラックボックステストの Stage 実行エンジン）
    from uuid import uuid4

    review_svc = InternalReviewService(
        session_factory=session_factory,
        gate_repo_factory=SqliteInternalReviewGateRepository,
        task_repo_factory=SqliteTaskRepository,
        workflow_repo_factory=SqliteWorkflowRepository,
        room_repo_factory=SqliteRoomRepository,
        event_bus=event_bus,
    )
    internal_review_executor = InternalReviewGateExecutor(
        review_svc=review_svc,
        llm_provider=fake_llm,
        agent_id=uuid4(),
        session_factory=session_factory,
    )
    stage_worker = StageWorker(
        session_factory=session_factory,
        llm_provider=fake_llm,
        event_bus=event_bus,
        internal_review_port=internal_review_executor,
        max_concurrent=1,
    )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_bus = event_bus
    # ConnectionManager が必要なエンドポイントのために初期化する
    from bakufu.interfaces.http.connection_manager import ConnectionManager

    app.state.connection_manager = ConnectionManager()
    app.state.allowed_origins = ["http://test"]
    app.state.stage_worker = stage_worker

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        stage_worker.start()
        try:
            yield AcceptanceCtx(
                client=client,
                session_factory=session_factory,
                stage_worker=stage_worker,
                fake_llm=fake_llm,
            )
        finally:
            await stage_worker.stop()

    await engine.dispose()


async def poll_task_status(
    client: AsyncClient,
    task_id: object,
    *,
    expected: set[str],
    timeout: float = _POLL_TIMEOUT,
) -> dict:
    """Task の status が expected のいずれかになるまでポーリングして task dict を返す。

    タイムアウト時は TimeoutError を送出する。
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/api/tasks/{task_id}")
        assert r.status_code == 200, f"GET /api/tasks/{task_id} failed: {r.status_code}"
        data = r.json()
        if data["status"] in expected:
            return data
        await asyncio.sleep(_POLL_INTERVAL)
    raise TimeoutError(f"Task {task_id} did not reach {expected} within {timeout}s")


async def poll_internal_review_gates(
    client: AsyncClient,
    task_id: object,
    *,
    min_count: int = 1,
    timeout: float = _POLL_TIMEOUT,
    owner_id: str | None = None,
) -> list[dict]:
    """InternalReviewGate が min_count 件以上になるまでポーリングしてリストを返す。"""
    headers = {"Authorization": f"Bearer {owner_id}"} if owner_id is not None else {}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/api/tasks/{task_id}/internal-review-gates", headers=headers)
        assert r.status_code == 200, f"GET internal-review-gates failed: {r.status_code}"
        gates = r.json()
        if len(gates) >= min_count:
            return gates
        await asyncio.sleep(_POLL_INTERVAL)
    raise TimeoutError(
        f"Task {task_id}: {min_count} InternalReviewGate(s) not found within {timeout}s"
    )


async def poll_gate_with_verdict(
    client: AsyncClient,
    task_id: object,
    *,
    verdict: str,
    timeout: float = _POLL_TIMEOUT,
    owner_id: str | None = None,
) -> dict:
    """指定した verdict を持つ InternalReviewGate が現れるまでポーリングして返す。"""
    headers = {"Authorization": f"Bearer {owner_id}"} if owner_id is not None else {}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/api/tasks/{task_id}/internal-review-gates", headers=headers)
        assert r.status_code == 200
        for gate in r.json():
            if gate["gate_decision"] == verdict:
                return gate
        await asyncio.sleep(_POLL_INTERVAL)
    raise TimeoutError(f"Task {task_id}: gate with verdict={verdict!r} not found within {timeout}s")
