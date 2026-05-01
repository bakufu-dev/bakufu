"""MSG-AIVM-001〜002 文言物理保証テスト（TC-UT-MSG-AIVM-001〜002）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §MSG 確定文言
対応要件: MSG-AIVM-001, MSG-AIVM-002, R1-F

[FAIL] + Next: の 2 行構造が全 MSG で CI 強制されていることを物理確認する。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bakufu.application.services.validation_service import ValidationService
from bakufu.domain.exceptions.deliverable_template import LLMValidationError

from tests.factories.deliverable_record import make_acceptance_criterion, make_deliverable_record
from tests.factories.llm_provider_error import make_timeout_error
from tests.factories.stub_llm_provider import make_stub_llm_provider_raises


class TestMsgAivm:
    """TC-UT-MSG-AIVM-001〜002: MSG 文言物理保証テスト。"""

    @pytest.mark.asyncio
    async def test_msg_aivm_001_llm_call_failed_contains_fail_and_next(self) -> None:
        """TC-UT-MSG-AIVM-001: MSG-AIVM-001 — [FAIL] + Next: が含まれ、
        プレースホルダが展開されること。

        要件: MSG-AIVM-001, R1-F
        """
        provider = "claude-code"
        exc = make_timeout_error(message="timeout", provider=provider)
        stub = make_stub_llm_provider_raises(exc=exc, provider=provider)
        repo = AsyncMock()
        service = ValidationService(llm_provider=stub, repository=repo)
        record = make_deliverable_record()
        criterion = make_acceptance_criterion(required=True)

        with pytest.raises(LLMValidationError) as exc_info:
            await service.validate_deliverable(record, (criterion,))

        msg = str(exc_info.value)
        assert "[FAIL]" in msg, f"[FAIL] が含まれていない: {msg!r}"
        assert "Next:" in msg, f"Next: が含まれていない: {msg!r}"
        # プレースホルダが展開されていること（{provider} / {error_type} が残っていないこと）
        assert "{provider}" not in msg, f"{{provider}} が未展開: {msg!r}"
        assert "{error_type}" not in msg, f"{{error_type}} が未展開: {msg!r}"
        # 実際のプロバイダ名が含まれていること
        assert provider in msg, f"プロバイダ名 {provider!r} が含まれていない: {msg!r}"

    def test_msg_aivm_002_parse_failed_contains_fail_and_next(self) -> None:
        """TC-UT-MSG-AIVM-002: MSG-AIVM-002 — [FAIL] + Next: + フィールド言及が含まれること。

        要件: MSG-AIVM-002, R1-F
        """
        stub = MagicMock()
        stub.provider = "claude-code"
        repo = MagicMock()
        service = ValidationService(llm_provider=stub, repository=repo)

        with pytest.raises(LLMValidationError) as exc_info:
            service._parse_response("")

        msg = str(exc_info.value)
        assert "[FAIL]" in msg, f"[FAIL] が含まれていない: {msg!r}"
        assert "Next:" in msg, f"Next: が含まれていない: {msg!r}"
        # status / reason フィールドへの言及が含まれること
        assert "status" in msg or "reason" in msg, (
            f"status / reason フィールドへの言及がない: {msg!r}"
        )
