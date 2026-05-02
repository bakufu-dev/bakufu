"""InternalReviewGateExecutor — INTERNAL_REVIEW Stage を並列 LLM 実行で実装する Executor。

InternalReviewGateExecutorPort（application/ports/）の structural subtype として実装する。
GateRole ごとに独立した asyncio.gather タスクで LLM を並列呼び出しし、
VerdictDecision を submit_verdict ツール呼び出し経由で確定する（§確定 D）。

設計書: docs/features/internal-review-gate/application/basic-design.md §モジュール構成
        docs/features/internal-review-gate/application/detailed-design.md §確定 A〜I
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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

        deliverable_summary を取得するため GateRole ごとに独立した AsyncSession を
        生成する（§確定 I）。submit_verdict 呼び出しは self._review_svc に委譲し、
        session 管理は InternalReviewService 側で行う。
        """
        # deliverable_summary を取得（§確定 E）
        # GateRole ごとに独立した AsyncSession で Task を取得する（§確定 I）
        deliverable_summary = await self._fetch_deliverable_summary(task_id, stage_id)

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

            # LLM 応答から tool_call を解析（§確定 D）
            tool_call = self._extract_tool_call(chat_result.response)
            if tool_call is not None:
                decision_str, reason = tool_call
                decision = VerdictDecision(decision_str)
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

    async def _fetch_deliverable_summary(self, task_id: TaskId, stage_id: StageId) -> str:
        """GateRole 専用の独立 AsyncSession で Task を取得し成果物テキストを返す（§確定 E・I）。

        stage_id は将来の拡張（role 別 stage 対応）のために引数として保持するが、
        現時点では task.deliverables の最新成果物を返す（WORK Stage が直前に生成した成果物）。

        Args:
            task_id: 対象 Task の識別子。
            stage_id: INTERNAL_REVIEW Stage の識別子（将来の拡張用）。

        Returns:
            審査対象成果物テキスト（deliverable.body_markdown）。

        Raises:
            IllegalTaskStateError: Task が存在しないか current_deliverable が None の場合。
        """
        from bakufu.application.exceptions.task_exceptions import TaskNotFoundError
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        async with self._session_factory() as session:
            task_repo = SqliteTaskRepository(session)
            task = await task_repo.find_by_id(task_id)

        if task is None:
            raise TaskNotFoundError(task_id)

        # task.deliverables は {StageId: Deliverable} 形式。
        # INTERNAL_REVIEW Stage には deliverable がないため、直前 WORK Stage の
        # 成果物（最新エントリ）を取得する（§確定 E: task.current_deliverable に対応）。
        if not task.deliverables:
            raise _make_illegal_task_state_error(task_id, stage_id)

        latest_deliverable = next(reversed(task.deliverables.values()))
        return latest_deliverable.body_markdown

    def _build_prompt(self, role: GateRole, deliverable_summary: str) -> str:
        """§確定 E のプロンプト構造でシステムプロンプトを構築する。"""
        return default_prompt.build(role, deliverable_summary)

    @staticmethod
    def _extract_tool_call(response: str) -> tuple[str, str] | None:
        """LLM 応答テキストから submit_verdict ツール呼び出しを抽出する（§確定 D）。

        chat_with_tools() の応答形式は LLMProvider 実装に依存する。
        Claude Code CLI の tool_use 応答は JSON 形式（type="tool_use"）で返るため、
        JSON パースを試みる。パース失敗時は None を返し、リトライへ委ねる。

        注意: 実際の応答形式は ClaudeCodeLLMClient.chat_with_tools() 実装に依存する。
        当実装は Claude Code CLI が tool_use ブロックを JSON として埋め込む形式を前提とする。
        LLMProvider 実装変更時はこのメソッドも更新すること。

        Returns:
            (decision, reason) のタプル。ツール呼び出しが無い場合は None。
        """
        try:
            parsed: object = json.loads(response)
            if not isinstance(parsed, dict):
                return None
            data: dict[str, object] = cast(dict[str, object], parsed)
            if data.get("type") != "tool_use":
                return None
            tool_input_raw = data.get("input", {})
            if not isinstance(tool_input_raw, dict):
                return None
            tool_input: dict[str, object] = cast(dict[str, object], tool_input_raw)
            decision_raw = tool_input.get("decision")
            if decision_raw not in ("APPROVED", "REJECTED"):
                return None
            decision: str = str(decision_raw)
            reason_raw = tool_input.get("reason", "")
            reason: str = str(reason_raw) if reason_raw is not None else ""
            return (decision, reason)
        except (json.JSONDecodeError, AttributeError, KeyError):
            pass
        return None


def _make_illegal_task_state_error(task_id: TaskId, stage_id: StageId) -> Exception:
    """INTERNAL_REVIEW 実行時に Task の成果物が存在しない場合の例外を生成する（§確定 E）。

    Task に deliverable が存在しない状態で INTERNAL_REVIEW が起動されるのは
    ワークフロー設計バグ（直前 WORK Stage が commit_deliverable を呼ばずに
    INTERNAL_REVIEW に遷移した）であり、Fail Fast で検出する。
    """
    return ValueError(
        f"Task {task_id} has no deliverable for INTERNAL_REVIEW stage {stage_id}. "
        f"The preceding WORK Stage must commit a deliverable before INTERNAL_REVIEW."
    )


__all__ = ["InternalReviewGateExecutor"]
