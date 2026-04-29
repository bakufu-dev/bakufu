"""Room Repository: DB制約 + アーキテクチャテスト参照。

TC-IT-RR-009 / TC-IT-RR-013-arch — **UNIQUE(room_id, agent_id, role)
二重防衛** (§確定 R1-D) と CI レイヤー2 アーキテクチャテスト相互参照。

§確定 R1-D: 重複 (room_id, agent_id, role) トリプレットは **2つのレイヤー** で禁止:

1. **Aggregate レベル**: Room 構築時にメンバー一意性を検証。
2. **DB レベル**: 明示的 ``UniqueConstraint("room_id", "agent_id", "role",
   name="uq_room_members_triplet")`` が INSERT を物理的に拒否 —
   Aggregate をバイパスするコードパス（生 SQL、将来の Repository 実装、
   ダンプ/リストア移行など）の最終防衛線。

このテストは Aggregate を迂回する生 SQL を書いて **レイヤー2を単独で** 実行。
UniqueConstraint DDL をドロップするリグレッションは 2 番目の INSERT を
サイレントに成功させてしまう。

また以下もテスト:
* ``rooms.workflow_id FK RESTRICT``: Workflow を削除するもルームがそれを
  参照 → ``IntegrityError`` を発生させる必要 (§確定 R1-I)。
* ``room_members.room_id FK CASCADE``: ルームを削除するとカスケードして
  room_members 行に伝播 (§確定 R1-C Room エンティティカスケード)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-RR-009: UNIQUE(room_id, agent_id, role) 二重防衛 (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestUniqueRoomMemberTripletDoubleDefense:
    """TC-IT-RR-009: 重複 (room_id, agent_id, role) は IntegrityError を発生させる。

    Aggregate のメンバー検証が第1層；このテストは生 SQL を直接書いて
    バイパスするため DB制約が唯一つのサイレント重複を防ぐもの。
    最初の INSERT は成功する必要；2番目は ``IntegrityError`` を発生させる必要。
    """

    async def test_duplicate_triplet_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """TC-IT-RR-009: 同じ (room_id, agent_id, role) を2回 INSERT → IntegrityError。"""
        from datetime import UTC, datetime

        from sqlalchemy.exc import IntegrityError

        room_id = uuid4()
        agent_id = uuid4()
        empire_id = seeded_empire_id
        workflow_id = seeded_workflow_id

        # room_members FK が解決するよう、最初に rooms 行をシード。
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, "
                    ":prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": empire_id.hex,
                    "workflow_id": workflow_id.hex,
                    "name": "constraint-test-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

        joined_at = datetime.now(UTC).isoformat()

        # 最初のメンバー INSERT — 成功する必要。
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                    "VALUES (:room_id, :agent_id, :role, :joined_at)"
                ),
                {
                    "room_id": room_id.hex,
                    "agent_id": agent_id.hex,
                    "role": "LEADER",
                    "joined_at": joined_at,
                },
            )

        # 同じ (room_id, agent_id, role) トリプレットでの 2 番目 INSERT —
        # uq_room_members_triplet 制約が拒否する必要。
        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                        "VALUES (:room_id, :agent_id, :role, :joined_at)"
                    ),
                    {
                        "room_id": room_id.hex,
                        "agent_id": agent_id.hex,
                        "role": "LEADER",  # 同じロール → 同じトリプレット
                        "joined_at": joined_at,
                    },
                )

    async def test_same_agent_different_roles_are_permitted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """同じ (room_id, agent_id) で異なるロールは例外を発生させる必要なし。

        一意性は **トリプレット** にスコープされることを確認 —
        同じ (room_id, agent_id) の異なるロールは異なるメンバーシップ
        レコードを表す（例：DEVELOPER と REVIEWER の両方であるエージェント）。
        """
        from datetime import UTC, datetime

        room_id = uuid4()
        agent_id = uuid4()

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": seeded_empire_id.hex,
                    "workflow_id": seeded_workflow_id.hex,
                    "name": "multi-role-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

        joined_at = datetime.now(UTC).isoformat()
        async with session_factory() as session, session.begin():
            for role in ("LEADER", "REVIEWER"):
                await session.execute(
                    text(
                        "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                        "VALUES (:room_id, :agent_id, :role, :joined_at)"
                    ),
                    {
                        "room_id": room_id.hex,
                        "agent_id": agent_id.hex,
                        "role": role,
                        "joined_at": joined_at,
                    },
                )

        # 両方の行が存在; トリプレット一意性は発動しなかった。
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM room_members WHERE room_id = :room_id"),
                {"room_id": room_id.hex},
            )
            count = result.scalar_one()
        assert count == 2


# ---------------------------------------------------------------------------
# TC-IT-RR-009 補強: workflow_id FK RESTRICT (§確定 R1-I)
# ---------------------------------------------------------------------------
class TestWorkflowFkRestrict:
    """``rooms.workflow_id`` FK RESTRICT は Workflow 削除時の孤立 Room を防ぐ。

    §確定 R1-I: Workflow は Room の*参照*ターゲット、所有者ではない。
    Workflow が削除される一方でルームがそれをまだ参照することは
    DB レベルのハード失敗 — アプリケーションレイヤーのチェックのみでは
    生 SQL パスに対して不十分。

    注: SQLite FK の強制実行は ``PRAGMA foreign_keys = ON`` を要求し、
    本番エンジンは接続時に有効化。
    """

    async def test_delete_referenced_workflow_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Room が参照中に workflow を DELETE → IntegrityError。"""
        from sqlalchemy.exc import IntegrityError

        room_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": seeded_empire_id.hex,
                    "workflow_id": seeded_workflow_id.hex,
                    "name": "restrict-test-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )

        # 次に、room が参照している workflow を削除しようとする ──
        # RESTRICT が発動しなければならない。
        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text("DELETE FROM workflows WHERE id = :id"),
                    {"id": seeded_workflow_id.hex},
                )


