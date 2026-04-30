"""RoleProfile Repository ポート。

empire-repository §確定 A に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない** —
  Python 3.12 の ``typing.Protocol`` ダックタイピングで十分。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.deliverable_template import RoleProfile
from bakufu.domain.value_objects import EmpireId, RoleProfileId
from bakufu.domain.value_objects.enums import Role


class RoleProfileRepository(Protocol):
    """:class:`RoleProfile` Aggregate Root の永続化契約。

    UNIQUE(empire_id, role) 制約により、``find_by_empire_and_role`` は
    最大 1 件を返す。同一 Empire 内で同 Role の RoleProfile を重複させようとすると
    ``sqlalchemy.IntegrityError`` が上位伝播する（§確定 H）。

    SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository`
    に存在する。
    """

    async def find_by_empire_and_role(
        self,
        empire_id: EmpireId,
        role: Role,
    ) -> RoleProfile | None:
        """``(empire_id, role)`` に対応する RoleProfile をハイドレートする。

        UNIQUE 制約により最大 1 件。該当なしは ``None`` を返す。
        """
        ...

    async def find_all_by_empire(self, empire_id: EmpireId) -> list[RoleProfile]:
        """指定 Empire の全 RoleProfile を ``ORDER BY role ASC`` で返す（§確定 I）。

        0 件の場合は空リストを返す。
        """
        ...

    async def save(self, role_profile: RoleProfile) -> None:
        """``role_profiles`` 1 テーブルへの UPSERT で永続化する（§確定 B）。

        ``ON CONFLICT (id) DO UPDATE SET ...`` を使用する。
        同一 ``(empire_id, role)`` で別 ``id`` の INSERT は
        ``UNIQUE(empire_id, role)`` 違反として ``IntegrityError`` を上位伝播する
        （§確定 H）。Repository は commit / rollback を決して呼ばない。
        """
        ...

    async def delete(self, profile_id: RoleProfileId) -> None:
        """``DELETE FROM role_profiles WHERE id = :profile_id``。

        対象行が存在しない場合は何もしない（no-op）。Service 層で事前に
        ``find_by_empire_and_role`` による存在確認を行う設計のため、
        Repository 側では silent no-op を許容する。
        """
        ...


__all__ = ["RoleProfileRepository"]
