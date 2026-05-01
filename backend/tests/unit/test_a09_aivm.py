"""A09 機密情報非混入物理保証テスト（TC-UT-A09-AIVM-001〜002）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §A09 機密情報非混入
対応要件: A09 機密情報非混入セキュリティ設計

LLMValidationError フィールドに認証情報・機密情報が混入しないことを物理確認する。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bakufu.application.services.validation_service import ValidationService
from bakufu.domain.exceptions.deliverable_template import LLMValidationError

from tests.factories.deliverable_record import make_acceptance_criterion, make_deliverable_record
from tests.factories.llm_provider_error import make_auth_error
from tests.factories.stub_llm_provider import make_stub_llm_provider_raises

# 機密情報として扱うパターン（テスト用。実際のトークンは使用しない）
_SECRET_PATTERNS = [
    "sk-ant-",
    "Bearer ",
    "access_token",
    "secret_key",
    "password",
    "private_key",
    "-----BEGIN",
]


class TestA09Aivm:
    """TC-UT-A09-AIVM-001〜002: 機密情報非混入物理保証テスト。"""

    @pytest.mark.asyncio
    async def test_auth_error_llm_validation_error_has_no_secret(self) -> None:
        """TC-UT-A09-AIVM-001: LLMProviderAuthError → LLMValidationError に認証情報が含まれない。

        要件: A09
        """
        # OAuth メッセージを含む AuthError を生成（実際のトークンは使わない）
        exc = make_auth_error(message="OAuth expired", provider="claude-code")
        stub = make_stub_llm_provider_raises(exc=exc, provider="claude-code")
        repo = AsyncMock()
        service = ValidationService(llm_provider=stub, repository=repo)
        record = make_deliverable_record()
        criterion = make_acceptance_criterion(required=True)

        with pytest.raises(LLMValidationError) as exc_info:
            await service.validate_deliverable(record, (criterion,))

        llm_err = exc_info.value
        # message / provider / llm_error_kind の全フィールドを結合して機密情報を検索
        combined = f"{llm_err.message} {llm_err.provider} {llm_err.llm_error_kind}"

        for pattern in _SECRET_PATTERNS:
            assert pattern not in combined, (
                f"機密情報パターン {pattern!r} が LLMValidationError フィールドに検出された: "
                f"{combined!r}"
            )

    def test_parse_failed_llm_validation_error_has_no_secret(self) -> None:
        """TC-UT-A09-AIVM-002: parse_failed 時の LLMValidationError に機密情報が含まれない。

        要件: A09
        """
        stub = MagicMock()
        stub.provider = "claude-code"
        repo = MagicMock()
        service = ValidationService(llm_provider=stub, repository=repo)

        with pytest.raises(LLMValidationError) as exc_info:
            service._parse_response("")

        llm_err = exc_info.value
        combined = f"{llm_err.message} {llm_err.kind}"

        for pattern in _SECRET_PATTERNS:
            assert pattern not in combined, (
                f"機密情報パターン {pattern!r} が LLMValidationError フィールドに検出された: "
                f"{combined!r}"
            )
