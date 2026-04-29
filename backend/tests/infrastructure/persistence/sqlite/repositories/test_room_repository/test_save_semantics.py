"""Room Repository: save() のセマンティクス ── delete-then-insert + ORDER BY + Tx 境界。

TC-UT-RR-002 / 003 / 010 / 011 ── §確定 R1-B の 3 ステップ save フロー契約 +
ORDER BY 観測 + Tx 境界 + ラウンドトリップ等価性。

§確定 R1-B の 3 ステップ:
    1. ``rooms`` UPSERT (id PK, ON CONFLICT で 5 スカラーカラムを更新)
    2. ``room_members`` DELETE WHERE room_id = ?
    3. ``room_members`` 一括 INSERT（members が空のときはスキップ）

ORDER BY（day 1 から踏襲する §BUG-EMR-001）:
    ``find_by_id`` は room_members に ``ORDER BY agent_id, role`` を発行し、
    SQLite の内部スキャン順に左右されない決定性を持つメンバリストとする。

``docs/features/room-repository/test-design.md`` 準拠。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import Role
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.room_members import RoomMemberRow
from sqlalchemy import event, select

from tests.factories.room import (
    make_agent_membership,
    make_leader_membership,
    make_populated_room,
    make_room,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-RR-002: 3-step delete-then-insert SQL order (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-UT-RR-002: ``save`` が §確定 R1-B の 3 ステップ DML シーケンスを発行する。

    ``before_cursor_execute`` リスナで観測し、以下を assert する:

    1. ``INSERT INTO rooms`` (ON CONFLICT DO UPDATE による UPSERT)
    2. ``DELETE FROM room_members``
    3. ``INSERT INTO room_members``
    """

    async def test_save_emits_upsert_then_delete_insert(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """3 ステップの DML 順序が §確定 R1-B に一致する。"""
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
            # 3 ステップの DML すべてが発火するよう、メンバを持つ Room を構築する。
            # 空 Room ではステップ 3（INSERT room_members）がスキップされる。
            room = make_populated_room(workflow_id=seeded_workflow_id)
            async with session_factory() as session, session.begin():
                await SqliteRoomRepository(session).save(room, seeded_empire_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in (
                    "INSERT INTO ROOMS",
                    "DELETE FROM ROOM_MEMBERS",
                    "INSERT INTO ROOM_MEMBERS",
                )
            )
        ]
        assert len(dml) >= 3, (
            f"[FAIL] save emitted only {len(dml)} DML statements; expected >=3.\n"
            f"Captured DML: {dml}"
        )
        assert dml[0].upper().startswith("INSERT INTO ROOMS"), (
            f"[FAIL] Step 1 must be UPSERT INTO rooms; got: {dml[0]!r}"
        )
        assert dml[1].upper().startswith("DELETE FROM ROOM_MEMBERS"), (
            f"[FAIL] Step 2 must be DELETE FROM room_members; got: {dml[1]!r}"
        )
        assert dml[2].upper().startswith("INSERT INTO ROOM_MEMBERS"), (
            f"[FAIL] Step 3 must be INSERT INTO room_members; got: {dml[2]!r}"
        )

    async def test_save_empty_room_skips_member_insert(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """メンバなしの Room はステップ 3（INSERT room_members）をスキップする。

        ``save()`` には明示的な ``if member_rows:`` ガードがある (§確定 R1-B)。
        SQL 的には空 INSERT も no-op だが、本テストは短絡経路を確認する ──
        ガードを除去して空 INSERT を発行する回帰は、振る舞いテストだけでは捕まえられない。
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
            # 明示的に空 members リスト。
            room = make_room(members=[], workflow_id=seeded_workflow_id)
            async with session_factory() as session, session.begin():
                await SqliteRoomRepository(session).save(room, seeded_empire_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        room_member_inserts = [
            s for s in captured if s.upper().startswith("INSERT INTO ROOM_MEMBERS")
        ]
        assert room_member_inserts == [], (
            f"[FAIL] save emitted INSERT INTO room_members for empty Room.\n"
            f"Next: the ``if member_rows:`` guard must prevent an empty INSERT.\n"
            f"Captured: {room_member_inserts}"
        )


# ---------------------------------------------------------------------------
# TC-UT-RR-003: ORDER BY contract (§BUG-EMR-001 inherited from day 1)
# ---------------------------------------------------------------------------
class TestFindByIdOrderByContract:
    """TC-UT-RR-003: ``find_by_id`` が room_members に ``ORDER BY agent_id, role`` を発行する。

    empire-repository BUG-EMR-001 のクロージャが ORDER BY 契約を凍結し、
    Room Repository は PR #33 から踏襲する。これらの句がないと SQLite は
    内部スキャン順で行を返し、``Room == Room`` ラウンドトリップ等価性
    （Aggregate がメンバリスト同士で比較する）が壊れる。
    """

    async def test_find_by_id_emits_order_by_agent_id_role(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``find_by_id`` が ``ORDER BY room_members.agent_id, room_members.role`` を発行する。"""
        room = make_populated_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

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
                await SqliteRoomRepository(session).find_by_id(room.id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        member_selects = [
            stmt for stmt in captured if "FROM room_members" in stmt and "SELECT" in stmt.upper()
        ]
        assert member_selects, "find_by_id must SELECT from room_members"
        assert any("ORDER BY" in stmt.upper() and "agent_id" in stmt for stmt in member_selects), (
            f"[FAIL] find_by_id missing ``ORDER BY agent_id``.\n"
            f"Captured room_members SELECTs: {member_selects}"
        )
        assert any("ORDER BY" in stmt.upper() and "role" in stmt for stmt in member_selects), (
            f"[FAIL] find_by_id missing ``ORDER BY role``.\n"
            f"Captured room_members SELECTs: {member_selects}"
        )

    async def test_member_list_deterministic_across_saves(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """複数回 find_by_id を呼んでも同じ ORDER BY 順でメンバが返る。

        異なる agent_id を持つメンバ 3 件で Room を seed し、find_by_id を
        2 回連続で呼んだ結果が同一のメンバリストになることを確認する ──
        ORDER BY が SQLite ページをまたいで決定的であることを示す。
        """
        from uuid import UUID as _UUID

        # 別個の 3 つの agent ID。ORDER BY 不在を検出できるよう、
        # 意図的に UUID hex の昇順にはしない。
        a1 = _UUID("aaaaaaaa-0000-0000-0000-000000000001")
        a2 = _UUID("aaaaaaaa-0000-0000-0000-000000000002")
        a3 = _UUID("aaaaaaaa-0000-0000-0000-000000000003")

        room = make_room(
            workflow_id=seeded_workflow_id,
            members=[
                make_leader_membership(agent_id=a3),
                make_agent_membership(agent_id=a1, role=Role.DEVELOPER),
                make_agent_membership(agent_id=a2, role=Role.REVIEWER),
            ],
        )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            first = await SqliteRoomRepository(session).find_by_id(room.id)
        async with session_factory() as session:
            second = await SqliteRoomRepository(session).find_by_id(room.id)

        assert first is not None
        assert second is not None
        assert [m.agent_id for m in first.members] == [m.agent_id for m in second.members], (
            "[FAIL] find_by_id returns members in different orders across calls.\n"
            "Next: ensure ORDER BY agent_id, role is present on the room_members SELECT."
        )


# ---------------------------------------------------------------------------
# TC-UT-RR-002 (delete-then-insert replacement semantics)
# ---------------------------------------------------------------------------
class TestSaveReplacesMemberRows:
    """``save`` が room_members を丸ごと置換する (§確定 R1-B ステップ 2-3)。"""

    async def test_save_replaces_member_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """メンバ 2 → 1 が room_members で 1 行として反映される（残骸なし）。

        DELETE-then-INSERT パターンを検証する: メンバを減らして再 save しても、
        room_members に古い行が残ってはならない。
        """
        # 初期状態は 2 メンバ。
        original = make_room(
            workflow_id=seeded_workflow_id,
            members=[
                make_leader_membership(),
                make_agent_membership(role=Role.DEVELOPER),
            ],
        )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(original, seeded_empire_id)

        # メンバ 1 名で再 save。
        solo_member = make_leader_membership()
        replacement = original.model_copy(update={"members": [solo_member]})
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(replacement, seeded_empire_id)

        async with session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(RoomMemberRow).where(RoomMemberRow.room_id == original.id)
                    )
                ).scalars()
            )
        assert len(rows) == 1
        assert rows[0].role == solo_member.role.value


