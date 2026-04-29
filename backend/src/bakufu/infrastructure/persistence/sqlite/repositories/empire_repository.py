""":class:`bakufu.application.ports.EmpireRepository` の SQLite アダプタ。

§確定 B の "delete-then-insert" 保存フローを実装する:

1. ``empires`` UPSERT（id 衝突時に name を更新）
2. ``empire_room_refs`` DELETE WHERE empire_id = ?
3. ``empire_room_refs`` 一括 INSERT（``RoomRef`` ごとに 1 行）
4. ``empire_agent_refs`` DELETE WHERE empire_id = ?
5. ``empire_agent_refs`` 一括 INSERT（``AgentRef`` ごとに 1 行）

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、上記 5 ステップ
を 1 トランザクションに収める（§確定 B Tx 境界の責務分離）。これにより 1 つの
サービスが同じ Unit-of-Work で複数のリポジトリを組み合わせられる
（``EmpireRepository.save`` + Outbox 行追加など）。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（§確定 C）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.empire import Empire
from bakufu.domain.value_objects import (
    AgentRef,
    EmpireId,
    Role,
    RoomRef,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_agent_refs import (
    EmpireAgentRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_room_refs import (
    EmpireRoomRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empires import EmpireRow


class SqliteEmpireRepository:
    """:class:`EmpireRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, empire_id: EmpireId) -> Empire | None:
        """empires と関連テーブルを SELECT し、:meth:`_from_row` で水和する。

        empires 行が存在しない場合は ``None`` を返す。2 つの関連 SELECT は SQL を
        単純に保つため逐次実行する。バルクの Empire は Confirmation C の
        ``len(rooms) ≤ 100`` 上限を超えないため、MVP では IN 句バッチ化は不要。
        """
        empire_stmt = select(EmpireRow).where(EmpireRow.id == empire_id)
        empire_row = (await self._session.execute(empire_stmt)).scalar_one_or_none()
        if empire_row is None:
            return None

        # BUG-EMR-001 修正: ORDER BY room_id / agent_id により、水和されたリストを
        # 決定的にする。これがないと SQLite は内部スキャン順で行を返し、
        # ``Empire == Empire`` の往復等価性が壊れていた（Aggregate VO はリスト同士
        # で比較する）。設計解決は docs/features/empire-repository/detailed-design.md
        # §Known Issues を参照。basic-design.md L127-128 が ``ORDER BY room_id`` /
        # ``ORDER BY agent_id`` を設計コントラクトとして凍結している。
        room_stmt = (
            select(EmpireRoomRefRow)
            .where(EmpireRoomRefRow.empire_id == empire_id)
            .order_by(EmpireRoomRefRow.room_id)
        )
        room_rows = list((await self._session.execute(room_stmt)).scalars().all())

        agent_stmt = (
            select(EmpireAgentRefRow)
            .where(EmpireAgentRefRow.empire_id == empire_id)
            .order_by(EmpireAgentRefRow.agent_id)
        )
        agent_rows = list((await self._session.execute(agent_stmt)).scalars().all())

        return self._from_row(empire_row, room_rows, agent_rows)

    async def find_all(self) -> list[Empire]:
        """``SELECT * FROM empires`` を関連テーブル水和込みで実行する。

        bakufu の Empire はシングルトン（R1-5）であるため、結果リストは 0 または 1
        要素になる。実装は全 ``empires`` 行を取得した後、:meth:`find_by_id` セマン
        ティクスで各行を水和することで水和ロジックを集約する。
        """
        empire_stmt = select(EmpireRow)
        empire_rows = list((await self._session.execute(empire_stmt)).scalars().all())

        result: list[Empire] = []
        for empire_row in empire_rows:
            empire_id = _uuid(empire_row.id)
            room_stmt = (
                select(EmpireRoomRefRow)
                .where(EmpireRoomRefRow.empire_id == empire_id)
                .order_by(EmpireRoomRefRow.room_id)
            )
            room_rows = list((await self._session.execute(room_stmt)).scalars().all())

            agent_stmt = (
                select(EmpireAgentRefRow)
                .where(EmpireAgentRefRow.empire_id == empire_id)
                .order_by(EmpireAgentRefRow.agent_id)
            )
            agent_rows = list((await self._session.execute(agent_stmt)).scalars().all())

            result.append(self._from_row(empire_row, room_rows, agent_rows))

        return result

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM empires``。

        ``EmpireService.create()`` がこれを呼んでシングルトン不変条件を強制する
        （§確定 D）。リポジトリ自体は ``count != 0`` がエラーかどうかについて
        沈黙する — その判断はアプリケーション サービスのもの。

        実装詳細: SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を
        発行するため、SQLite は全 PK を Python にストリームせずスカラー 1 行だけ
        返す。これは 6 つの後続リポジトリ PR（workflow / agent / room / directive
        / task / external-review-gate）に対する **テンプレート責任** として重要
        である — Stage / Task テーブルは数百行を保持し得るため、ここで提示する
        パターンが下流に伝播する。
        """
        stmt = select(func.count()).select_from(EmpireRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, empire: Empire) -> None:
        """§確定 B の 5 ステップ delete-then-insert で ``empire`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。各ステップ
        内部の失敗はそのまま伝播するため、アプリケーション サービスの Unit-of-Work
        境界はクリーンにロールバックできる。
        """
        empire_row, room_refs, agent_refs = self._to_row(empire)

        # Step 1: empires UPSERT（id PK、ON CONFLICT で name を更新）。
        upsert_stmt = sqlite_insert(EmpireRow).values(empire_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": upsert_stmt.excluded.name,
                "archived": upsert_stmt.excluded.archived,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: empire_room_refs DELETE。
        await self._session.execute(
            delete(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == empire.id)
        )

        # Step 3: empire_room_refs 一括 INSERT（rooms が無い場合はスキップ）。
        if room_refs:
            await self._session.execute(insert(EmpireRoomRefRow), room_refs)

        # Step 4: empire_agent_refs DELETE。
        await self._session.execute(
            delete(EmpireAgentRefRow).where(EmpireAgentRefRow.empire_id == empire.id)
        )

        # Step 5: empire_agent_refs 一括 INSERT（agents が無い場合はスキップ）。
        if agent_refs:
            await self._session.execute(insert(EmpireAgentRefRow), agent_refs)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(
        self,
        empire: Empire,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """``empire`` を ``(empires_row, room_refs, agent_refs)`` に分割する。

        3 つの返り値は :meth:`save` が書き込む 3 つのテーブルに対応する。SQLAlchemy
        ``Row`` オブジェクトは意図的に使わない — ドメイン層が SQLAlchemy の型階層に
        偶発的に依存することを防ぐため。
        """
        empire_row: dict[str, Any] = {
            "id": empire.id,
            "name": empire.name,
            "archived": empire.archived,
        }
        room_refs: list[dict[str, Any]] = [
            {
                "empire_id": empire.id,
                "room_id": ref.room_id,
                "name": ref.name,
                "archived": ref.archived,
            }
            for ref in empire.rooms
        ]
        agent_refs: list[dict[str, Any]] = [
            {
                "empire_id": empire.id,
                "agent_id": ref.agent_id,
                "name": ref.name,
                "role": ref.role.value,
            }
            for ref in empire.agents
        ]
        return empire_row, room_refs, agent_refs

    def _from_row(
        self,
        empire_row: EmpireRow,
        room_rows: list[EmpireRoomRefRow],
        agent_rows: list[EmpireAgentRefRow],
    ) -> Empire:
        """3 つの行から :class:`Empire` Aggregate Root を水和する。

        ``Empire.model_validate`` は post-validator を再実行するため、リポジトリ側
        の水和も ``EmpireService.create()`` が構築時に走らせるのと同じ不変条件
        チェックを通る。コントラクト（§確定 C）は「リポジトリ水和は妥当な Empire
        を生成するか例外を送出する」。
        """
        rooms = [
            RoomRef(
                room_id=_uuid(row.room_id),
                name=row.name,
                archived=row.archived,
            )
            for row in room_rows
        ]
        agents = [
            AgentRef(
                agent_id=_uuid(row.agent_id),
                name=row.name,
                role=Role(row.role),
            )
            for row in agent_rows
        ]
        return Empire(
            id=_uuid(empire_row.id),
            name=empire_row.name,
            archived=empire_row.archived,
            rooms=rooms,
            agents=agents,
        )


def _uuid(value: UUID | str) -> UUID:
    """行の値を :class:`uuid.UUID` に強制変換する。

    SQLAlchemy の UUIDStr TypeDecorator は ``process_result_value`` で既に ``UUID``
    インスタンスを返すが、防御的な強制変換により、raw SQL 経路の水和も同じコードを
    通せる — 各呼び出し箇所で ``isinstance`` の階段を書かずに済む。
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


__all__ = ["SqliteEmpireRepository"]
