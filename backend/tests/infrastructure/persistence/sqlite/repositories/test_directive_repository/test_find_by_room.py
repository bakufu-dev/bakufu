"""Directive Repository: find_by_room ORDER BY + ルームスコーピングテスト。

TC-UT-DRR-004 / 004b / 004c / 004d / 004e。

§確定 R1-D: find_by_room は最新優先で Directive を返し、id DESC でタイブレーク
(BUG-EMR-001 規約 — ORDER BY created_at DESC のみは複数の Directive が
同じタイムスタンプを共有する場合、非決定的)。

``docs/features/directive-repository/test-design.md`` 準拠。
Issue #34 — M2 0006。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
    SqliteDirectiveRepository,
)
from sqlalchemy import event

from tests.factories.directive import make_directive
from tests.infrastructure.persistence.sqlite.repositories.test_directive_repository.conftest import (
    seed_room,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-DRR-004: ORDER BY created_at DESC, id DESC + SQL log (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestFindByRoomOrderBy:
    """TC-UT-DRR-004: find_by_room は id DESC タイブレーカーで最新優先を返す。"""

    async def test_find_by_room_returns_directives_newest_first(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Directive は最新優先 (created_at DESC) で返される。"""
        oldest = make_directive(
            target_room_id=seeded_room_id,
            created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )
        middle = make_directive(
            target_room_id=seeded_room_id,
            created_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
        )
        newest = make_directive(
            target_room_id=seeded_room_id,
            created_at=datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC),
        )
        # 非時系列順で save し、ソートが挿入順ではないことを示す
        for d in (middle, oldest, newest):
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(d)

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)

        assert len(results) == 3
        assert results[0].id == newest.id
        assert results[1].id == middle.id
        assert results[2].id == oldest.id

    async def test_find_by_room_emits_order_by_created_at_and_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_room_id: UUID,
    ) -> None:
        """SQL ログに ORDER BY created_at DESC, id DESC が含まれる (§確定 R1-D)。

        BUG-EMR-001 規約の回帰検知の基点: 実装が ``id DESC`` を削除したら
        このテストは失敗する。
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement)

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            async with session_factory() as session:
                await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        directive_selects = [
            s for s in captured if "FROM directives" in s and "SELECT" in s.upper()
        ]
        assert directive_selects, "find_by_room は directives から SELECT しなければならない"
        target_stmt = directive_selects[0].lower()
        assert "order by" in target_stmt and "created_at" in target_stmt, (
            f"[FAIL] find_by_room SQL missing ORDER BY created_at.\n"
            f"Captured: {directive_selects[0]!r}"
        )
        assert "id" in target_stmt, (
            f"[FAIL] find_by_room SQL ORDER BY missing id DESC tiebreaker (BUG-EMR-001 規約).\n"
            f"Captured: {directive_selects[0]!r}\n"
            f"Next: add .order_by(DirectiveRow.created_at.desc(), DirectiveRow.id.desc())"
        )

    async def test_find_by_room_count_matches_saved(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """find_by_room は保存した Directive の正確な数を返す。"""
        for _ in range(4):
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(
                    make_directive(target_room_id=seeded_room_id)
                )

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        assert len(results) == 4


# ---------------------------------------------------------------------------
# TC-UT-DRR-004b: 空の Room は [] を返す (None ではなく)
# ---------------------------------------------------------------------------
class TestFindByRoomEmpty:
    """TC-UT-DRR-004b: find_by_room は Directive がない Room に対して [] を返す。"""

    async def test_find_by_room_empty_room_returns_empty_list(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Directive がない Room → [] (空リスト、None ではない)。"""
        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        assert results == [], (
            f"[FAIL] find_by_room returned {results!r} instead of [] for empty Room.\n"
            "Next: ensure find_by_room returns [] not None when no rows found."
        )

    async def test_find_by_room_unknown_room_returns_empty_list(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """未知の room_id (行が存在しない) → [] (None ではなく、エラーでもない)。"""
        unknown_room_id = uuid4()
        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(unknown_room_id)
        assert results == []


# ---------------------------------------------------------------------------
# TC-UT-DRR-004c: Room スコープ隔離 (IDOR 防止)
# ---------------------------------------------------------------------------
class TestFindByRoomScopeIsolation:
    """TC-UT-DRR-004c: find_by_room は Room スコープを厳密に適用する。"""

    async def test_find_by_room_isolates_directives_by_room(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """room_a からの Directive は room_b のクエリで返されない。

        Room 間の隔離: WHERE target_room_id = :room_id スコープなしであれば、
        room_a の Directive が room_b のクエリに漏洩する可能性がある。
        """
        room_a = await seed_room(session_factory)
        room_b = await seed_room(session_factory)

        d_in_a = make_directive(target_room_id=room_a)
        d_in_b = make_directive(target_room_id=room_b)

        async with session_factory() as session, session.begin():
            repo = SqliteDirectiveRepository(session)
            await repo.save(d_in_a)
            await repo.save(d_in_b)

        async with session_factory() as session:
            results_a = await SqliteDirectiveRepository(session).find_by_room(room_a)

        ids_in_a = {d.id for d in results_a}
        assert d_in_a.id in ids_in_a
        assert d_in_b.id not in ids_in_a, (
            "[FAIL] find_by_room leaked a Directive from room_b into room_a query.\n"
            "Next: verify WHERE target_room_id = :room_id is in the SELECT."
        )


# ---------------------------------------------------------------------------
# TC-UT-DRR-004d: _from_row 全属性復元
# ---------------------------------------------------------------------------
class TestFindByRoomFromRowRestoration:
    """TC-UT-DRR-004d: find_by_room は _from_row で Directive を正しく補水する。"""

    async def test_find_by_room_restores_all_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """すべての Directive 属性 (id/text/target_room_id/created_at/task_id) が復元される。"""
        directive = make_directive(
            target_room_id=seeded_room_id,
            text="テスト用ディレクティブ",
            task_id=None,
        )
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)

        assert len(results) == 1
        restored = results[0]
        assert restored.id == directive.id
        assert restored.text == directive.text
        assert restored.target_room_id == directive.target_room_id
        assert restored.task_id == directive.task_id
        assert restored.created_at.tzinfo is not None, (
            "[FAIL] created_at lost timezone info in find_by_room _from_row restoration."
        )


# ---------------------------------------------------------------------------
# TC-UT-DRR-004e: id DESC タイブレーカー — 同一 created_at (BUG-EMR-001 規約)
# ---------------------------------------------------------------------------
class TestFindByRoomTiebreaker:
    """TC-UT-DRR-004e: created_at が同一のときの id DESC タイブレーカー。

    BUG-EMR-001 規約: ORDER BY created_at DESC だけでは複数の Directive が
    同じタイムスタンプを共有する場合に非決定的。id DESC (PK, UUID) が
    タイブレーカーでなければならない。

    このテストは **回帰検知パス**: 実装が ORDER BY 句から ``id DESC`` を削除した場合、
    返却順がエンジン依存（任意）になるためこのテストは失敗する。
    """

    async def test_same_created_at_ordered_by_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """同一 created_at の Directive 3 つ → id DESC 順で返される。

        UUID 文字列 (hex 形式) は辞書順比較。同じ created_at タイムスタンプで
        Directive 3 つを保存し、結果順が id DESC と一致することを検証 ——
        タイブレーカーが活作していることを証明。id DESC が削除されたら、
        順序が予測不可能になり、このアサーションは断続的に失敗する。
        """
        # created_at が区別できないよう固定の同一タイムスタンプを使用。
        shared_ts = datetime(9999, 1, 1, 0, 0, 0, tzinfo=UTC)

        d1 = make_directive(target_room_id=seeded_room_id, created_at=shared_ts)
        d2 = make_directive(target_room_id=seeded_room_id, created_at=shared_ts)
        d3 = make_directive(target_room_id=seeded_room_id, created_at=shared_ts)

        async with session_factory() as session, session.begin():
            repo = SqliteDirectiveRepository(session)
            await repo.save(d1)
            await repo.save(d2)
            await repo.save(d3)

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)

        assert len(results) == 3

        # 期待順序を構築: id DESC (UUID hex 文字列降順)
        ids = [d1.id, d2.id, d3.id]
        expected_order = sorted(ids, key=lambda uid: uid.hex, reverse=True)
        actual_order = [r.id for r in results]

        assert actual_order == expected_order, (
            f"[FAIL] find_by_room が id DESC タイブレーカーを適用していない"
            f"(BUG-EMR-001 規約)。\n"
            f"3 つの Directive すべてが同一 created_at={shared_ts.isoformat()}。\n"
            f"期待される id 順 (desc): {[uid.hex for uid in expected_order]}\n"
            f"実際の id 順:          {[uid.hex for uid in actual_order]}\n"
            f"次: .order_by(DirectiveRow.created_at.desc(), DirectiveRow.id.desc()) を追加"
        )