# ---------------------------------------------------------------------------
# TC-UT-RR-011: round-trip equality (_to_row / _from_row via DB)
# ---------------------------------------------------------------------------
class TestRoundTripEquality:
    """TC-UT-RR-011: save → find_by_id ラウンドトリップで Room の同一性が保たれる。

    本テストはデフォルトの ``prompt_kit.prefix_markdown=''``（secret なし）を使うため、
    マスキングは no-op となり full ``==`` が成立する。secret を含むラウンドトリップは
    §確定 R1-J §不可逆性 により非等価になる ── その経路は
    :mod:`...test_masking_prompt_kit` で扱う。
    """

    async def test_populated_room_round_trips(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """メンバ 2 名の Room が構造的にラウンドトリップする（ORDER BY を考慮）。"""
        room = make_populated_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            restored = await SqliteRoomRepository(session).find_by_id(room.id)

        assert restored is not None
        assert restored.id == room.id
        assert restored.name == room.name
        assert restored.description == room.description
        assert restored.archived == room.archived
        assert restored.workflow_id == room.workflow_id
        assert restored.prompt_kit == room.prompt_kit
        # メンバは ORDER BY (agent_id, role) で返るため、
        # 元側を (agent_id, role) で sort してから比較する（ORDER BY を意識した assertion）。
        original_sorted = sorted(room.members, key=lambda m: (str(m.agent_id), m.role.value))
        assert len(restored.members) == len(original_sorted)
        for got, want in zip(restored.members, original_sorted, strict=True):
            assert got.agent_id == want.agent_id
            assert got.role == want.role


# ---------------------------------------------------------------------------
# TC-UT-RR-010: Tx boundary responsibility separation (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestTxBoundaryRespectedByRepository:
    """TC-UT-RR-010: Repository は commit / rollback を呼ばない (§確定 R1-B)。"""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """外側の ``async with session.begin()`` が save を commit する。"""
        room = make_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``begin()`` 内の例外が 3 ステップの DML すべてをロールバックする。

        Room 行と room_members は同一の呼び出し側管理トランザクションに参加する。
        単一の未捕捉例外が **すべて** を破棄せねばならない。
        """

        class _BoomError(Exception):
            """ロールバック経路を駆動する合成例外。"""

        room = make_populated_room(workflow_id=seeded_workflow_id)

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteRoomRepository(session).save(room, seeded_empire_id)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)
        assert fetched is None

        # room_members も空 ── §確定 R1-B の契約により、3 ステップは
        # 呼び出し側 UoW 下で 1 つの論理操作として扱われる。
        async with session_factory() as session:
            member_rows = (
                await session.execute(select(RoomMemberRow).where(RoomMemberRow.room_id == room.id))
            ).all()
        assert member_rows == []

    async def test_repository_does_not_commit_implicitly(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``begin()`` の外側での ``save`` は自動 commit しない (§確定 R1-B)。"""
        room = make_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session:
            await SqliteRoomRepository(session).save(room, seeded_empire_id)
            # AsyncSession の __aexit__ が処理中の tx をロールバックする。

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)
        assert fetched is None, (
            "[FAIL] Room persisted without an outer commit.\n"
            "Next: SqliteRoomRepository.save() must not call session.commit()."
        )
