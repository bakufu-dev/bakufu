"""Workflow Repository: DB制約 + アーキテクチャテスト部分マスキングテンプレート.

TC-IT-WFR-017 / 018 / 023 — FK CASCADE、UNIQUE ペアの強制実行、および
この Workflow PR が導入する**部分マスキング** CI 3層防御テンプレート
（empire-repo は*マスキングなし*テンプレートをフリーズ；この PR は
*部分マスキング*テンプレートをフリーズ — 正確に1列がマスキングされ、
他の全列はマスキングされない）。

詳細は ``docs/features/workflow-repository/test-design.md`` を参照。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_transitions import (
    WorkflowTransitionRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow
from sqlalchemy import delete, select, text

from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-WFR-017: FK CASCADE
# ---------------------------------------------------------------------------
class TestForeignKeyCascade:
    """TC-IT-WFR-017: ``DELETE FROM workflows`` は副テーブルにカスケードする。"""

    async def test_delete_workflow_cascades_to_side_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-017: FK ON DELETE CASCADE が
        workflow_stages / workflow_transitions を空にする。"""
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b],
            transitions=[transition_ab],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session, session.begin():
            await session.execute(delete(WorkflowRow).where(WorkflowRow.id == workflow.id))

        async with session_factory() as session:
            stage_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
                    )
                ).scalars()
            )
            transition_rows = list(
                (
                    await session.execute(
                        select(WorkflowTransitionRow).where(
                            WorkflowTransitionRow.workflow_id == workflow.id
                        )
                    )
                ).scalars()
            )
        assert stage_rows == []
        assert transition_rows == []


# ---------------------------------------------------------------------------
# TC-IT-WFR-018: UNIQUE制約 (workflow_id, stage_id) および
#                                       （workflow_id, transition_id）の複合キー
# ---------------------------------------------------------------------------
class TestUniqueConstraintViolation:
    """TC-IT-WFR-018: 重複 (workflow_id, stage_id) / (..., transition_id) は例外を発生させる。"""

    async def test_duplicate_stage_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-018a: 同じ (workflow_id, stage_id) を2回 INSERT → DB が拒否。

        Repository の削除後挿入フロー は常に挿入前に副テーブルをクリアするため、
        Repository API 経由では制約に引っかかることはない。**DB レベルの**
        UNIQUE 契約を検証するために、Repository をバイパスする生 SQL を発行する。
        """
        from sqlalchemy.exc import IntegrityError

        workflow = make_workflow()
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        stage_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO workflow_stages "
                    "(workflow_id, stage_id, name, kind, roles_csv, "
                    "required_deliverables_json, completion_policy_json, "
                    "notify_channels_json) "
                    "VALUES (:workflow_id, :stage_id, :name, :kind, :roles_csv, "
                    ":deliverable, :policy, :channels)"
                ),
                {
                    "workflow_id": workflow.id.hex,
                    "stage_id": stage_id.hex,
                    "name": "first",
                    "kind": "WORK",
                    "roles_csv": "DEVELOPER",
                    "deliverable": "[]",
                    "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                    "channels": "[]",
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO workflow_stages "
                        "(workflow_id, stage_id, name, kind, roles_csv, "
                        "required_deliverables_json, completion_policy_json, "
                        "notify_channels_json) "
                        "VALUES (:workflow_id, :stage_id, :name, :kind, :roles_csv, "
                        ":deliverable, :policy, :channels)"
                    ),
                    {
                        "workflow_id": workflow.id.hex,
                        "stage_id": stage_id.hex,
                        "name": "duplicate",
                        "kind": "WORK",
                        "roles_csv": "DEVELOPER",
                        "deliverable": "[]",
                        "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                        "channels": "[]",
                    },
                )

    async def test_duplicate_transition_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-018b: 同じ (workflow_id, transition_id) を2回 INSERT → DB が拒否。"""
        from sqlalchemy.exc import IntegrityError

        # 2段階 Workflow は以下の生 INSERT に対する正当な from_stage_id / to_stage_id 値を提供する。
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b],
            transitions=[transition_ab],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        transition_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO workflow_transitions "
                    "(workflow_id, transition_id, from_stage_id, to_stage_id, "
                    "condition, label) "
                    "VALUES (:workflow_id, :transition_id, :from_id, :to_id, "
                    ":cond, :label)"
                ),
                {
                    "workflow_id": workflow.id.hex,
                    "transition_id": transition_id.hex,
                    "from_id": stage_a.id.hex,
                    "to_id": stage_b.id.hex,
                    "cond": "APPROVED",
                    "label": "first",
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO workflow_transitions "
                        "(workflow_id, transition_id, from_stage_id, to_stage_id, "
                        "condition, label) "
                        "VALUES (:workflow_id, :transition_id, :from_id, :to_id, "
                        ":cond, :label)"
                    ),
                    {
                        "workflow_id": workflow.id.hex,
                        "transition_id": transition_id.hex,
                        "from_id": stage_a.id.hex,
                        "to_id": stage_b.id.hex,
                        "cond": "APPROVED",
                        "label": "duplicate",
                    },
                )


