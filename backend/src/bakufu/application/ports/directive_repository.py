"""Directive Repository ポート。

``docs/features/directive-repository/detailed-design.md`` §確定 R1-A
（empire-repo / workflow-repo / agent-repo / room-repo テンプレート 100% 継承）に加え、
§確定 R1-D（``find_by_room`` — Room スコープの Directive 検索、BUG-EMR-001 規約に
基づき決定的な順序とするため ``created_at DESC, id DESC`` で並べる）および §確定 R1-F
（``save(directive)`` — :class:`Directive` Aggregate が ``target_room_id`` を自身の
属性として保持するため、標準の 1 引数パターン）に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない**
  （empire-repo §確定 A: Python 3.12 の ``typing.Protocol`` ダックタイピングで十分）。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポート境界を越えることはない。
* ``save`` のシグネチャは ``save(directive: Directive) -> None``（標準 1 引数パターン、
  §確定 R1-F）。:class:`Directive` は ``target_room_id`` を属性として持つため、
  Repository が直接読み取れる — Room の非対称パターンはここでは不要。
* ``find_by_room`` が第 4 メソッド。``find_by_task_id`` は task-repository PR に
  延期（YAGNI、§確定 R1-D 後続申し送り）。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.directive.directive import Directive
from bakufu.domain.value_objects import DirectiveId, RoomId


class DirectiveRepository(Protocol):
    """:class:`Directive` Aggregate Root の永続化契約。

    application 層（``DirectiveService``、将来 PR）が依存性注入により本 Protocol を
    消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.directive_repository`
    に存在する。
    """

    async def find_by_id(self, directive_id: DirectiveId) -> Directive | None:
        """主キーが ``directive_id`` の Directive をハイドレートする。

        該当行がない場合は ``None`` を返す。SQLAlchemy / ドライバ /
        ``pydantic.ValidationError`` 例外はそのまま伝播させ、application service の
        Unit-of-Work 境界がロールバックとエラー表出のいずれを取るかを判断できるように
        する。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM directives`` を返す。

        application service は本メソッドを監視 / 一括イントロスペクションに用いる。
        カウントはグローバル（§確定 R1-A: SQL ``COUNT(*)`` 契約、empire-repo
        §確定 D 踏襲）。
        """
        ...

    async def save(self, directive: Directive) -> None:
        """単一テーブルの UPSERT で ``directive`` を永続化する（§確定 R1-B）。

        Directive には子テーブルが存在しないため、save フローは 1 ステップに集約される:
        ``INSERT INTO directives ... ON CONFLICT (id) DO UPDATE SET ...``。

        ``target_room_id`` は ``directive.target_room_id`` から直接読み取る
        （§確定 R1-F: 標準 1 引数パターン）。実装は ``session.commit()`` /
        ``session.rollback()`` を呼んではならない。Unit-of-Work 境界の保有は
        application service の責務である（empire-repo §確定 B 踏襲）。
        """
        ...

    async def find_by_room(self, room_id: RoomId) -> list[Directive]:
        """``room_id`` を対象とする全 Directive を新しい順に返す。

        ORDER BY ``created_at DESC, id DESC``（BUG-EMR-001 規約: 決定的な順序付けの
        ための複合キー — 複数の Directive が同一タイムスタンプを持つ場合 ``created_at``
        単独では不十分。``id``（PK、UUID）が tiebreaker として結果を完全に決定的にする）。

        Room に対して Directive が存在しない場合は ``[]`` を返す。空リスト応答は
        「Room は存在するが Directive がない」と「Room が存在しない」を区別しない —
        この区別は application 層の責務である。
        """
        ...


__all__ = ["DirectiveRepository"]
