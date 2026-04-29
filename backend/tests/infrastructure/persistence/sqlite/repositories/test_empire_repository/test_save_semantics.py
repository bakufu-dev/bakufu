"""Empire Repository: save() の挙動 ── delete-then-insert + Tx 境界.

TC-IT-EMR-006 / 007 / 011 / 012 + TC-UT-EMR-003 ── ``save()`` フローを
裏付ける §確定 B 契約とラウンドトリップ等価性。
Norman の 500 行ルールに従い、元の ``test_empire_repository.py`` から分割。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_room_refs import (
    EmpireRoomRefRow,
)
from sqlalchemy import select

from tests.factories.empire import make_empire, make_populated_empire, make_room_ref
from tests.infrastructure.persistence.sqlite.repositories.test_empire_repository.conftest import (
    seed_rooms,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


class TestSaveDeleteThenInsert:
    """TC-IT-EMR-006: ``save`` は side-table 行を一括置換する (§確定 B)。"""

    async def test_save_replaces_room_refs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-006: 2 rooms → 1 room は empire_room_refs で 1 行として反映される。"""
        original = make_populated_empire(n_rooms=2, n_agents=3)
        # save 前に seed できるよう、置換用 room ref を先行生成する。
        replacement_room = make_room_ref(name="残った部屋")

        # Alembic 0005 で empire_room_refs.room_id → rooms.id FK が追加された
        # (BUG-EMR-001 閉鎖)。empire_room_refs に登場し得る全 room_id を seed する。
        all_room_ids = [r.room_id for r in original.rooms] + [replacement_room.room_id]
        await seed_rooms(session_factory, original.id, all_room_ids)

        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(original)

        # 同じ id で 1 room だけの新しい Empire を構築する。
        replacement = make_empire(
            empire_id=original.id,
            name=original.name,
            rooms=[replacement_room],
            agents=list(original.agents),
        )
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(replacement)

        # side テーブルは古い + 新しいの merge ではなく新状態を反映せねばならない。
        async with session_factory() as session:
            room_rows = list(
                (
                    await session.execute(
                        select(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == original.id)
                    )
                ).scalars()
            )
        assert len(room_rows) == 1
        assert room_rows[0].name == "残った部屋"


