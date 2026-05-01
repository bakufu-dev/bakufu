"""SqliteDeliverableRecordRepository 結合テスト（TC-IT-REPO-001〜007）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §結合テストケース
対応要件: REQ-AIVM-003（SqliteDeliverableRecordRepository.save 7 段階冪等）

DB: in-memory SQLite 実接続（create_all でスキーマ作成、Alembic なし）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.domain.value_objects.enums import ValidationStatus
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_record_repository import (
    SqliteDeliverableRecordRepository,
)

from tests.factories.deliverable_record import (
    make_criterion_validation_result,
    make_deliverable_record,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-REPO-001: save → find_by_id ラウンドトリップ
# ---------------------------------------------------------------------------


class TestSaveFindById:
    """TC-IT-REPO-001: save → find_by_id ラウンドトリップ。"""

    async def test_save_and_find_by_id_roundtrip(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-001: save → find_by_id で同一 record が復元される。

        要件: REQ-AIVM-003
        """
        result_a = make_criterion_validation_result(status=ValidationStatus.PASSED)
        result_b = make_criterion_validation_result(status=ValidationStatus.FAILED)
        record = make_deliverable_record(
            validation_status=ValidationStatus.FAILED,
            criterion_results=(result_a, result_b),
        )

        async with repo_session_factory() as session:
            async with session.begin():
                repo = SqliteDeliverableRecordRepository(session)
                await repo.save(record)

        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            restored = await repo.find_by_id(record.id)

        assert restored is not None
        assert restored.id == record.id
        assert restored.deliverable_id == record.deliverable_id
        assert restored.validation_status == ValidationStatus.FAILED
        assert len(restored.criterion_results) == 2

    # ---------------------------------------------------------------------------
    # TC-IT-REPO-002: save → find_by_deliverable_id ラウンドトリップ
    # ---------------------------------------------------------------------------

    async def test_save_and_find_by_deliverable_id_roundtrip(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-002: save → find_by_deliverable_id で最新 record が返る。

        要件: REQ-AIVM-003
        """
        record = make_deliverable_record(
            validation_status=ValidationStatus.PASSED,
            criterion_results=(
                make_criterion_validation_result(status=ValidationStatus.PASSED),
            ),
        )

        async with repo_session_factory() as session:
            async with session.begin():
                repo = SqliteDeliverableRecordRepository(session)
                await repo.save(record)

        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            restored = await repo.find_by_deliverable_id(record.deliverable_id)

        assert restored is not None
        assert restored.deliverable_id == record.deliverable_id
        assert restored.validation_status == ValidationStatus.PASSED


# ---------------------------------------------------------------------------
# TC-IT-REPO-003: save 冪等性（7 段階 save() パターン §確定D）
# ---------------------------------------------------------------------------


class TestSaveIdempotency:
    """TC-IT-REPO-003: 同一 id で 2 回 save → 最新データで完全上書き。"""

    async def test_save_idempotent_overwrites_with_latest_data(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-003: 同一 id の record を 2 回 save → 2 回目のデータで完全上書き。

        要件: REQ-AIVM-003, §確定D
        古い criterion_results が完全に置換されること（旧レコードなし）。
        """
        from uuid import uuid4

        record_id = uuid4()

        # 1 回目: PENDING 状態で保存
        first_record = make_deliverable_record(
            record_id=record_id,
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )

        async with repo_session_factory() as session:
            async with session.begin():
                repo = SqliteDeliverableRecordRepository(session)
                await repo.save(first_record)

        # 2 回目: 同一 id で PASSED 状態に更新して保存
        updated_record = make_deliverable_record(
            record_id=record_id,
            deliverable_id=first_record.deliverable_id,
            template_ref=first_record.template_ref,
            content=first_record.content,
            task_id=first_record.task_id,
            validation_status=ValidationStatus.PASSED,
            criterion_results=(
                make_criterion_validation_result(status=ValidationStatus.PASSED),
            ),
            created_at=first_record.created_at,
        )

        async with repo_session_factory() as session:
            async with session.begin():
                repo = SqliteDeliverableRecordRepository(session)
                await repo.save(updated_record)

        # 2 回目 save 後に find_by_id で取得した record が PASSED になっていること
        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            restored = await repo.find_by_id(record_id)

        assert restored is not None
        assert restored.validation_status == ValidationStatus.PASSED
        # 古い criterion_results（空）が置換されて新しいもの（1件）になっていること
        assert len(restored.criterion_results) == 1
        assert restored.criterion_results[0].status == ValidationStatus.PASSED


# ---------------------------------------------------------------------------
# TC-IT-REPO-004〜005: find_by_id / find_by_deliverable_id 存在しない ID
# ---------------------------------------------------------------------------


class TestFindNotFound:
    """TC-IT-REPO-004〜005: 存在しない ID → None が返る。"""

    async def test_find_by_id_not_found_returns_none(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-004: find_by_id — 存在しない ID → None。

        要件: REQ-AIVM-003
        """
        from uuid import uuid4
        random_id = uuid4()

        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            result = await repo.find_by_id(random_id)

        assert result is None

    async def test_find_by_deliverable_id_not_found_returns_none(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-005: find_by_deliverable_id — 存在しない ID → None。

        要件: REQ-AIVM-003
        """
        from uuid import uuid4
        random_id = uuid4()

        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            result = await repo.find_by_deliverable_id(random_id)

        assert result is None


# ---------------------------------------------------------------------------
# TC-IT-REPO-006: criterion_results N 件保存・全件取得
# ---------------------------------------------------------------------------


class TestSaveNResults:
    """TC-IT-REPO-006: criterion_results N 件保存・全件取得。"""

    async def test_save_and_retrieve_n_criterion_results(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-006: criterion_results 5 件保存 → find_by_id で全件復元。

        要件: REQ-AIVM-003
        """
        results = tuple(
            make_criterion_validation_result(
                status=ValidationStatus.PASSED,
                reason=f"理由{i}",
            )
            for i in range(5)
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PASSED,
            criterion_results=results,
        )

        async with repo_session_factory() as session:
            async with session.begin():
                repo = SqliteDeliverableRecordRepository(session)
                await repo.save(record)

        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            restored = await repo.find_by_id(record.id)

        assert restored is not None
        assert len(restored.criterion_results) == 5
        # criterion_id が全件正確に復元されていること
        original_ids = {r.criterion_id for r in results}
        restored_ids = {r.criterion_id for r in restored.criterion_results}
        assert original_ids == restored_ids


# ---------------------------------------------------------------------------
# TC-IT-REPO-007: トランザクション失敗 → Rollback
# ---------------------------------------------------------------------------


class TestTransactionRollback:
    """TC-IT-REPO-007: INSERT フェーズで SQLAlchemyError → Rollback → find_by_id が None。"""

    async def test_save_rollback_on_sqlalchemy_error(
        self,
        repo_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-REPO-007: save の INSERT フェーズで SQLAlchemyError → Rollback。

        要件: REQ-AIVM-003, §確定D
        Rollback 後に find_by_id が None を返す（中途半端な状態が残っていない）。
        """
        from sqlalchemy.exc import SQLAlchemyError

        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )

        try:
            async with repo_session_factory() as session:
                async with session.begin():
                    repo = SqliteDeliverableRecordRepository(session)
                    # Step 3 の INSERT を強制的に失敗させる
                    from sqlalchemy import insert
                    original_execute = session.execute

                    call_count = 0

                    async def _patched_execute(stmt: object, *args: object, **kwargs: object) -> object:
                        nonlocal call_count
                        call_count += 1
                        # 3 回目の execute（deliverable_records INSERT）で失敗させる
                        if call_count == 3:
                            raise SQLAlchemyError("forced error for test")
                        return await original_execute(stmt, *args, **kwargs)

                    with patch.object(session, "execute", side_effect=_patched_execute):
                        await repo.save(record)
        except SQLAlchemyError:
            pass  # ロールバックが期待される

        # Rollback 後に find_by_id が None を返すこと
        async with repo_session_factory() as session:
            repo = SqliteDeliverableRecordRepository(session)
            result = await repo.find_by_id(record.id)

        assert result is None, (
            f"Rollback 後も record が残っている: {result}"
        )