# ---------------------------------------------------------------------------
# TC-IT-WFR-023: レイヤー2アーキテクチャテスト部分マスキングテンプレート構造
# ---------------------------------------------------------------------------
class TestPartialMaskTemplateStructure:
    """TC-IT-WFR-023: アーキテクチャテストは部分マスキングのパラメータ化構造を公開する。

    Workflow PR は empire-repository のマスキングなしパターンと並んで
    **部分マスキング**パターンを導入：``workflow_stages`` は正確に
    1つのマスキング列（``notify_channels_json``）を持ち、他のすべての列は
    0個。アーキテクチャテストは ``_PARTIAL_MASK_TABLES`` をパラメータ化
    してこれをアサート — 今後のPRが§逆引き表を最初に更新せずに
    他の列を Masked* 型に交換する場合、アーキテクチャテストに引っかかる。

    今後の Repository PR は、それぞれのAggregate のテーブルに対して
    「部分マスキング」行を追加；構造的な形状により、ハーネスを
    書き直さずに拡張できる。
    """

    async def test_arch_test_module_imports_partial_mask_table_list(self) -> None:
        """TC-IT-WFR-023: ``_PARTIAL_MASK_TABLES`` が ``workflow_stages`` をリストアップ。"""
        from tests.architecture.test_masking_columns import (
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
            _PARTIAL_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        # workflow_stages は部分マスキングテーブル。
        partial_mask_table_names = {tbl for tbl, _ in _PARTIAL_MASK_TABLES}
        assert "workflow_stages" in partial_mask_table_names, (
            "[FAIL] workflow_stages は _PARTIAL_MASK_TABLES に"
            "登録される必要があります。\n"
            "次: detailed-design.md §確定 H. に従い\n"
            "('workflow_stages', 'notify_channels_json') を追加。"
        )
        # workflow_stages の許可される列は正確に notify_channels_json。
        allowed_columns = [col for tbl, col in _PARTIAL_MASK_TABLES if tbl == "workflow_stages"]
        assert allowed_columns == ["notify_channels_json"], (
            f"[FAIL] workflow_stages 部分マスキングが {allowed_columns!r} と宣言、"
            f"期待値は ['notify_channels_json']。\n"
            f"次: §逆引き表 が notify_channels_json をマスキング対象の唯一の列としてフリーズ。"
        )

        # workflows / workflow_transitions はマスキングなしリストに存在。
        assert "workflows" in _NO_MASK_TABLES, (
            "[FAIL] workflows は _NO_MASK_TABLES に登録される必要があります。"
        )
        assert "workflow_transitions" in _NO_MASK_TABLES, (
            "[FAIL] workflow_transitions は _NO_MASK_TABLES に登録される必要があります。"
        )
