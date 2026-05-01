"""ValidationService + SqliteDeliverableRecordRepository 結合テスト（TC-IT-VS-001〜002）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §ValidationService+Repository
対応要件: REQ-AIVM-001〜003

LLMProviderPort のみ AsyncMock で mock。DB は in-memory SQLite 実接続。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.application.services.validation_service import ValidationService
from bakufu.domain.exceptions.deliverable_template import LLMValidationError
from bakufu.domain.value_objects.chat_result import ChatResult
from bakufu.domain.value_objects.enums import ValidationStatus
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_record_repository import (
    SqliteDeliverableRecordRepository,
)

from tests.factories.deliverable_record import (
    make_acceptance_criterion,
    make_deliverable_record,
)
from tests.factories.llm_provider_error import make_timeout_error
from tests.factories.stub_llm_provider import (
    make_stub_llm_provider,
    make_stub_llm_provider_raises,
)

pytestmark = pytest.mark.asyncio


class TestValidationServiceIntegration:
    """TC-IT-VS-001〜002: ValidationService + Repository 結合テスト。"""

    async def test_validate_deliverable_passed_and_saved_to_db(
        self,
        vs_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-VS-001: validate_deliverable PASSED → DB から取得しても PASSED。

        要件: REQ-AIVM-001〜003
        """
        stub = make_stub_llm_provider(
            responses=[
                ChatResult(
                    response='{"status": "PASSED", "reason": "要件を満たす"}',
                    session_id=None,
                    compacted=False,
                )
            ]
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        criterion = make_acceptance_criterion(required=True)

        async with vs_session_factory() as session:
            async with session.begin():
                repo = SqliteDeliverableRecordRepository(session)
                service = ValidationService(llm_provider=stub, repository=repo)
                result = await service.validate_deliverable(record, (criterion,))

        # 返却 record が PASSED
        assert result.validation_status == ValidationStatus.PASSED

        # DB から取得した record も PASSED
        async with vs_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            db_record = await repo.find_by_id(record.id)

        assert db_record is not None
        assert db_record.validation_status == ValidationStatus.PASSED

    async def test_validate_deliverable_llm_error_not_saved_to_db(
        self,
        vs_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-VS-002: LLM 失敗 → LLMValidationError が伝播し、DB には保存されない。

        要件: REQ-AIVM-001, REQ-AIVM-003
        """
        exc = make_timeout_error(message="timeout", provider="claude-code")
        stub = make_stub_llm_provider_raises(exc=exc, provider="claude-code")
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        criterion = make_acceptance_criterion(required=True)

        with pytest.raises(LLMValidationError) as exc_info:
            async with vs_session_factory() as session:
                async with session.begin():
                    repo = SqliteDeliverableRecordRepository(session)
                    service = ValidationService(llm_provider=stub, repository=repo)
                    await service.validate_deliverable(record, (criterion,))

        assert exc_info.value.kind == "llm_call_failed"

        # DB には保存されていないこと（find_by_id が None を返す）
        async with vs_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            db_record = await repo.find_by_id(record.id)

        assert db_record is None, (
            f"LLM 失敗時に DB に record が保存されてしまった: {db_record}"
        )
