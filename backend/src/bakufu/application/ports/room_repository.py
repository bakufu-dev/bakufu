"""Room Repository ポート。

``docs/features/room-repository/detailed-design.md`` §確定 R1-A
（empire-repo / workflow-repo / agent-repo テンプレート 100% 継承）に加え、
§確定 R1-F（``find_by_name`` を第 4 メソッドとして追加 — Empire スコープでの
名前検索）および §確定 R1-H（``save(room, empire_id)`` — :class:`Room` Aggregate が
``empire_id`` 属性を保持しないため、empire_id を引数で渡す）に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない**
  （empire-repo §確定 A: Python 3.12 の ``typing.Protocol`` ダックタイピングで十分）。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポート境界を越えることはない。
* ``save`` のシグネチャは ``save(room: Room, empire_id: EmpireId) -> None``。
  :class:`Room` は ``empire_id`` を保持しない（所有関係は
  ``Empire.rooms: list[RoomRef]`` で表現される）ため、呼び出し元のサービスが常に
  保持している ``empire_id`` をドメインモデル変更を強制せずに引数として渡す
  （§確定 R1-H）。
* ``find_by_name`` は ``empire_id`` を第 1 引数に取る。Room の名前一意性は Empire
  スコープのため（§確定 R1-F: ``WHERE empire_id = :e AND name = :n``）。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.room.room import Room
from bakufu.domain.value_objects import EmpireId, RoomId


class RoomRepository(Protocol):
    """:class:`Room` Aggregate Root の永続化契約。

    application 層（``RoomService``、``EmpireService``、将来 PR）が依存性注入により
    本 Protocol を消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.room_repository`
    に存在する。
    """

    async def find_by_id(self, room_id: RoomId) -> Room | None:
        """主キーが ``room_id`` の Room をハイドレートする。

        該当行がない場合は ``None`` を返す。SQLAlchemy / ドライバ /
        ``pydantic.ValidationError`` 例外はそのまま伝播させ、application service の
        Unit-of-Work 境界がロールバックとエラー表出のいずれを取るかを判断できるように
        する。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM rooms`` を返す。

        application service は本メソッドを監視 / 一括イントロスペクションに用いる。
        カウントは Empire グローバル（§確定 R1-D: SQL ``COUNT(*)`` 契約、empire-repo
        §確定 D 踏襲）。
        """
        ...

    async def save(self, room: Room, empire_id: EmpireId) -> None:
        """§確定 R1-B の 3 段階 delete-then-insert で ``room`` を永続化する。

        ``empire_id`` を明示的な引数として渡す。これは :class:`Room` が ``empire_id``
        を属性として保持しないため（room §確定 — 所有関係は ``Empire.rooms`` で
        表現される）。呼び出し元のサービスは常に ``empire_id`` をスコープに持つので
        ここで渡す（§確定 R1-H）。

        実装は **呼び出し元が管理する** トランザクション内で 3 段階のシーケンス
        （UPSERT rooms → DELETE room_members → bulk INSERT room_members）を
        実行しなければならない。Repository は ``session.commit()`` /
        ``session.rollback()`` を決して呼び出さない。Unit-of-Work 境界の保有は
        application service の責務である（empire-repo §確定 B 踏襲）。
        """
        ...

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Room | None:
        """Empire ``empire_id`` 内で ``name`` という名前の Room をハイドレートする（§確定 R1-F）。

        2 段階フロー: 軽量な ``SELECT id ... LIMIT 1`` で RoomId を特定し、
        :meth:`find_by_id` に委譲することで子テーブルの SELECT と ``_from_row``
        変換を一元化する（agent §R1-C 継承パターン）。

        該当 Room がない場合は ``None`` を返す。実装は全 Room を取得して Python 側で
        フィルタしてはならない — そのパターンはメモリ / N+1 落とし穴として
        §確定 R1-F (c) で明示的に却下されている。
        """
        ...

    async def find_all_by_empire(self, empire_id: EmpireId) -> list[Room]:
        """``empire_id`` に一致する全 Room を返す（§確定 H / UC-RM-009）。

        実装は ``SELECT * FROM rooms WHERE empire_id = :empire_id ORDER BY name ASC``
        を発行しなければならない（Q-OPEN-2 暫定: name 昇順）。全 Room を取得して
        Python 側でフィルタしてはならない。

        Empire 内に Room が存在しない場合は空リストを返す。
        """
        ...

    async def find_empire_id_by_room_id(self, room_id: RoomId) -> EmpireId | None:
        """``room_id`` に一致する Room 行の ``empire_id`` を返す。

        write 操作（update / archive / assign_agent / unassign_agent）から使用する。
        service は ``room_id`` を持つが ``empire_id`` は持たない
        （:class:`Room` は ``empire_id`` 属性を保持しない — §確定 R1-H）ため。

        行が存在しない場合は ``None`` を返す。
        """
        ...


__all__ = ["RoomRepository"]
