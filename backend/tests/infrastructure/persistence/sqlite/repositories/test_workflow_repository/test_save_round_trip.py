"""Workflow Repository: save() ── roles_csv 決定性 + ラウンドトリップ + Tx 境界.

TC-IT-WFR-011 / 012 / 015 / 016 ── §確定 G の "sorted CSV" 決定性、
§確定 C のラウンドトリップ構造的等価、および §確定 B の Tx 境界責務分離。

Norman 500 行ルールに従い ``test_save_semantics.py`` から分割。
姉妹ファイル
:mod:`...test_workflow_repository.test_save_delete_then_insert` で
delete-then-insert + 5 ステップ DML 順 + ワークフロー横断 isolation スモークを扱う。

``docs/features/workflow-repository/test-design.md`` 準拠。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bakufu.domain.value_objects import Role
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from sqlalchemy import select, text

from tests.factories.workflow import (
    make_stage,
    make_transition,
    make_workflow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# §確定 G: roles_csv の sorted CSV 決定性 (TC-IT-WFR-011 / 012)
# ---------------------------------------------------------------------------
class TestRolesCsvSortedDeterminism:
    """TC-IT-WFR-011 / 012: ``roles_csv`` はソート済。同値 frozenset → 同値 CSV。

    §確定 G が「sorted CSV」を凍結する理由は、Python ``frozenset`` の
    iteration 順が実装依存だから。ソートしない場合、同一 Workflow を
    2 回 save() すると ``roles_csv`` のバイト列が異なってしまい、
    delete-then-insert の差分ノイズが発生する (ドメイン値は同一なのに
    行が *見かけ上* 変わる)。

    検証項目:

    1. **ラウンドトリップ復元** ── frozenset → CSV → frozenset で
       role 集合が保たれる (欠落も追加もない)。
    2. **バイト決定性** ── Stage の ``required_role`` を **異なる挿入順**
       (例: ``frozenset({DEVELOPER, REVIEWER})`` vs.
       ``frozenset({REVIEWER, DEVELOPER})``) で構築した 2 つの Workflow
       がバイト等価な ``roles_csv`` を DB に書く。
    """

    async def test_required_role_round_trips_via_roles_csv(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-011: ``frozenset[Role]`` は CSV ラウンドトリップに耐える。"""
        roles = frozenset({Role.DEVELOPER, Role.TESTER, Role.REVIEWER})
        stage = make_stage(required_role=roles)
        workflow = make_workflow(stages=[stage], entry_stage_id=stage.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        assert len(restored.stages) == 1
        assert restored.stages[0].required_role == roles
        assert isinstance(restored.stages[0].required_role, frozenset)

    async def test_same_role_set_yields_byte_identical_csv(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-012: 同じ ``frozenset`` はバイト等価な ``roles_csv`` を生む。

        ``required_role`` を異なる順の iterable から構築した 2 つの Stage
        だが、同一 ``frozenset`` を返す ── 永続化された ``roles_csv``
        文字列はバイト等価でなければならない。さもないと
        delete-then-insert が同じ行を毎回書き直す (差分ノイズ)。
        """
        roles_forward = frozenset({Role.DEVELOPER, Role.REVIEWER, Role.TESTER})
        roles_reverse = frozenset([Role.TESTER, Role.REVIEWER, Role.DEVELOPER])
        # frozenset の等価は集合等価 ── セットアップの確認。
        assert roles_forward == roles_reverse

        stage_a = make_stage(required_role=roles_forward)
        stage_b = make_stage(required_role=roles_reverse)
        workflow_a = make_workflow(stages=[stage_a], entry_stage_id=stage_a.id)
        workflow_b = make_workflow(stages=[stage_b], entry_stage_id=stage_b.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow_a)
            await SqliteWorkflowRepository(session).save(workflow_b)

        # 2 つの ``roles_csv`` セルを raw SQL で取得 ── SQLAlchemy は
        # 通常 TypeDecorator で実バイトを隠す (ここでは隠していないが、
        # 後続の Repository PR のために明示的な raw 形で意図を残す)。
        async with session_factory() as session:
            stmt = text(
                "SELECT roles_csv FROM workflow_stages "
                "WHERE workflow_id IN (:wf_a, :wf_b) ORDER BY workflow_id"
            )
            result = await session.execute(
                stmt,
                {"wf_a": workflow_a.id.hex, "wf_b": workflow_b.id.hex},
            )
            csv_values = sorted(row[0] for row in result)

        assert len(csv_values) == 2
        assert csv_values[0] == csv_values[1], (
            f"[FAIL] sorted-CSV determinism violated: {csv_values[0]!r} != {csv_values[1]!r}.\n"
            f"Next: verify _to_row uses ``sorted(role.value for role in stage.required_role)`` "
            f"per detailed-design.md §確定 G."
        )


# ---------------------------------------------------------------------------
# §確定 C: ラウンドトリップ構造的等価 (TC-IT-WFR-015)
# ---------------------------------------------------------------------------
class TestRoundTripStructuralEquality:
    """TC-IT-WFR-015: save → find_by_id ラウンドトリップで Workflow アイデンティティが保たれる。

    Workflow Repository は PR #1 から empire-repository の ``ORDER BY
    stage_id`` / ``ORDER BY transition_id`` 契約を継承している
    (BUG-EMR-001 の教訓を後追いではなく設計時に適用した)。Repository が
    ソートしたのと同じキーで *期待* リストをソートし、リスト順等価を
    契約とする。

    本ラウンドトリップテストは ``EXTERNAL_REVIEW`` ステージを意図的に
    避ける ── §確定 H §不可逆性 により ``find_by_id`` がそれらに対して
    raise するため。irreversibility は別途 :mod:`...test_masking` で検証。
    """

    async def test_multi_stage_workflow_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-015: 3 stage + 2 transition がリスト順等価でラウンドトリップ。"""
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        stage_c = make_stage(name="C")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        transition_bc = make_transition(from_stage_id=stage_b.id, to_stage_id=stage_c.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        assert restored.id == workflow.id
        assert restored.name == workflow.name
        assert restored.entry_stage_id == workflow.entry_stage_id
        # ORDER BY stage_id / transition_id 物理保証: 復元される side-table
        # リストは決定的なので、リスト順等価が契約。
        assert restored.stages == sorted(workflow.stages, key=lambda s: s.id)
        assert restored.transitions == sorted(workflow.transitions, key=lambda t: t.id)

    async def test_single_stage_workflow_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-015: 単一ステージ Workflow (entry == sink)
        は完全 ``==`` でラウンドトリップ。"""
        workflow = make_workflow()  # デフォルト = 1 WORK stage、0 transition
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        assert restored is not None
        # リスト順の曖昧さなし ── 完全 ``==`` で良い。
        assert restored == workflow


# ---------------------------------------------------------------------------
# §確定 B: Tx 境界責務分離 (TC-IT-WFR-016)
# ---------------------------------------------------------------------------
class TestTxBoundaryRespectedByRepository:
    """TC-IT-WFR-016: Repository は commit / rollback を呼ばない (§確定 B)。"""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-016 (commit): 外側 ``async with session.begin()`` で save がコミットされる。"""
        workflow = make_workflow()
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-016 (rollback): ``begin()`` 内の例外で save がロールバックされる。

        Workflow 行と (空でない可能性のある) stages / transitions は
        全て呼び出し側管理の同一トランザクションに参加する。``begin()``
        ブロック内の未捕捉例外 1 つで **全て** が消えなければならない ──
        Repository 自身は何もコミットしていないから。
        """

        class _BoomError(Exception):
            """ロールバック経路を駆動するための合成例外。"""

        # 3 stage Workflow を使い、ロールバック対象として stages + transitions
        # も Workflow 行と一緒に消えることを実証する。
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b],
            transitions=[transition_ab],
            entry_stage_id=stage_a.id,
        )

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteWorkflowRepository(session).save(workflow)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        # ロールバックはアトミックでなければならない ── 行は残らない。
        assert fetched is None

        # side テーブルも空 ── §確定 B 契約は、5 ステップ列が呼び出し側 UoW
        # 配下の **1 つ** の論理操作であり、5 つの別個の永続化ではない。
        async with session_factory() as session:
            stage_count = (
                await session.execute(
                    select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
                )
            ).all()
        assert stage_count == []

    async def test_repository_does_not_commit_implicitly(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-016 補強: ``begin()`` 外の ``save`` は自動コミットしない。

        Repository に紛れ込んだ ``await session.commit()`` があれば、
        ``async with session.begin()`` 無しの save が永続化されてしまい、
        後続の新規セッション読み取りで観測される。SQLAlchemy AsyncSession
        の既定は autobegin=True でトランザクショナル SELECT。本テストは
        ``begin()`` ブロックなしでセッションを開いて save を直接呼び、
        新規セッションで expire + 再読する。Repository の契約は ──
        コミットが発火しないので ── 行が **永続化されない**。
        """
        workflow = make_workflow()
        async with session_factory() as session:
            await SqliteWorkflowRepository(session).save(workflow)
            # ``commit()`` を呼ばずに意図的に終了 ── AsyncSession の
            # ``__aexit__`` が in-flight トランザクションをロールバックする。

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)
        # Repository は暗黙コミットしてはならない。
        assert fetched is None, (
            "[FAIL] Workflow row persisted without an outer commit.\n"
            "Next: SqliteWorkflowRepository.save() must not call "
            "session.commit() per §確定 B Tx 境界責務分離."
        )
