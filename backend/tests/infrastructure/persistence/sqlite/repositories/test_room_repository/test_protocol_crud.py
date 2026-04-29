"""Room Repository: Protocol サーフェス + 基本 CRUD カバレッジ。

TC-UT-RR-001 / 004 / 005 / 006 ── エントリポイント挙動と
**4 メソッドの Protocol サーフェス** (``find_by_id`` / ``count`` / ``save`` /
``find_by_name``、§確定 R1-A + R1-F)。

``docs/features/room-repository/test-design.md`` 準拠。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from sqlalchemy import event

from tests.factories.room import make_populated_room, make_room
from tests.infrastructure.persistence.sqlite.repositories.test_room_repository.conftest import (
    seed_empire,
    seed_workflow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-RR-001: Protocol definition + 4-method surface (§確定 R1-A)
# ---------------------------------------------------------------------------
class TestRoomRepositoryProtocol:
    """TC-UT-RR-001: Protocol が 4 つの async メソッドを宣言する。"""

    async def test_protocol_declares_four_async_methods(self) -> None:
        """TC-UT-RR-001: ``RoomRepository`` が find_by_id / count / save / find_by_name を持つ。"""
        assert hasattr(RoomRepository, "find_by_id")
        assert hasattr(RoomRepository, "count")
        assert hasattr(RoomRepository, "save")
        assert hasattr(RoomRepository, "find_by_name")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-RR-001: ``SqliteRoomRepository`` を ``RoomRepository`` に代入できる。

        変数アノテーションが静的型アサーションとして機能する。pyright strict は、
        Protocol メソッドが欠落または誤シグネチャの場合に代入を拒否する。
        """
        async with session_factory() as session:
            repo: RoomRepository = SqliteRoomRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")
            assert hasattr(repo, "find_by_name")

    async def test_protocol_does_not_expose_count_by_empire(self) -> None:
        """TC-UT-RR-001: ``count_by_empire`` は Protocol に含まれない（YAGNI）。

        §確定 R1-A が ``count_by_empire`` を YAGNI として凍結したため、
        メソッドは公開 Protocol サーフェスに現れてはならない。再追加する将来の
        PR は §確定 R1-A の更新を先に行う必要がある。さもなくば本アサーションが発火する。
        """
        assert not hasattr(RoomRepository, "count_by_empire"), (
            "[FAIL] RoomRepository.count_by_empire must not exist (YAGNI, §確定 R1-A).\n"
            "Next: remove count_by_empire from the Protocol."
        )


# ---------------------------------------------------------------------------
# REQ-RR-002 (find_by_id basic round-trip)
# ---------------------------------------------------------------------------
class TestFindById:
    """find_by_id は保存済み Room を取得する。未知の id は None を返す。"""

    async def test_find_by_id_returns_saved_room(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``find_by_id(room.id)`` が構造的に等価な Room を返す（デフォルトでは secret なし）。

        デフォルト factory の ``prompt_kit.prefix_markdown=''`` には
        Schneier-#6 の secret が含まれないため、マスキングは no-op となり
        ラウンドトリップ等価性が成立する。secret を含む prefix のラウンドトリップは
        :mod:`...test_masking_prompt_kit` (§確定 R1-J §不可逆性) で扱う。
        """
        room = make_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)

        assert fetched is not None
        assert fetched == room

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """``find_by_id(uuid4())`` は例外を投げず ``None`` を返す。"""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(unknown_id)
        assert fetched is None

    async def test_find_by_id_hydrates_members(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``find_by_id`` がメンバを hydrate した Room を返す。"""
        room = make_populated_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)

        assert fetched is not None
        assert len(fetched.members) == 2  # make_populated_room による LEADER + DEVELOPER