class TestRoundTripStructuralEquality:
    """TC-IT-EMR-007 + TC-UT-EMR-003: save → find_by_id ラウンドトリップで等価性が保たれる。

    BUG-EMR-001 閉鎖: :meth:`SqliteEmpireRepository.find_by_id` は
    ``basic-design.md`` L127-128 と ``detailed-design.md`` §クラス設計 に従い、
    ``ORDER BY room_id`` / ``ORDER BY agent_id`` を発行する。
    ハイドレートされたリストは決定的になるため、以前の set ベースの
    ワークアラウンドは外し、契約に沿ったリスト順比較に置き換えた。

    テスト契約 (ORDER BY 物理保証): Repository の
    ``ORDER BY room_id`` / ``ORDER BY agent_id`` 設計契約を、入力 Empire の
    コレクションを同じキーでソートしてリスト等価を要求する形でアサートする。
    本アサートが失敗すれば SQL 契約のリグレッション (``ORDER BY`` が
    落ちた、もしくはカラムが変わった) を意味する。
    """

    async def test_populated_empire_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-007: ラウンドトリップが Empire アイデンティティと
        メンバーシップを ORDER BY 順で保持する。"""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        await seed_rooms(session_factory, empire.id, [r.room_id for r in empire.rooms])
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        assert restored.id == empire.id
        assert restored.name == empire.name
        # ORDER BY room_id / agent_id 物理保証: 復元される side-table
        # リストは決定的なので、リスト順等価が契約。期待リストは
        # Repository の ``ORDER BY`` と同じキーでソートしておく。
        assert restored.rooms == sorted(empire.rooms, key=lambda r: r.room_id)
        assert restored.agents == sorted(empire.agents, key=lambda a: a.agent_id)

    async def test_empty_empire_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-007: rooms / agents 空の Empire をラウンドトリップする。"""
        empire = make_empire()  # デフォルトで rooms=[] agents=[]
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        # 空ケース: リスト順の曖昧さは無いので完全な ``==`` で良い。
        assert restored == empire

    async def test_to_row_then_from_row_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-EMR-003: ``_to_row`` → save + find_by_id (≡ ``_from_row``) で等価性が保たれる。"""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        await seed_rooms(session_factory, empire.id, [r.room_id for r in empire.rooms])
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        assert restored.id == empire.id
        assert restored.name == empire.name
        # test_populated_empire_round_trip と同じ ORDER BY 認識のリスト比較 ──
        # BUG-EMR-001 閉鎖の根拠はクラス docstring を参照。
        assert restored.rooms == sorted(empire.rooms, key=lambda r: r.room_id)
        assert restored.agents == sorted(empire.agents, key=lambda a: a.agent_id)


# ---------------------------------------------------------------------------
# 確定 B: delete-then-insert 5 段階順序 + Tx 境界
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-IT-EMR-011: ``save`` は §確定 B の 5 ステップ順で SQL を発行する。

    **sync** エンジンに ``before_cursor_execute`` リスナを付け、方言が
    実際に発行する SQL 文字列を観察する。リスナは各文をキャプチャ用リストに
    append し、プレフィックス列が設計の 5 ステップに一致することをアサートする。
    ディスパッチャ / ORM は追加で SAVEPOINT / BEGIN を発行し得るので
    フィルタする ── 契約は *DML* のプレフィックスに対する。
    """

    async def test_save_emits_upsert_then_delete_insert_pairs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: object,  # AsyncEngine; リスナ API のため緩く型付け
    ) -> None:
        """TC-IT-EMR-011: empires UPSERT → empire_room_refs DEL+INS → empire_agent_refs DEL+INS。"""
        from sqlalchemy import event

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

        sync_engine = app_engine.sync_engine  # type: ignore[attr-defined]  # AsyncEngine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            empire = make_populated_empire(n_rooms=2, n_agents=3)
            await seed_rooms(session_factory, empire.id, [r.room_id for r in empire.rooms])
            async with session_factory() as session, session.begin():
                await SqliteEmpireRepository(session).save(empire)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # 注目したい 5 件の DML 文に絞る (BEGIN /
        # SAVEPOINT / RELEASE / COMMIT のノイズを除去)。
        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in ("INSERT INTO EMPIRES", "DELETE FROM EMPIRE", "INSERT INTO EMPIRE")
            )
        ]
        # Step 1（UPSERT empires）→ Step 2（DELETE empire_room_refs）→
        # Step 3（INSERT empire_room_refs）→ Step 4（DELETE
        # empire_agent_refs) → Step 5 (INSERT empire_agent_refs)。
        assert len(dml) >= 5
        assert dml[0].upper().startswith("INSERT INTO EMPIRES")
        assert dml[1].upper().startswith("DELETE FROM EMPIRE_ROOM_REFS")
        assert dml[2].upper().startswith("INSERT INTO EMPIRE_ROOM_REFS")
        assert dml[3].upper().startswith("DELETE FROM EMPIRE_AGENT_REFS")
        assert dml[4].upper().startswith("INSERT INTO EMPIRE_AGENT_REFS")


class TestTxBoundaryRespectedByRepository:
    """TC-IT-EMR-012: Repository は commit / rollback を呼ばない (§確定 B)。"""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-012 (commit): 外側の ``async with session.begin()``
        で save がコミットされる。"""
        empire = make_empire()
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            fetched = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-012 (rollback): ``begin()`` 内の例外で save がロールバックされる。"""

        class _BoomError(Exception):
            """ロールバック経路を駆動するための合成例外。"""

        empire = make_empire()
        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteEmpireRepository(session).save(empire)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteEmpireRepository(session).find_by_id(empire.id)
        # ロールバックはアトミックでなければならない ── 行は残らない。
        assert fetched is None
