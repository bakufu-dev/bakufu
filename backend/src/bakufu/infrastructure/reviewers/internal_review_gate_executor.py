"""InternalReviewGateExecutor — INTERNAL_REVIEW Stage を並列 LLM 実行で実装する Executor。

InternalReviewGateExecutorPort（application/ports/）の structural subtype として実装する。
GateRole ごとに独立した asyncio.gather タスクで LLM を並列呼び出しし、
VerdictDecision を submit_verdict ツール呼び出し経由で確定する（§確定 D）。

設計書: docs/features/internal-review-gate/application/basic-design.md §モジュール構成
        docs/features/internal-review-gate/application/detailed-design.md §確定 A〜I
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.application.ports.llm_provider_port import LLMProviderPort
from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.value_objects import (
    AgentId,
    GateRole,
    InternalGateId,
    StageId,
    TaskId,
    VerdictDecision,
)
from bakufu.infrastructure.reviewers.prompts import default as default_prompt

if TYPE_CHECKING:
    from bakufu.application.services.internal_review_service import InternalReviewService

logger = logging.getLogger(__name__)

# submit_verdict LLM tool schema（§確定 D ツール定義）
_SUBMIT_VERDICT_TOOL_SCHEMA: dict[str, object] = {
    "name": "submit_verdict",
    "description": (
        "審査判定を登録する。レビュー完了時に **必ず** 呼び出すこと。テキストのみの返答は無効。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["APPROVED", "REJECTED"],
                "description": "審査判定。APPROVED または REJECTED の 2 値のみ。",
            },
            "reason": {
                "type": "string",
                "description": "審査根拠・フィードバック（500文字以内）。",
            },
        },
        "required": ["decision", "reason"],
    },
}

# ツール未呼び出し時の固定文言（§確定 D）
_TOOL_NOT_CALLED_MSG: str = "ツールを呼び出さずテキストのみで応答しました"

# 再指示プロンプト（§確定 D）
_RETRY_PROMPT_1: str = (
    "前回の応答で判定ツールの呼び出しが確認できませんでした。"
    "理由: {tool_not_called}。"
    "前回応答の要約: {prev_response_summary}。"
    "必ず `submit_verdict` ツールを呼び出して判定を登録してください。"
)

_RETRY_PROMPT_2: str = (
    "前回の応答でも判定ツールの呼び出しが確認できませんでした。"
    "理由: {tool_not_called}。"
    "前回応答の要約: {prev_response_summary}。"
    "**これが最終機会です。** "
    "必ず `submit_verdict` ツールを呼び出してください。"
    "この後ツールを呼び出さない場合、システムが自動的に REJECTED として登録します。"
)

_PREV_RESPONSE_MAX_CHARS: int = 200


class InternalReviewGateExecutor:
    """INTERNAL_REVIEW Gate を並列 LLM 実行で実装する Executor（§確定 G）。

    InternalReviewGateExecutorPort（application/ports/）を structural subtype として満足する。
    InternalReviewService と LLMProviderPort に依存し、GateRole ごとに独立した
    asyncio タスクで LLM を並列呼び出しする（§確定 B）。
    """

    MAX_TOOL_RETRIES: int = 2  # 最大リトライ回数（§確定 D: 3回試行 = 初回1 + リトライ2）

    def __init__(
        self,
        *,
        review_svc: InternalReviewService,
        llm_provider: LLMProviderPort,
        agent_id: AgentId,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Executor を初期化する。

        Args:
            review_svc: InternalReviewService（Gate CRUD + Verdict 提出）。
                TYPE_CHECKING 下でのみ import することで実行時の循環 import リスクを
                回避しつつ、pyright の型検査を有効にする（application → infrastructure
                方向の依存逆転は TYPE_CHECKING ブロックで保全する）。
            llm_provider: GateRole 審査 LLM 呼び出し用 Port。
            agent_id: 全 GateRole 審査に使用する Executor 共通の AgentId。
            session_factory: GateRole ごとの独立 AsyncSession 生成元（§確定 I）。
        """
        self._review_svc = review_svc
        self._llm_provider = llm_provider
        self._agent_id = agent_id
        self._session_factory = session_factory

    async def execute(
        self,
        task_id: TaskId,
        stage_id: StageId,
        required_gate_roles: frozenset[GateRole],
    ) -> None:
        """Gate を生成し、全 GateRole を並列 LLM 実行して判定完了まで待機する（§確定 B）。

        StageWorker が Semaphore を acquire したまま await する long-running coroutine。
        全 GateRole 完了（または REJECTED）後に return し、Semaphore を解放させる。

        Raises:
            LLMProviderError 系: LLM 呼び出し失敗時（StageExecutorService が Task.block() に帰着）
        """
        gate = await self._review_svc.create_gate(task_id, stage_id, required_gate_roles)
        if gate is None:
            # required_gate_roles が空集合 → Gate 生成スキップ（§確定 F）
            return

        gate_id: InternalGateId = gate.id

        tasks = [
            self._execute_single_role(gate_id, role, task_id, stage_id)
            for role in required_gate_roles
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 例外フィルタリング（§確定 B）
        non_gate_already_decided_errors = [
            exc
            for exc in results
            if isinstance(exc, BaseException)
            and not (
                isinstance(exc, InternalReviewGateInvariantViolation)
                and exc.kind == "gate_already_decided"
            )
        ]
        if non_gate_already_decided_errors:
            raise non_gate_already_decided_errors[0]

    async def _execute_single_role(
        self,
        gate_id: InternalGateId,
        role: GateRole,
        task_id: TaskId,
        stage_id: StageId,
    ) -> None:
        """1 GateRole に対して LLM を呼び出し、submit_verdict を取得する（§確定 D）。

        task.current_deliverable で成果物テキストを取得し、
        chat_result.tool_calls で ToolCall を解析する（§確定 D / E 更新後）。
        submit_verdict 呼び出しは self._review_svc に委譲する。
        """
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        # deliverable_summary を取得（§確定 E）
        # GateRole ごとに独立した AsyncSession で Task を取得する（§確定 I）
        async with self._session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            task = await task_repo.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        current_deliverable = task.current_deliverable
        if current_deliverable is None:
            raise InternalReviewGateExecutor._make_illegal_state_error(task_id, stage_id)
        deliverable_summary = current_deliverable.body_markdown

        system_prompt = self._build_prompt(role, deliverable_summary)
        initial_messages: list[dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    "成果物を審査し、必ず `submit_verdict(decision, reason)` ツールを呼び出せ。"
                ),
            }
        ]

        prev_response_summary: str = "（前回応答なし）"

        for attempt in range(1 + self.MAX_TOOL_RETRIES):
            session_id = str(uuid4())  # §確定 A: GateRole ごとに独立した UUID v4

            if attempt == 0:
                current_messages = initial_messages
            elif attempt == 1:
                retry_msg = _RETRY_PROMPT_1.format(
                    tool_not_called=_TOOL_NOT_CALLED_MSG,
                    prev_response_summary=prev_response_summary,
                )
                current_messages = [*initial_messages, {"role": "user", "content": retry_msg}]
            else:
                retry_msg = _RETRY_PROMPT_2.format(
                    tool_not_called=_TOOL_NOT_CALLED_MSG,
                    prev_response_summary=prev_response_summary,
                )
                current_messages = [*initial_messages, {"role": "user", "content": retry_msg}]

            chat_result = await self._llm_provider.chat_with_tools(
                messages=current_messages,
                system=system_prompt,
                tools=[_SUBMIT_VERDICT_TOOL_SCHEMA],
                session_id=session_id,
            )

            # LLM 応答から tool_calls を解析（§確定 D 更新後）
            submit_verdict_call = next(
                (tc for tc in chat_result.tool_calls if tc.name == "submit_verdict"),
                None,
            )
            if submit_verdict_call is not None:
                decision_raw: object = submit_verdict_call.input.get("decision")
                reason_raw: object = submit_verdict_call.input.get("reason", "")
                if decision_raw in ("APPROVED", "REJECTED"):
                    decision = VerdictDecision(str(decision_raw))
                    reason = str(reason_raw) if reason_raw is not None else ""
                    await self._review_svc.submit_verdict(
                        gate_id=gate_id,
                        role=role,
                        agent_id=self._agent_id,
                        decision=decision,
                        comment=reason,
                    )
                    return

            # ツール未呼び出し → 再指示へ（§確定 D）
            # T3 対策: raw LLM 出力全体をログに記録しない。先頭 200 文字のみ保持。
            raw_response = chat_result.response
            prev_response_summary = raw_response[:_PREV_RESPONSE_MAX_CHARS]
            prev_response_length = len(raw_response)
            logger.info(
                "submit_verdict tool not called: gate_id=%s role=%s "
                "attempt=%d prev_response_length=%d",
                gate_id,
                role,
                attempt,
                prev_response_length,
            )

        # 全試行でツール未呼び出し → REJECTED fallback（§確定 D）
        retry_count = self.MAX_TOOL_RETRIES + 1
        logger.warning(
            "event=tool_not_called_all_retries gate_id=%s role=%s retry_count=%d",
            gate_id,
            role,
            retry_count,
        )
        await self._review_svc.submit_verdict(
            gate_id=gate_id,
            role=role,
            agent_id=self._agent_id,
            decision=VerdictDecision.REJECTED,
            comment="[SYSTEM] 全試行でツール未呼び出し——判定未登録（ambiguous 扱い）",
        )

    def _build_prompt(self, role: GateRole, deliverable_summary: str) -> str:
        """§確定 E のプロンプト構造でシステムプロンプトを構築する。"""
        return default_prompt.build(role, deliverable_summary)

    @classmethod
    def _make_illegal_state_error(cls, task_id: TaskId, stage_id: StageId) -> IllegalTaskStateError:
        """INTERNAL_REVIEW 実行時に Task の成果物が存在しない場合の例外を生成する（§確定 E）."""
        return IllegalTaskStateError(
            task_id,
            "IN_PROGRESS",
            f"fetch_current_deliverable (stage_id={stage_id}): no deliverable found",
        )


__all__ = ["InternalReviewGateExecutor"]
