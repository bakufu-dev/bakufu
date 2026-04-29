"""Workflow Repository: save() ── delete-then-insert + SQL 順序 + 隔離。

TC-IT-WFR-009 / 010 ── ``save()`` フローの行丸ごと置換と 5 ステップ DML シーケンスを
裏付ける §確定 B 契約と、Workflow 間の隔離スモーク（``DELETE`` は単一の
``workflow_id`` にスコープされる）を扱う。

Norman 500 行ルールにより ``test_save_semantics.py`` から分割
（BUG-WFR-001 修正後にファイルが 502 行に達するため）。残り 2 つの併設ファイルは
ラウンドトリップ + Tx 境界の契約をカバーする:

* :mod:`...test_workflow_repository.test_save_round_trip` ──
  ``roles_csv`` の決定性 + 構造的等価性 + Tx commit / rollback。

``docs/features/workflow-repository/test-design.md`` 準拠。
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
from sqlalchemy import event, select

from tests.factories.workflow import (
    build_v_model_payload,
    make_stage,
    make_transition,
    make_workflow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# §確定 B: delete-then-insert replacement semantics (TC-IT-WFR-009)
# ---------------------------------------------------------------------------
class TestSaveDeleteThenInsert:
    """TC-IT-WFR-009: ``save`` が side-table 行を丸ごと置換する (§確定 B)。"""

    async def test_save_replaces_stage_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-009: 3 ステージ → 1 ステージが workflow_stages で 1 行として反映される。

        **同じ workflow_id** を持つ新しい単一ステージ Workflow を構築して再 save する。
        §確定 B 契約により、side-table は新しい状態のみを反映し、
        古いステージが残骸として残ってはならない。
        """
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        stage_c = make_stage(name="C")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        transition_bc = make_transition(from_stage_id=stage_b.id, to_stage_id=stage_c.id)
        original = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(original)

        # 同じ id で 1 ステージのみの新しい Workflow を構築。
        replacement_stage = make_stage(name="残ったステージ")
        replacement = make_workflow(
            workflow_id=original.id,
            name=original.name,
            stages=[replacement_stage],
            transitions=[],
            entry_stage_id=replacement_stage.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(replacement)

        # side-table は新状態のみを示し、古い+新しいの混在ではないこと。
        async with session_factory() as session:
            stage_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == original.id)
                    )
                ).scalars()
            )
        assert len(stage_rows) == 1
        assert stage_rows[0].name == "残ったステージ"


# ---------------------------------------------------------------------------
# §確定 B: 5-step SQL order (TC-IT-WFR-010)
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-IT-WFR-010: ``save`` が §確定 B の 5 ステップ順序で SQL を発行する。

    **sync** engine に ``before_cursor_execute`` リスナを取り付け、ダイアレクトが
    実際に発行する SQL 文字列を観測する。リスナは各 statement をキャプチャ
    リストに追加し、その後プレフィックスシーケンスが設計の 5 ステップと
    一致することを assert する。dispatcher / ORM は余分な SAVEPOINT / BEGIN
    を発行しうるため、それらを除外する ── 契約は *DML* プレフィックスにある。

    empire-repository TC-IT-EMR-011 と同じハーネス。後続 5 つの Repository PR は
    本テンプレートを再利用すべき。
    """

    async def test_save_emits_upsert_then_delete_insert_pairs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-010: 5 ステップの DML 順序が §確定 B に一致する。

        workflows UPSERT → workflow_stages DEL+INS → workflow_transitions DEL+INS。
        """
        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement.strip())

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            # V-model ペイロードは 13 ステージ + 15 トランジションで動作する ──
            # 最も忙しい ``save()`` 形状であり、SQL 順序観測に適している。
            from bakufu.domain.workflow import Workflow

            workflow = Workflow.from_dict(build_v_model_payload())
            async with session_factory() as session, session.begin():
                await SqliteWorkflowRepository(session).save(workflow)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # 注目する 5 つの DML statement のみにフィルタ（BEGIN / SAVEPOINT /
        # RELEASE / COMMIT のノイズを除外）。
        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in (
                    "INSERT INTO WORKFLOWS",
                    "DELETE FROM WORKFLOW_",
                    "INSERT INTO WORKFLOW_",
                )
            )
        ]
        # Step 1（UPSERT workflows）→ Step 2（DELETE workflow_stages）→
        # Step 3（INSERT workflow_stages）→ Step 4（DELETE workflow_transitions）→
        # Step 5 (INSERT workflow_transitions)。
        assert len(dml) >= 5, (
            f"[FAIL] save emitted only {len(dml)} DML statements; expected ≥5.\n"
            f"Next: verify save() executes the §確定 B 5-step sequence. "
            f"Captured DML: {dml}"
        )
        assert dml[0].upper().startswith("INSERT INTO WORKFLOWS")
        assert dml[1].upper().startswith("DELETE FROM WORKFLOW_STAGES")
        assert dml[2].upper().startswith("INSERT INTO WORKFLOW_STAGES")
        assert dml[3].upper().startswith("DELETE FROM WORKFLOW_TRANSITIONS")
        assert dml[4].upper().startswith("INSERT INTO WORKFLOW_TRANSITIONS")


# ---------------------------------------------------------------------------
# スモークテスト: 未知の workflow_id は既存の行と衝突しない
# ---------------------------------------------------------------------------
class TestSaveDistinctWorkflowsAreIndependent:
    """Workflow 間の副作用隔離。"""

    async def test_save_one_does_not_disturb_another(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Workflow B を save しても Workflow A のステージは削除されない。

        §確定 B の ``DELETE WHERE workflow_id = ?`` ステップは save 中の
        workflow_id にスコープされる。スコープなし DELETE を発行する粗末な
        Repository は DB 内の他のすべての Workflow を破壊しうる。
        前後スナップショットでスコーピングを assert する。
        """
        workflow_a = make_workflow()
        workflow_b = make_workflow()
        # id が別個であることのサニティチェック。
        assert workflow_a.id != workflow_b.id

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow_a)

        # B を save → A は無傷でなければならない。
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow_b)

        async with session_factory() as session:
            a_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(
                            WorkflowStageRow.workflow_id == workflow_a.id
                        )
                    )
                ).scalars()
            )
            b_rows = list(
                (
                    await session.execute(
                        select(WorkflowStageRow).where(
                            WorkflowStageRow.workflow_id == workflow_b.id
                        )
                    )
                ).scalars()
            )

        assert len(a_rows) == 1
        assert len(b_rows) == 1

        # サニティ: 2 つの Workflow がステージ行を共有していない。
        a_stage_ids = {row.stage_id for row in a_rows}
        b_stage_ids = {row.stage_id for row in b_rows}
        assert a_stage_ids.isdisjoint(b_stage_ids)

    async def test_unknown_workflow_id_returns_none_after_other_saves(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """DB が空でなくても、未知 id の find_by_id は None を返す。"""
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())

        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(unknown_id)
        assert fetched is None
