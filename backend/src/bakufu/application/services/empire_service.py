"""EmpireService — Empire Aggregate 操作の application 層サービス。

``docs/features/empire/http-api/detailed-design.md`` §確定 G に従い、
``REQ-EM-HTTP-001``〜``REQ-EM-HTTP-005`` を実装する。

設計メモ:

* **UoW 境界**: write 操作 (``create`` / ``update`` / ``archive``) は read も含め
  単一の ``async with self._session.begin():`` ブロック内で完結させる。
  read-then-write パターンで read 操作が SQLAlchemy autobegin を起動したあとに
  再度 ``begin()`` を呼ぶと ``InvalidRequestError: A transaction is already begun``
  が発生するため (BUG-EM-001 修正)。
* ``find_all`` / ``find_by_id`` は read-only。明示的な ``begin()`` は不要。
  SQLAlchemy が autobegin するため呼び出し元でトランザクションを意識しなくてよい。
* 本サービスは sentinel 値を返す代わりに application 層の例外
  (:class:`EmpireNotFoundError` / :class:`EmpireAlreadyExistsError` /
  :class:`EmpireArchivedError`) を送出することで、interfaces 層をドメインレベルの
  条件分岐から解放する。
* ドメイン層の ``EmpireInvariantViolation`` はそのまま interfaces 層へ伝播し、
  ``empire_invariant_violation_handler`` 経由で HTTP 422 にマップされる。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.empire_exceptions import (
    EmpireAlreadyExistsError,
    EmpireArchivedError,
    EmpireNotFoundError,
)
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.domain.empire import Empire
from bakufu.domain.value_objects.identifiers import EmpireId


class EmpireService:
    """Empire Aggregate 操作の thin CRUD サービス (確定 G)。

    session は repository とともに注入され、サービスが write 操作向けに自前の
    Unit-of-Work トランザクションを開いて commit できるようにする。read-only 操作
    （``find_all`` / ``find_by_id``）は明示的な ``begin()`` なしで session 上で
    直接実行する。
    """

    def __init__(self, repo: EmpireRepository, session: AsyncSession) -> None:
        self._repo = repo
        self._session = session

    async def create(self, name: str) -> Empire:
        """新しい Empire を構築して永続化する（REQ-EM-HTTP-001）。

        Args:
            name: 生の Empire 名。ドメインの NFC+strip パイプラインで正規化され、
                長さは 1–80 文字として検証される（R1-1）。

        Returns:
            新たに永続化された Empire。

        Raises:
            EmpireAlreadyExistsError: Empire が既に存在する場合（R1-5）。
            EmpireInvariantViolation: ``name`` がドメイン検証に失敗した場合。
        """
        # BUG-EM-001: count() が autobegin を起動する。
        # "InvalidRequestError: A transaction is already begun" を避けるため、
        # 全操作（read + write）を単一の begin() 内に置く。
        async with self._session.begin():
            count = await self._repo.count()
            if count > 0:
                raise EmpireAlreadyExistsError()
            # EmpireId は UUID の型エイリアスのため、uuid4() が正しい型となる。
            empire = Empire(
                id=uuid4(),
                name=name,
                archived=False,
            )
            await self._repo.save(empire)
        return empire

    async def find_all(self) -> list[Empire]:
        """全 Empire 行を返す（REQ-EM-HTTP-002）。

        Returns:
            0 件または 1 件の Empire（シングルトン）。例外は送出しない。
        """
        return await self._repo.find_all()

    async def find_by_id(self, empire_id: EmpireId) -> Empire:
        """主キーで単一の Empire をハイドレートする（REQ-EM-HTTP-003）。

        Args:
            empire_id: 対象 Empire の UUID。

        Returns:
            ハイドレートされた Empire。

        Raises:
            EmpireNotFoundError: ``empire_id`` の Empire が存在しない場合。
        """
        empire = await self._repo.find_by_id(empire_id)
        if empire is None:
            raise EmpireNotFoundError(str(empire_id))
        return empire

    async def update(self, empire_id: EmpireId, name: str | None) -> Empire:
        """Empire に部分更新を適用する（REQ-EM-HTTP-004）。

        Args:
            empire_id: 対象 Empire の UUID。
            name: 新しい名前。``None`` の場合は変更しない。

        Returns:
            更新後の Empire。

        Raises:
            EmpireNotFoundError: Empire が存在しない場合。
            EmpireArchivedError: Empire がアーカイブ済みの場合（R1-8）。
            EmpireInvariantViolation: 新しい名前がドメイン検証に失敗した場合。
        """
        # BUG-EM-001: find_by_id が autobegin を起動する。
        # トランザクション境界を 1 つに保つため、すべてを単一の begin() 内にまとめる。
        async with self._session.begin():
            empire = await self._repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))
            if empire.archived:
                raise EmpireArchivedError(str(empire_id))
            if name is None:
                # 変更フィールドなし — 永続化対象なし。
                return empire
            updated = Empire(
                id=empire.id,
                name=name,
                archived=empire.archived,
                rooms=list(empire.rooms),
                agents=list(empire.agents),
            )
            await self._repo.save(updated)
        return updated

    async def archive(self, empire_id: EmpireId) -> None:
        """Empire を論理削除する（REQ-EM-HTTP-005 / UC-EM-010）。

        Args:
            empire_id: 対象 Empire の UUID。

        Raises:
            EmpireNotFoundError: Empire が存在しない場合。
        """
        # BUG-EM-001: find_by_id が autobegin を起動する。
        # トランザクション境界を 1 つに保つため、すべてを単一の begin() 内にまとめる。
        async with self._session.begin():
            empire = await self._repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))
            archived_empire = empire.archive()
            await self._repo.save(archived_empire)


__all__ = ["EmpireService"]
