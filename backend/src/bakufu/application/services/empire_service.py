"""EmpireService — Empire Aggregate 操作の application 層サービス。

Implements ``REQ-EM-HTTP-001``〜``REQ-EM-HTTP-005`` per
``docs/features/empire/http-api/detailed-design.md`` §確定 G.

Design notes:

* **UoW 境界**: write 操作 (``create`` / ``update`` / ``archive``) は read も含め
  単一の ``async with self._session.begin():`` ブロック内で完結させる。
  read-then-write パターンで read 操作が SQLAlchemy autobegin を起動したあとに
  再度 ``begin()`` を呼ぶと ``InvalidRequestError: A transaction is already begun``
  が発生するため (BUG-EM-001 修正)。
* ``find_all`` / ``find_by_id`` は read-only。明示的な ``begin()`` は不要。
  SQLAlchemy が autobegin するため呼び出し元でトランザクションを意識しなくてよい。
* The service raises application-layer exceptions
  (:class:`EmpireNotFoundError` / :class:`EmpireAlreadyExistsError` /
  :class:`EmpireArchivedError`) rather than returning sentinel values,
  keeping the interfaces layer free of domain-level conditionals.
* Domain-layer ``EmpireInvariantViolation`` propagates unchanged to the
  interfaces layer which maps it to HTTP 422 via
  ``empire_invariant_violation_handler``.
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

    The session is injected alongside the repository so the service can
    open and commit its own Unit-of-Work transactions for write
    operations. Read-only operations (``find_all`` / ``find_by_id``)
    execute directly on the session without an explicit ``begin()``.
    """

    def __init__(self, repo: EmpireRepository, session: AsyncSession) -> None:
        self._repo = repo
        self._session = session

    async def create(self, name: str) -> Empire:
        """Construct and persist a new Empire (REQ-EM-HTTP-001).

        Args:
            name: Raw Empire name. Normalized via domain's NFC+strip
                pipeline; length validated as 1-80 chars (R1-1).

        Returns:
            The freshly persisted Empire.

        Raises:
            EmpireAlreadyExistsError: if an Empire already exists (R1-5).
            EmpireInvariantViolation: if ``name`` fails domain validation.
        """
        # BUG-EM-001: count() triggers autobegin. Put ALL operations
        # (read + write) inside a single begin() to avoid
        # "InvalidRequestError: A transaction is already begun".
        async with self._session.begin():
            count = await self._repo.count()
            if count > 0:
                raise EmpireAlreadyExistsError()
            # EmpireId is a type alias for UUID — uuid4() is the correct type.
            empire = Empire(
                id=uuid4(),
                name=name,
                archived=False,
            )
            await self._repo.save(empire)
        return empire

    async def find_all(self) -> list[Empire]:
        """Return all Empire rows (REQ-EM-HTTP-002).

        Returns:
            0 or 1 Empire (singleton). Never raises.
        """
        return await self._repo.find_all()

    async def find_by_id(self, empire_id: EmpireId) -> Empire:
        """Hydrate a single Empire by its primary key (REQ-EM-HTTP-003).

        Args:
            empire_id: Target Empire's UUID.

        Returns:
            The hydrated Empire.

        Raises:
            EmpireNotFoundError: if no Empire with ``empire_id`` exists.
        """
        empire = await self._repo.find_by_id(empire_id)
        if empire is None:
            raise EmpireNotFoundError(str(empire_id))
        return empire

    async def update(self, empire_id: EmpireId, name: str | None) -> Empire:
        """Apply a partial update to an Empire (REQ-EM-HTTP-004).

        Args:
            empire_id: Target Empire's UUID.
            name: New name, or ``None`` to leave it unchanged.

        Returns:
            The updated Empire.

        Raises:
            EmpireNotFoundError: if the Empire does not exist.
            EmpireArchivedError: if the Empire is archived (R1-8).
            EmpireInvariantViolation: if the new name fails domain validation.
        """
        # BUG-EM-001: find_by_id triggers autobegin. Keep everything in one
        # begin() so there is only one transaction boundary.
        async with self._session.begin():
            empire = await self._repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))
            if empire.archived:
                raise EmpireArchivedError(str(empire_id))
            if name is None:
                # No fields changed — nothing to persist.
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
        """Logically delete an Empire (REQ-EM-HTTP-005 / UC-EM-010).

        Args:
            empire_id: Target Empire's UUID.

        Raises:
            EmpireNotFoundError: if the Empire does not exist.
        """
        # BUG-EM-001: find_by_id triggers autobegin. Keep everything in one
        # begin() so there is only one transaction boundary.
        async with self._session.begin():
            empire = await self._repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))
            archived_empire = empire.archive()
            await self._repo.save(archived_empire)


__all__ = ["EmpireService"]
