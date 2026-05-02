"""InternalReviewGateExecutor ユニットテスト（TC-UT-IRG-A101〜A111）。

設計書: docs/features/internal-review-gate/application/test-design.md
対象: §確定 A / §確定 B（return_exceptions）/ §確定 D（ツール呼出）/ §確定 E（プロンプト）
Issue: #164 feat(M5-B): InternalReviewGate infrastructure実装

前提:
- LLM: make_stub_llm_provider_with_tools() / make_stub_llm_provider_with_tools_raises()
- review_svc / session_factory: AsyncMock
- SqliteTaskRepository: patch して task.current_deliverable.body_markdown を返す（UT スコープ外）
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.value_objects import GateDecision, VerdictDecision
from bakufu.domain.value_objects.chat_result import ChatResult

from tests.factories.internal_review_gate import make_gate
from tests.factories.llm_provider_error import make_timeout_error
from tests.factories.stub_llm_provider import (
    make_stub_llm_provider_with_tools,
    make_text_chat_result,
    make_tool_call_chat_result,
)

pytestmark = pytest.mark.asyncio

_TASK_REPO_PATH = (
    "bakufu.infrastructure.persistence.sqlite.repositories.task_repository.SqliteTaskRepository"
)

# ---------------------------------------------------------------------------
# 共通ヘルパー
# ---------------------------------------------------------------------------


def _stub_task_repo(deliverable_body: str = "# 成果物テキスト") -> object:
    """SqliteTaskRepository をスタブ化するパッチコンテキストマネージャ。

    _execute_single_role() が task.current_deliverable.body_markdown を参照するため、
    SqliteTaskRepository をパッチして mock task を返す。
    """
    mock_task = MagicMock()
    mock_task.current_deliverable = MagicMock()
    mock_task.current_deliverable.body_markdown = deliverable_body

    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=mock_task)

    return patch(_TASK_REPO_PATH, return_value=mock_repo)


def _make_executor(
    *,
    llm_provider: object | None = None,
    review_svc: AsyncMock | None = None,
    agent_id: UUID | None = None,
    max_tool_retries: int = 2,
) -> object:
    """InternalReviewGateExecutor をテスト用設定で生成する。"""
    from bakufu.infrastructure.reviewers.internal_review_gate_executor import (
        InternalReviewGateExecutor,
    )

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    executor = InternalReviewGateExecutor(
        review_svc=review_svc or AsyncMock(),
        llm_provider=llm_provider or make_stub_llm_provider_with_tools(),
        agent_id=agent_id or uuid4(),
        session_factory=mock_sf,
    )
    executor.MAX_TOOL_RETRIES = max_tool_retries
    return executor


# ---------------------------------------------------------------------------
# TC-UT-IRG-A101/A102: 初回ツール呼び出し成功
# ---------------------------------------------------------------------------


class TestInitialToolCallSuccess:
    """TC-UT-IRG-A101/A102: _execute_single_role() — 初回ツール呼び出し成功。"""

    async def test_initial_tool_call_approved(self) -> None:
        """TC-UT-IRG-A101: 初回 chat_with_tools() が APPROVED を返す → submit_verdict(APPROVED)。

        §確定 D ステップ 1→2→3a。
        """

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.ALL_APPROVED)
        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[make_tool_call_chat_result("APPROVED", "コードに問題なし")]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with _stub_task_repo():
            await executor._execute_single_role(gate_id, "reviewer", uuid4(), uuid4())

        # chat_with_tools() が 1 回呼ばれた（リトライなし）
        assert llm.chat_with_tools.call_count == 1
        # submit_verdict() が APPROVED で 1 回呼ばれた
        mock_review_svc.submit_verdict.assert_awaited_once()
        kwargs = mock_review_svc.submit_verdict.call_args.kwargs
        assert kwargs["decision"] == VerdictDecision.APPROVED

    async def test_initial_tool_call_rejected(self) -> None:
        """TC-UT-IRG-A102: 初回 chat_with_tools() が REJECTED を返す → submit_verdict(REJECTED)。

        §確定 D ステップ 1→2→3a。
        """

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.REJECTED)
        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_tool_call_chat_result("REJECTED", "SQLインジェクション脆弱性を発見")
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with _stub_task_repo():
            await executor._execute_single_role(gate_id, "security", uuid4(), uuid4())

        assert llm.chat_with_tools.call_count == 1
        mock_review_svc.submit_verdict.assert_awaited_once()
        kwargs = mock_review_svc.submit_verdict.call_args.kwargs
        assert kwargs["decision"] == VerdictDecision.REJECTED


# ---------------------------------------------------------------------------
# TC-UT-IRG-A103: _build_prompt() 必須セクション確認
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """TC-UT-IRG-A103: _build_prompt() — 必須キーワードの存在確認（§確定 E）。"""

    async def test_build_prompt_contains_required_keywords(self) -> None:
        """TC-UT-IRG-A103: プロンプトに必須キーワードが含まれる。旧来の '1行目' は含まれない。"""
        executor = _make_executor()
        prompt = executor._build_prompt("security", "テスト成果物")

        assert "security" in prompt
        assert "submit_verdict" in prompt
        assert "APPROVED" in prompt
        assert "REJECTED" in prompt
        assert "必ず" in prompt
        assert "1行目" not in prompt


# ---------------------------------------------------------------------------
# TC-UT-IRG-A106: session_id が GateRole ごとに独立した UUID v4
# ---------------------------------------------------------------------------


class TestSessionIdIndependence:
    """TC-UT-IRG-A106: execute() — 各 GateRole の session_id が独立した UUID v4（§確定 A）。"""

    async def test_session_ids_are_independent_uuids(self) -> None:
        """TC-UT-IRG-A106: 3 GateRole で execute() — session_id が各々独立した UUID v4。"""

        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        mock_review_svc = AsyncMock()
        mock_review_svc.create_gate = AsyncMock(return_value=gate)
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.ALL_APPROVED)

        # 3 GateRole それぞれに APPROVED tool call を返す
        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_tool_call_chat_result("APPROVED", "OK"),
                make_tool_call_chat_result("APPROVED", "OK"),
                make_tool_call_chat_result("APPROVED", "OK"),
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        with _stub_task_repo():
            await executor.execute(uuid4(), uuid4(), frozenset({"reviewer", "ux", "security"}))

        # session_id を収集
        session_ids = [c.kwargs["session_id"] for c in llm.chat_with_tools.call_args_list]
        assert len(session_ids) == 3
        # 全て異なる
        assert len(set(session_ids)) == 3
        # 各々が有効な UUID v4 形式であること
        for sid in session_ids:
            assert sid is not None
            UUID(sid, version=4)  # raises ValueError if not valid UUID v4


# ---------------------------------------------------------------------------
# TC-UT-IRG-A107: return_exceptions=True で一部エラーでも全 gather 完了
# ---------------------------------------------------------------------------


class TestReturnExceptions:
    """TC-UT-IRG-A107: execute() — return_exceptions=True（§確定 B）。"""

    async def test_partial_error_still_reraises_non_gate_already_decided(self) -> None:
        """TC-UT-IRG-A107: ux が TimeoutError → TimeoutError 再送出（他は APPROVED で完了）。"""
        from bakufu.domain.exceptions.llm_provider import LLMProviderTimeoutError

        gate = make_gate(required_gate_roles=frozenset({"reviewer", "ux", "security"}))
        mock_review_svc = AsyncMock()
        mock_review_svc.create_gate = AsyncMock(return_value=gate)
        # reviewer と security は APPROVED を返す
        submit_call_count = 0

        async def side_effect_submit(**kwargs: object) -> GateDecision:
            nonlocal submit_call_count
            submit_call_count += 1
            return GateDecision.PENDING

        mock_review_svc.submit_verdict = AsyncMock(side_effect=side_effect_submit)

        timeout_exc = make_timeout_error()

        # reviewer: APPROVED / ux: raise TimeoutError / security: APPROVED
        # 呼び出し順は GateRole ごとに独立なので side_effect のシーケンス管理が困難。
        # ux role だけ TimeoutError を raise するよう per-role で mock_provider をセット。
        async def chat_with_tools_side_effect(**kwargs: object) -> ChatResult:
            # messages の内容で role を判別する（system プロンプトに role が含まれる）
            system: str = kwargs.get("system", "")  # type: ignore[assignment]
            if "ux" in system:
                raise timeout_exc
            return make_tool_call_chat_result("APPROVED", "OK")

        mock_llm = AsyncMock()
        mock_llm.provider = "claude-code"
        mock_llm.chat_with_tools = AsyncMock(side_effect=chat_with_tools_side_effect)
        mock_llm._meta_synthetic = True

        executor = _make_executor(llm_provider=mock_llm, review_svc=mock_review_svc)

        with (
            _stub_task_repo(),
            pytest.raises(LLMProviderTimeoutError),
        ):
            await executor.execute(uuid4(), uuid4(), frozenset({"reviewer", "ux", "security"}))

        # reviewer と security の submit_verdict は呼ばれた
        assert submit_call_count == 2

    async def test_gate_already_decided_is_silently_ignored(self) -> None:
        """TC-UT-IRG-A107 補足: gate_already_decided は無視され execute() は正常終了（§確定 B）。"""

        gate = make_gate(required_gate_roles=frozenset({"reviewer", "security"}))
        mock_review_svc = AsyncMock()
        mock_review_svc.create_gate = AsyncMock(return_value=gate)

        # 1 番目: REJECTED を返す / 2 番目: gate_already_decided 例外を raise
        already_decided_exc = InternalReviewGateInvariantViolation(
            kind="gate_already_decided",
            message="already decided",
            detail={},
        )

        submit_responses: list[object] = [GateDecision.REJECTED, already_decided_exc]
        mock_review_svc.submit_verdict = AsyncMock(side_effect=submit_responses)

        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_tool_call_chat_result("REJECTED", "バグあり"),
                make_tool_call_chat_result("APPROVED", "OK"),
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        with _stub_task_repo():
            # gate_already_decided は無視されるため例外なく正常終了する
            await executor.execute(uuid4(), uuid4(), frozenset({"reviewer", "security"}))


# ---------------------------------------------------------------------------
# TC-UT-IRG-A108〜A111: リトライロジック
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """TC-UT-IRG-A108〜A111: _execute_single_role() — 再指示プロンプト・リトライ上限（§確定 D）。"""

    async def test_retry_1st_prompt_injection(self) -> None:
        """TC-UT-IRG-A108: 初回ツール未呼び出し → 2 回目のメッセージに再指示プロンプトが注入される。

        §確定 D 再指示 1 回目:
        - "前回の応答で判定ツールの呼び出しが確認できませんでした" を含む
        - tool_not_called 固定文言 "ツールを呼び出さずテキストのみで応答しました" を含む
        - prev_response_summary に初回応答テキストの先頭 200 文字が含まれる
        - "これが最終機会" は含まれない（2 回目のため）
        """

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.ALL_APPROVED)

        first_response_text = "コードを確認しました。問題はありません。"
        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_text_chat_result(first_response_text),  # 1 回目: ツール未呼び出し
                make_tool_call_chat_result("APPROVED", "OK"),  # 2 回目: 成功
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with _stub_task_repo():
            await executor._execute_single_role(gate_id, "reviewer", uuid4(), uuid4())

        assert llm.chat_with_tools.call_count == 2

        # 2 回目の呼び出しの messages を検査
        second_call_kwargs = llm.chat_with_tools.call_args_list[1].kwargs
        messages: list[dict[str, str]] = second_call_kwargs["messages"]
        # 最後の user メッセージが再指示プロンプト
        retry_user_messages = [
            m for m in messages if m["role"] == "user" and "前回の応答" in m["content"]
        ]
        assert len(retry_user_messages) == 1
        retry_content = retry_user_messages[0]["content"]

        # 必須文言の確認
        assert "前回の応答で判定ツールの呼び出しが確認できませんでした" in retry_content
        assert "ツールを呼び出さずテキストのみで応答しました" in retry_content
        assert first_response_text[:200] in retry_content
        # "これが最終機会" は含まれない
        assert "これが最終機会" not in retry_content

    async def test_retry_2nd_prompt_contains_last_chance(self) -> None:
        """TC-UT-IRG-A109: 1・2 回目ツール未呼出 → 3 回目に "これが最終機会" が注入される。

        §確定 D 再指示 2 回目: "これが最終機会" + REJECTED 自動登録予告を含む。
        """

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.ALL_APPROVED)

        first_text = "1回目のテキスト応答"
        second_text = "2回目のテキスト応答"
        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_text_chat_result(first_text),  # 1 回目: ツール未呼び出し
                make_text_chat_result(second_text),  # 2 回目: ツール未呼び出し
                make_tool_call_chat_result("APPROVED", "OK"),  # 3 回目: 成功
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with _stub_task_repo():
            await executor._execute_single_role(gate_id, "reviewer", uuid4(), uuid4())

        assert llm.chat_with_tools.call_count == 3

        # 3 回目の呼び出しのメッセージを検査
        third_call_kwargs = llm.chat_with_tools.call_args_list[2].kwargs
        messages: list[dict[str, str]] = third_call_kwargs["messages"]
        retry_user_messages = [
            m for m in messages if m["role"] == "user" and "前回の応答" in m["content"]
        ]
        assert len(retry_user_messages) == 1
        retry_content = retry_user_messages[0]["content"]

        # 2 回目の応答テキストが prev_response_summary として含まれる
        assert second_text[:200] in retry_content
        # "これが最終機会" が含まれる
        assert "これが最終機会" in retry_content
        # REJECTED 自動登録予告が含まれる
        assert "REJECTED" in retry_content

    async def test_all_retries_fail_forces_rejected_with_system_comment(self) -> None:
        """TC-UT-IRG-A110: 3 回全てツール未呼び出し → REJECTED 強制登録 + audit_log 記録。

        §確定 D 3 回全て未登録時の処理 + §確定 J（audit_log）。
        """

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.REJECTED)

        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_text_chat_result("1回目テキスト"),
                make_text_chat_result("2回目テキスト"),
                make_text_chat_result("3回目テキスト"),
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with _stub_task_repo():
            await executor._execute_single_role(gate_id, "reviewer", uuid4(), uuid4())

        # chat_with_tools() が 3 回呼ばれた
        assert llm.chat_with_tools.call_count == 3

        # submit_verdict() が REJECTED で 1 回呼ばれた
        mock_review_svc.submit_verdict.assert_awaited_once()
        kwargs = mock_review_svc.submit_verdict.call_args.kwargs
        assert kwargs["decision"] == VerdictDecision.REJECTED
        assert "[SYSTEM]" in kwargs["comment"]
        assert "全試行でツール未呼び出し" in kwargs["comment"]

    async def test_all_retries_fail_logs_tool_not_called_event(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TC-UT-IRG-A110 補足: 3 回全て未登録 → WARNING ログに tool_not_called_all_retries。"""

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.REJECTED)

        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_text_chat_result("1回目"),
                make_text_chat_result("2回目"),
                make_text_chat_result("3回目"),
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with (
            _stub_task_repo(),
            caplog.at_level(
                logging.WARNING,
                logger="bakufu.infrastructure.reviewers.internal_review_gate_executor",
            ),
        ):
            await executor._execute_single_role(gate_id, "reviewer", uuid4(), uuid4())

        assert "tool_not_called_all_retries" in caplog.text
        assert "retry_count=3" in caplog.text

    async def test_prev_response_summary_is_truncated_to_200_chars(self) -> None:
        """TC-UT-IRG-A111: prev_response_summary は 200 文字でトランケートされる（T3 対策）。

        §確定 D 注入変数 `{prev_response_summary}` の 200 文字上限。
        ログに raw LLM 出力全体（500 文字）は含まれない。
        """

        mock_review_svc = AsyncMock()
        mock_review_svc.submit_verdict = AsyncMock(return_value=GateDecision.ALL_APPROVED)

        text_500_chars = "A" * 500  # 500 文字のテキスト応答
        llm = make_stub_llm_provider_with_tools(
            chat_with_tools_responses=[
                make_text_chat_result(text_500_chars),  # 1 回目: ツール未呼び出し
                make_tool_call_chat_result("APPROVED", "OK"),  # 2 回目: 成功
            ]
        )
        executor = _make_executor(llm_provider=llm, review_svc=mock_review_svc)

        gate_id = uuid4()
        with _stub_task_repo():
            await executor._execute_single_role(gate_id, "reviewer", uuid4(), uuid4())

        # 2 回目の呼び出しのメッセージを検査
        second_call_kwargs = llm.chat_with_tools.call_args_list[1].kwargs
        messages: list[dict[str, str]] = second_call_kwargs["messages"]
        retry_user_msgs = [
            m for m in messages if m["role"] == "user" and "前回の応答" in m["content"]
        ]
        assert len(retry_user_msgs) == 1
        retry_content = retry_user_msgs[0]["content"]

        # 200 文字まで（"A" * 200）は含まれる
        assert "A" * 200 in retry_content
        # 201 文字目以降は含まれない
        assert "A" * 201 not in retry_content