# ---------------------------------------------------------------------------
# TC-UT-RR-004: count() must issue SQL-level COUNT(*)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-UT-RR-004: ``count()`` は ``SELECT COUNT(*)`` を発行し、行を全件スキャンしない。"""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """SQL ログが ``count()`` に対し ``SELECT count(*)`` を示す。

        empire-repository §確定 D 補強の契約に従う ── ``count()`` は Python へ
        Room 行を全件ストリームしてはならない。Room が大きな
        ``prompt_kit_prefix_markdown`` を持つようになると特に重要。
        """
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(workflow_id=seeded_workflow_id), seeded_empire_id
            )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(workflow_id=seeded_workflow_id), seeded_empire_id
            )

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
            async with session_factory() as session:
                count = await SqliteRoomRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        room_selects = [s for s in captured if "FROM rooms" in s]
        assert room_selects, "count() must issue at least one SELECT against rooms"
        for stmt in room_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(RoomRow)."
            )


# ---------------------------------------------------------------------------
# TC-UT-RR-005: find_by_name Empire-scoped (§確定 R1-F)
# ---------------------------------------------------------------------------
class TestFindByNameEmpireScoped:
    """TC-UT-RR-005: ``find_by_name`` が Empire スコープを強制する。

    §確定 R1-F に沿う 3 つの直交ケース:

    1. **ヒット**: ``empire_a`` 内の ``foo`` という名前の Room が返る。
    2. **同 Empire 内ミス**: ``empire_a`` 配下の ``bar`` という名前は None を返す。
    3. **Empire 間隔離**: ``foo`` が ``empire_a`` に存在しても、``empire_b`` 配下の
       ``foo`` 検索は None を返す。これが IDOR ガード ── ``WHERE empire_id=:empire_id``
       がなければ攻撃者が名前を推測して別テナントの Room を読み取れる。
    """

    async def test_find_by_name_returns_room_when_present(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """ヒット経路: name + empire_id ペアが Room を返す。"""
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        room = make_room(name="room_a", workflow_id=wf)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, empire_a)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_name(empire_a, "room_a")

        assert fetched is not None
        assert fetched.id == room.id
        assert fetched.name == "room_a"

    async def test_find_by_name_returns_none_when_name_missing(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """ミス経路: 既知 Empire 内の未知の名前は None を返す。"""
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(name="room_a", workflow_id=wf), empire_a
            )

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_name(empire_a, "nonexistent")
        assert fetched is None

    async def test_find_by_name_isolates_by_empire(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """**IDOR ガード**: 別 Empire 配下の同名は None を返す。

        本テストは test-design.md §確定 R1-F の中核契約。``WHERE empire_id`` 句を
        落とす回帰は攻撃者にテナント越境で Room を読ませてしまう ──
        本アサーションがそれを即座に表面化させる。
        """
        empire_a = await seed_empire(session_factory)
        empire_b = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        room_in_a = make_room(name="shared_name", workflow_id=wf)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room_in_a, empire_a)

        async with session_factory() as session:
            # 同じ名前を別の empire で検索する ── empire_a に "shared_name" が
            # 存在しても None を返さなければならない。
            fetched = await SqliteRoomRepository(session).find_by_name(empire_b, "shared_name")
        assert fetched is None, (
            "[FAIL] find_by_name leaked a Room across Empire boundaries.\n"
            "Next: verify the SQL contains ``WHERE empire_id = :empire_id`` "
            "(detailed-design.md §確定 R1-F). A missing scope clause is an IDOR."
        )

    async def test_find_by_name_emits_empire_scoped_sql(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """SQL ログに ``WHERE rooms.empire_id = ?`` と ``LIMIT 1`` が含まれる。

        上の振る舞いテストに対する多層防御: クロス Empire テストが行偶発で
        pass してしまっても、SQL 自体がスコープ句を持たねばならない。
        ``before_cursor_execute`` リスナを取り付け、empire_id 述語を grep する。
        """
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(name="room_a", workflow_id=wf), empire_a
            )

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
                await SqliteRoomRepository(session).find_by_name(empire_a, "room_a")
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # RoomId を検索するために ``rooms`` を叩いた SELECT を探す。
        room_id_selects = [s for s in captured if "FROM rooms" in s and "SELECT" in s.upper()]
        assert room_id_selects, "find_by_name must SELECT from rooms"
        # SELECT は empire_id 述語と LIMIT の両方を持たねばならない。
        target_stmt = room_id_selects[0]
        assert "empire_id" in target_stmt, (
            f"[FAIL] find_by_name SQL missing empire_id predicate.\nCaptured: {target_stmt!r}"
        )
        assert "LIMIT" in target_stmt.upper(), (
            f"[FAIL] find_by_name SQL missing LIMIT clause.\nCaptured: {target_stmt!r}"
        )


# ---------------------------------------------------------------------------
# TC-UT-RR-006: Lifecycle integration (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-UT-RR-006: save → 検索 → 更新の完全フロー。"""

    async def test_full_lifecycle_with_description_update(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Save → find_by_name → find_by_id → description 更新 → save。

        4 つの Protocol メソッドがエンドツーエンドで協調し、再 save 経由の
        description 更新が UPSERT 経路（§確定 R1-B 3 ステップの Step 1）で
        DB に到達することを検証する。
        """
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        original = make_room(
            name="lifecycle_room",
            description="初期説明",
            workflow_id=wf,
        )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(original, empire_a)

        async with session_factory() as session:
            via_name = await SqliteRoomRepository(session).find_by_name(empire_a, "lifecycle_room")
        assert via_name is not None
        assert via_name.description == "初期説明"

        async with session_factory() as session:
            via_id = await SqliteRoomRepository(session).find_by_id(original.id)
        assert via_id is not None
        assert via_id == via_name

        # 更新: description を変更して再 save。
        updated = original.model_copy(update={"description": "更新後の説明"})
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(updated, empire_a)

        async with session_factory() as session:
            after = await SqliteRoomRepository(session).find_by_id(original.id)
        assert after is not None
        assert after.description == "更新後の説明"
