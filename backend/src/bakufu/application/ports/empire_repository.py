"""Empire Repository ポート。

``docs/features/empire-repository/detailed-design.md`` §確定 A に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない** —
  Python 3.12 の ``typing.Protocol`` ダックタイピングで十分。
  ``@runtime_checkable`` の実行時オーバーヘッドは、application 層が必要としない
  ``isinstance`` 経路を増やしてしまう。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。これにより
  application 層は ``async with session.begin():`` の Unit-of-Work 内で
  Repository を組み合わせられる。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポートを越えて漏れることはない。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.empire import Empire
from bakufu.domain.value_objects import EmpireId


class EmpireRepository(Protocol):
    """:class:`Empire` Aggregate Root の永続化契約。

    application 層（``EmpireService``）が依存性注入により本 Protocol を消費する。
    SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.empire_repository`
    に存在する。
    """

    async def find_by_id(self, empire_id: EmpireId) -> Empire | None:
        """主キーが ``empire_id`` の Empire をハイドレートする。

        該当行がない場合は ``None`` を返す。実装は SQLAlchemy / ドライバの例外を
        そのまま伝播させ、application service の Unit-of-Work 境界がロールバックと
        エラー表出のいずれを取るかを判断できるようにする。
        """
        ...

    async def find_all(self) -> list[Empire]:
        """全 Empire 行をリストとして返す。

        bakufu の Empire はシングルトンであるため、結果は 0 件または 1 件の要素となる。
        ``EmpireService.find_all()`` がこれを ``GET /api/empires``（REQ-EM-HTTP-002）の
        裏付けに用いる。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM empires`` を返す。

        ``EmpireService.create()`` は本メソッドを呼び出して Empire シングルトン不変条件を
        強制する。カウント自体は Repository の責務だが、``count == 0`` /
        ``count == 1`` / ``count >= 2`` のいずれが service レベルのエラーを起こすかの
        判断は *application* 層の役割である（§確定 D）。
        """
        ...

    async def save(self, empire: Empire) -> None:
        """§確定 B の delete-then-insert フローで ``empire`` を永続化する。

        実装は **呼び出し元が管理する** トランザクション内で 5 段階のシーケンス
        （UPSERT empires → DELETE empire_room_refs → bulk INSERT room_refs →
        DELETE empire_agent_refs → bulk INSERT agent_refs）を実行しなければならない。
        Repository は ``session.commit()`` / ``session.rollback()`` を決して
        呼び出さない。Unit-of-Work 境界の保有は application service の責務である。
        """
        ...


__all__ = ["EmpireRepository"]
