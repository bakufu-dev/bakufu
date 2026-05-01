"""ValidationService — DeliverableRecord LLM 検証フロー Application Service。

LLMProviderPort 経由で LLM CLI を呼び出し、受入基準評価を行い、
評価済み DeliverableRecord を永続化する。

設計書: docs/features/deliverable-template/ai-validation/basic-design.md REQ-AIVM-001, 002
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from bakufu.domain.exceptions.deliverable_template import LLMValidationError
from bakufu.domain.exceptions.llm_provider import LLMProviderError
from bakufu.domain.value_objects.deliverable_record_vos import CriterionValidationResult
from bakufu.domain.value_objects.enums import ValidationStatus

if TYPE_CHECKING:
    from bakufu.application.ports.llm_provider_port import LLMProviderPort
    from bakufu.domain.deliverable_record.deliverable_record import DeliverableRecord
    from bakufu.domain.ports.deliverable_record_repository import (
        AbstractDeliverableRecordRepository,
    )
    from bakufu.domain.value_objects.template_vos import AcceptanceCriterion

# §確定 B: Prompt Injection 対策 delimiter
_CONTENT_BEGIN = "--- BEGIN CONTENT ---"
_CONTENT_END = "--- END CONTENT ---"

# §確定 B: system プロンプト固定テキスト
_SYSTEM_PROMPT = (
    "You are an objective evaluator of deliverable content against acceptance criteria. "
    "Your task is to evaluate whether the given content satisfies the specified criterion. "
    "Respond ONLY with a JSON object in the following format: "
    '{"status": "PASSED" | "FAILED" | "UNCERTAIN", "reason": "<explanation, max 1000 chars>"}. '
    "Do not include any other text outside the JSON object."
)

# MSG-AIVM-001: LLM 呼び出し失敗
_MSG_AIVM_001_TMPL = (
    "[FAIL] LLM validation call failed: provider={provider}, error={error_type}.\n"
    "Next: Check LLM CLI availability and authentication status (claude / codex)."
)

# MSG-AIVM-002: JSON パース失敗
_MSG_AIVM_002 = (
    "[FAIL] LLM validation response could not be parsed: "
    "expected JSON with 'status' and 'reason' fields.\n"
    "Next: Check LLM model output format or update prompt structure in "
    "ValidationService._build_prompt."
)


class ValidationService:
    """DeliverableRecord LLM 検証フロー orchestration（REQ-AIVM-001, 002）。

    Fail Secure: _llm_provider が None の場合は即 LLMValidationError を raise する。
    LLMProviderError サブクラスは即 LLMValidationError(kind='llm_call_failed') に変換する。
    """

    def __init__(
        self,
        llm_provider: LLMProviderPort,
        repository: AbstractDeliverableRecordRepository,
    ) -> None:
        self._llm_provider = llm_provider
        self._repository = repository

    async def validate_deliverable(
        self,
        record: DeliverableRecord,
        criteria: tuple[AcceptanceCriterion, ...],
    ) -> DeliverableRecord:
        """DeliverableRecord を criteria に基づいて LLM 評価し、永続化して返す。

        Args:
            record: PENDING 状態の DeliverableRecord。
            criteria: 評価対象の AcceptanceCriterion タプル。

        Returns:
            評価済み DeliverableRecord（validation_status が PASSED/FAILED/UNCERTAIN）。

        Raises:
            LLMValidationError: LLM 呼び出し失敗またはパース失敗時。
        """
        results: list[CriterionValidationResult] = []

        for criterion in criteria:
            messages, system = self._build_prompt(record.content, criterion)
            try:
                chat_result = await self._llm_provider.chat(
                    messages=messages,
                    system=system,
                    session_id=None,
                )
            except LLMProviderError as exc:
                raise LLMValidationError(
                    message=_MSG_AIVM_001_TMPL.format(
                        provider=exc.provider,
                        error_type=type(exc).__name__,
                    ),
                    kind="llm_call_failed",
                    llm_error_kind=self._classify_llm_error(exc),
                    provider=exc.provider,
                ) from exc

            status, reason = self._parse_response(chat_result.response)
            results.append(
                CriterionValidationResult(
                    criterion_id=criterion.id,
                    status=status,
                    reason=reason,
                )
            )

        new_record = record.derive_status(tuple(results))
        await self._repository.save(new_record)
        return new_record

    def _build_prompt(
        self,
        content: str,
        criterion: AcceptanceCriterion,
    ) -> tuple[list[dict[str, str]], str]:
        """構造化プロンプトを構築する（§確定 B: Prompt Injection T1 対策）。

        Args:
            content: DeliverableRecord.content（評価対象テキスト）。
            criterion: 評価対象の AcceptanceCriterion。

        Returns:
            (messages, system) タプル。messages は 1 要素の user メッセージリスト。
        """
        user_content = (
            f"Criterion: {criterion.description}\n"
            f"Required: {'true' if criterion.required else 'false'}\n\n"
            f"{_CONTENT_BEGIN}\n"
            f"{content}\n"
            f"{_CONTENT_END}"
        )
        messages: list[dict[str, str]] = [{"role": "user", "content": user_content}]
        return messages, _SYSTEM_PROMPT

    def _parse_response(self, raw: str) -> tuple[ValidationStatus, str]:
        """LLM 応答 JSON をパースし (ValidationStatus, reason) を返す。

        Args:
            raw: LLM が返した応答テキスト（期待: JSON with status/reason）。

        Returns:
            (ValidationStatus, reason) タプル。

        Raises:
            LLMValidationError: raw が空、JSON でない、または status/reason キー不在時。
        """
        if not raw:
            raise LLMValidationError(
                message=_MSG_AIVM_002,
                kind="parse_failed",
                llm_error_kind="",
                provider=self._llm_provider.provider,
            )

        try:
            parsed = json.loads(raw)
            status_str = parsed["status"]
            reason = str(parsed["reason"])[:1000]
            status = ValidationStatus(status_str)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise LLMValidationError(
                message=_MSG_AIVM_002,
                kind="parse_failed",
                llm_error_kind="",
                provider=self._llm_provider.provider,
            ) from exc

        if status == ValidationStatus.PENDING:
            raise LLMValidationError(
                message=_MSG_AIVM_002,
                kind="parse_failed",
                llm_error_kind="",
                provider=self._llm_provider.provider,
            )

        return status, reason

    @staticmethod
    def _classify_llm_error(exc: LLMProviderError) -> str:
        """LLMProviderError サブクラスを llm_error_kind 文字列に変換する。"""
        from bakufu.domain.exceptions.llm_provider import (
            LLMProviderAuthError,
            LLMProviderEmptyResponseError,
            LLMProviderProcessError,
            LLMProviderTimeoutError,
        )

        if isinstance(exc, LLMProviderTimeoutError):
            return "timeout"
        if isinstance(exc, LLMProviderAuthError):
            return "auth"
        if isinstance(exc, LLMProviderProcessError):
            return "process_error"
        if isinstance(exc, LLMProviderEmptyResponseError):
            return "empty_response"
        return "unknown"


__all__ = ["ValidationService"]