# ---------------------------------------------------------------------------
# TC-IT-RR-009 補強: room_members CASCADE DELETE (§確定 R1-C)
# ---------------------------------------------------------------------------
class TestRoomMembersCascadeOnRoomDelete:
    """親 Room 削除時に room_members 行が削除される。

    ``room_members.room_id REFERENCES rooms.id ON DELETE CASCADE`` ——
    Room 行削除はメンバー行にカスケードする必須。Room 削除後に
    孤立 room_members 行が蓄積することを防ぐ。
    """

    async def test_cascade_deletes_member_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """rooms 行削除時に該当 room_members 行すべてにカスケードする。"""
        from datetime import UTC, datetime

        room_id = uuid4()
        joined_at = datetime.now(UTC).isoformat()

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO rooms "
                    "(id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) VALUES "
                    "(:id, :empire_id, :workflow_id, :name, :description, :prefix, :archived)"
                ),
                {
                    "id": room_id.hex,
                    "empire_id": seeded_empire_id.hex,
                    "workflow_id": seeded_workflow_id.hex,
                    "name": "cascade-test-room",
                    "description": "",
                    "prefix": "",
                    "archived": False,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO room_members (room_id, agent_id, role, joined_at) "
                    "VALUES (:room_id, :agent_id, :role, :joined_at)"
                ),
                {
                    "room_id": room_id.hex,
                    "agent_id": uuid4().hex,
                    "role": "LEADER",
                    "joined_at": joined_at,
                },
            )

        # Delete the parent room — member rows must cascade.
        async with session_factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM rooms WHERE id = :id"),
                {"id": room_id.hex},
            )

        async with session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM room_members WHERE room_id = :room_id"),
                {"room_id": room_id.hex},
            )
            count = result.scalar_one()
        assert count == 0, (
            f"[FAIL] room_members rows not cascaded on Room deletion (count={count}).\n"
            f"Next: ensure room_members.room_id FK carries ON DELETE CASCADE."
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-013-arch: Layer 2 arch-test reference — Room rows registered
# ---------------------------------------------------------------------------
class TestArchTestRegistrationStructure:
    """TC-IT-RR-013-arch: ``test_masking_columns.py`` parametrize リストが Room を含む。

    CI レイヤー2 アーキテクチャテストが Room テーブルをカバーするよう
    拡張されたことを交差検証（§確定 R1-E）。将来の PR が
    これらの登録を削除した場合（例：リファクタリング中の誤削除）、
    過剰/過少 masking 変更がサイレントに落ちるが、本テストが検出。
    """

    async def test_rooms_prompt_kit_prefix_markdown_in_masking_contract(self) -> None:
        """``rooms.prompt_kit_prefix_markdown`` は MaskedText で登録される。"""
        from bakufu.infrastructure.persistence.sqlite.base import MaskedText

        from tests.architecture.test_masking_columns import (
            _MASKING_CONTRACT,  # pyright: ignore[reportPrivateUsage]
        )

        assert ("rooms", "prompt_kit_prefix_markdown", MaskedText) in _MASKING_CONTRACT, (
            "[FAIL] rooms.prompt_kit_prefix_markdown missing from _MASKING_CONTRACT.\n"
            "Next: re-add the room §確定 G 実適用 row to "
            "tests/architecture/test_masking_columns.py."
        )

    async def test_room_members_in_no_mask_list(self) -> None:
        """``room_members`` は no-mask テーブル（agent_id は secret ではない）。"""
        from tests.architecture.test_masking_columns import (
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        assert "room_members" in _NO_MASK_TABLES, (
            "[FAIL] room_members missing from _NO_MASK_TABLES.\n"
            "Next: §確定 R1-E designates room_members as 'masking 対象なし'."
        )

    async def test_rooms_partial_mask_template_registered(self) -> None:
        """``rooms`` は partial-mask テンプレートリストに登録される。"""
        from tests.architecture.test_masking_columns import (
            _PARTIAL_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        partial = dict(_PARTIAL_MASK_TABLES)
        assert partial.get("rooms") == "prompt_kit_prefix_markdown", (
            f"[FAIL] rooms partial-mask declared {partial.get('rooms')!r}, "
            f"expected 'prompt_kit_prefix_markdown'.\n"
            f"Next: §逆引き表 freezes prompt_kit_prefix_markdown as the sole "
            f"masked column on rooms (§確定 R1-E)."
        )
