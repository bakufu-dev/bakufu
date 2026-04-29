""":class:`bakufu.application.ports.RoomRepository` の SQLite アダプタ。

§確定 R1-B の 3 ステップ保存フローを 2 つのテーブル（``rooms`` / ``room_members``）
に対して実装する:

1. ``rooms`` UPSERT（id 衝突時に workflow_id + name + description +
   prompt_kit_prefix_markdown + archived を更新。``prompt_kit_prefix_markdown``
   は :class:`MaskedText` 経由でバインドされるため、埋め込まれた API キー /
   OAuth トークン / Discord webhook シークレットは SQLite に到達する *前* に
   伏字化される — room §確定 G、§確定 R1-J 不可逆性凍結）。
2. ``room_members`` DELETE WHERE room_id = ?
3. ``room_members`` 一括 INSERT（AgentMembership ごとに 1 行）。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、上記 3 ステップ
を 1 トランザクションに収める（empire-repo §確定 B Tx 境界の責務分離）。

``save`` は明示的な ``empire_id`` 引数を取る。:class:`Room` Aggregate には
``empire_id`` 属性が無く、所有関係は ``Empire.rooms: list[RoomRef]`` で表現される
ため。呼び元サービスは常に ``empire_id`` をスコープに持つ（§確定 R1-H）。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（empire-repo §確定 C）。

``find_by_name`` は RoomId が判明し次第 ``find_by_id`` に委譲することで、子テーブル
SELECT と ``_from_row`` 変換を単一情報源に保つ（agent §R1-C テンプレート継承、
§確定 R1-F）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.room.room import Room
from bakufu.domain.room.value_objects import AgentMembership, PromptKit
from bakufu.domain.value_objects import EmpireId, Role, RoomId
from bakufu.infrastructure.persistence.sqlite.tables.room_members import RoomMemberRow
from bakufu.infrastructure.persistence.sqlite.tables.rooms import RoomRow


class SqliteRoomRepository:
    """:class:`RoomRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, room_id: RoomId) -> Room | None:
        """room と room_members を SELECT し、:meth:`_from_row` で水和する。

        rooms 行が存在しない場合は ``None`` を返す。room_members の SELECT は
        ``ORDER BY agent_id, role``（複合キー昇順）を使い、水和されたメンバ リスト
        が決定的になるようにする — empire-repository BUG-EMR-001 が凍結したコント
        ラクトを当初から適用する。
        """
        room_stmt = select(RoomRow).where(RoomRow.id == room_id)
        room_row = (await self._session.execute(room_stmt)).scalar_one_or_none()
        if room_row is None:
            return None

        # ORDER BY を付与することで find_by_id を決定的にする。これがないと SQLite は
        # 内部スキャン順で行を返し、``Room == Room`` の往復等価性が壊れる
        # （Aggregate はリスト同士で比較する）。empire-repo BUG-EMR-001 を参照 —
        # 本 PR では当初から決定の済んだコントラクトを採用する。
        member_stmt = (
            select(RoomMemberRow)
            .where(RoomMemberRow.room_id == room_id)
            .order_by(RoomMemberRow.agent_id, RoomMemberRow.role)
        )
        member_rows = list((await self._session.execute(member_stmt)).scalars().all())

        return self._from_row(room_row, member_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM rooms``。

        実装詳細: SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を
        発行するため、SQLite は全 PK を Python にストリームせずスカラー 1 行だけ
        返す（empire-repo §確定 D 踏襲）。
        """
        stmt = select(func.count()).select_from(RoomRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, room: Room, empire_id: EmpireId) -> None:
        """§確定 R1-B の 3 ステップ delete-then-insert で ``room`` を永続化する。

        :class:`Room` には ``empire_id`` 属性が無いため（§確定 R1-H）、``empire_id``
        を明示引数とする。外側の ``async with session.begin():`` ブロックは呼び元の
        責任。各ステップ内部の失敗はそのまま伝播するため、アプリケーション サービス
        の Unit-of-Work 境界はクリーンにロールバックできる。
        """
        room_row, member_rows = self._to_row(room, empire_id)

        # Step 1: rooms UPSERT（id PK、ON CONFLICT で workflow_id + name +
        # description + prompt_kit_prefix_markdown + archived を更新）。
        # ``prompt_kit_prefix_markdown`` は MaskedText 経由でバインドされるため、
        # 更新時にも伏字化された形で DB に到達する（§確定 R1-J）。
        upsert_stmt = sqlite_insert(RoomRow).values(room_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "workflow_id": upsert_stmt.excluded.workflow_id,
                "name": upsert_stmt.excluded.name,
                "description": upsert_stmt.excluded.description,
                "prompt_kit_prefix_markdown": upsert_stmt.excluded.prompt_kit_prefix_markdown,
                "archived": upsert_stmt.excluded.archived,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: room_members DELETE。
        await self._session.execute(delete(RoomMemberRow).where(RoomMemberRow.room_id == room.id))

        # Step 3: room_members 一括 INSERT（メンバが無い場合はスキップ —
        # 新規作成された room はメンバ 0 で正当に存在し得る）。
        if member_rows:
            await self._session.execute(insert(RoomMemberRow), member_rows)

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Room | None:
        """``empire_id`` 内の ``name`` という Room を水和する（§確定 R1-F）。

        2 段階フロー: 軽量な ``SELECT id ... LIMIT 1`` で ``INDEX(empire_id, name)``
        を介して RoomId を特定し、その後 :meth:`find_by_id` に委譲することで、
        子テーブル SELECT と ``_from_row`` 変換を単一情報源に保つ
        （agent §R1-C テンプレート継承）。
        """
        id_stmt = (
            select(RoomRow.id).where(RoomRow.empire_id == empire_id, RoomRow.name == name).limit(1)
        )
        found_id = (await self._session.execute(id_stmt)).scalar_one_or_none()
        if found_id is None:
            return None
        return await self.find_by_id(found_id)

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------
    def _to_row(
        self,
        room: Room,
        empire_id: EmpireId,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """``room`` を ``(room_row, member_rows)`` に分割する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存しないよう、SQLAlchemy ``Row``
        オブジェクトは使わない。返却される各 ``dict`` のキーは ``mapped_column``
        名と完全一致する。

        :class:`Room` には ``empire_id`` 属性が無いため、``empire_id`` を明示的に
        渡す（§確定 R1-H）。
        """
        room_row: dict[str, Any] = {
            "id": room.id,
            "empire_id": empire_id,
            "workflow_id": room.workflow_id,
            "name": room.name,
            "description": room.description,
            # MaskedText.process_bind_param が VARCHAR ストレージに到達する前に
            # この文字列からシークレットを伏字化する — room §確定 G 実適用。
            "prompt_kit_prefix_markdown": room.prompt_kit.prefix_markdown,
            "archived": room.archived,
        }
        member_rows: list[dict[str, Any]] = [
            {
                "room_id": room.id,
                "agent_id": membership.agent_id,
                "role": membership.role.value,
                "joined_at": membership.joined_at,
            }
            for membership in room.members
        ]
        return room_row, member_rows

    def _from_row(
        self,
        room_row: RoomRow,
        member_rows: list[RoomMemberRow],
    ) -> Room:
        """2 つの行型から :class:`Room` Aggregate Root を水和する。

        ``Room.model_validate`` は post-validator を再実行するため、リポジトリ側の
        水和も ``RoomService.establish_room()`` が構築時に走らせるのと同じ不変条件
        チェックを通る。

        §確定 R1-J §不可逆性: ``prompt_kit.prefix_markdown`` はディスクから既に
        伏字化されたテキストを保持する。``PromptKit`` は長さ上限内の任意の文字列を
        受理するため伏字化された形でも構築は通るが、生成された Room は
        ``feature/llm-adapter`` の masked-prompt ガード無しに LLM へディスパッチ
        すべきではない。

        ``empire_id`` は :class:`Room` 上に **復元しない** — Aggregate には
        ``empire_id`` 属性が無い（§確定 R1-H）。
        """
        members = [
            AgentMembership(
                agent_id=row.agent_id,
                role=Role(row.role),
                joined_at=row.joined_at,
            )
            for row in member_rows
        ]
        return Room(
            id=room_row.id,
            workflow_id=room_row.workflow_id,
            name=room_row.name,
            description=room_row.description,
            prompt_kit=PromptKit(prefix_markdown=room_row.prompt_kit_prefix_markdown or ""),
            members=members,
            archived=room_row.archived,
        )


__all__ = ["SqliteRoomRepository"]
