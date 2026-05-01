"""RoomService — Room Aggregate 操作の application 層サービス (確定 G).

実装ノート:

* **UoW 境界**: write 操作 (create / update / archive / assign_agent /
  unassign_agent) は read も含め単一の ``async with self._session.begin()``
  ブロック内で完結させる。read-then-write パターンで autobegin が起動したあと
  再度 ``begin()`` を呼ぶと ``InvalidRequestError`` が発生するため (BUG-EM-001
  修正の教訓を踏まえた設計)。
* ``find_all_by_empire`` / ``find_by_id`` は read-only。明示的な ``begin()``
  は不要。
* application-layer 例外 (RoomNotFoundError / RoomNameAlreadyExistsError /
  RoomArchivedError / WorkflowNotFoundError / AgentNotFoundError) を raise し、
  domain-layer ``RoomInvariantViolation`` は interface 層に伝播させる。
* ``unassign_agent`` の invalid role 文字列は ``RoomInvariantViolation(kind=
  'member_not_found')`` に変換し 404 を返す (確定 E: role バリデーションを
  domain に委ねて HTTP 層の責務を最小化)。
* ``RoomService`` は ``empire_id`` を Room aggregate から取得できないため
  (Room は empire_id を持たない — §確定 R1-H)、write ops では
  ``room_repo.find_empire_id_by_room_id`` で DB から取得する。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.empire_exceptions import EmpireNotFoundError
from bakufu.application.exceptions.room_exceptions import (
    AgentNotFoundError,
    RoomArchivedError,
    RoomDeliverableMatchingError,
    RoomNameAlreadyExistsError,
    RoomNotFoundError,
    WorkflowNotFoundError,
)
from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.room_role_override_repository import RoomRoleOverrideRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.services.room_matching_service import RoomMatchingService
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room.room import Room
from bakufu.domain.room.value_objects import AgentMembership, PromptKit, RoomRoleOverride
from bakufu.domain.value_objects import (
    AgentId,
    DeliverableTemplateRef,
    EmpireId,
    Role,
    RoomId,
    WorkflowId,
)


class RoomService:
    """Room Aggregate 操作の thin CRUD サービス (確定 G)。

    4 つの Repository と session を受け取る。session は write 操作の
    Unit-of-Work (``async with session.begin()``) 管理に使用する。
    """

    def __init__(
        self,
        room_repo: RoomRepository,
        empire_repo: EmpireRepository,
        workflow_repo: WorkflowRepository,
        agent_repo: AgentRepository,
        session: AsyncSession,
        matching_svc: RoomMatchingService | None = None,
        override_repo: RoomRoleOverrideRepository | None = None,
    ) -> None:
        self._room_repo = room_repo
        self._empire_repo = empire_repo
        self._workflow_repo = workflow_repo
        self._agent_repo = agent_repo
        self._session = session
        self._matching_svc = matching_svc
        self._override_repo = override_repo

    async def create(
        self,
        empire_id: EmpireId,
        name: str,
        description: str,
        workflow_id: WorkflowId,
        prompt_kit_prefix_markdown: str,
    ) -> Room:
        """Room を新規作成して永続化する (REQ-RM-HTTP-001).

        Raises:
            EmpireNotFoundError: Empire が存在しない場合。
            WorkflowNotFoundError: Workflow が存在しない場合。
            RoomNameAlreadyExistsError: 同 Empire 内で同名 Room が存在する場合 (R1-8)。
            RoomInvariantViolation: domain バリデーション違反。
        """
        async with self._session.begin():
            empire = await self._empire_repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))

            workflow = await self._workflow_repo.find_by_id(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))

            existing = await self._room_repo.find_by_name(empire_id, name)
            if existing is not None:
                raise RoomNameAlreadyExistsError(name, str(empire_id))

            room = Room(
                id=uuid4(),
                name=name,
                description=description,
                workflow_id=workflow_id,
                prompt_kit=PromptKit(prefix_markdown=prompt_kit_prefix_markdown),
                members=[],
                archived=False,
            )
            await self._room_repo.save(room, empire_id)
        return room

    async def find_all_by_empire(self, empire_id: EmpireId) -> list[Room]:
        """Empire スコープの Room 全件を返す (REQ-RM-HTTP-002).

        Raises:
            EmpireNotFoundError: Empire が存在しない場合。
        """
        empire = await self._empire_repo.find_by_id(empire_id)
        if empire is None:
            raise EmpireNotFoundError(str(empire_id))
        return await self._room_repo.find_all_by_empire(empire_id)

    async def find_by_id(self, room_id: RoomId) -> Room:
        """Room を単件取得する (REQ-RM-HTTP-003).

        Raises:
            RoomNotFoundError: Room が存在しない場合。
        """
        room = await self._room_repo.find_by_id(room_id)
        if room is None:
            raise RoomNotFoundError(str(room_id))
        return room

    async def update(
        self,
        room_id: RoomId,
        name: str | None,
        description: str | None,
        prompt_kit_prefix_markdown: str | None,
    ) -> Room:
        """Room を部分更新して永続化する (REQ-RM-HTTP-004).

        ``None`` のフィールドは変更しない。全フィールドが ``None`` の場合は
        save せず既存 Room を返す (確定 G §update の部分更新ルール)。

        Raises:
            RoomNotFoundError: Room が存在しない場合。
            RoomArchivedError: Room がアーカイブ済みの場合 (R1-5)。
            RoomInvariantViolation: domain バリデーション違反。
        """
        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))
            if room.archived:
                raise RoomArchivedError(str(room_id))

            if name is None and description is None and prompt_kit_prefix_markdown is None:
                return room

            empire_id = await self._room_repo.find_empire_id_by_room_id(room_id)
            if empire_id is None:  # pragma: no cover — 直前の find_by_id で存在確認済み
                raise RoomNotFoundError(str(room_id))

            new_name = name if name is not None else room.name
            new_description = description if description is not None else room.description
            new_prefix = (
                prompt_kit_prefix_markdown
                if prompt_kit_prefix_markdown is not None
                else room.prompt_kit.prefix_markdown
            )
            updated = Room(
                id=room.id,
                name=new_name,
                description=new_description,
                workflow_id=room.workflow_id,
                prompt_kit=PromptKit(prefix_markdown=new_prefix),
                members=list(room.members),
                archived=room.archived,
            )
            await self._room_repo.save(updated, empire_id)
        return updated

    async def archive(self, room_id: RoomId) -> None:
        """Room を論理削除する (REQ-RM-HTTP-005 / UC-RM-010).

        ``archived=True`` に設定して永続化する。物理削除は行わない。
        ``room.archive()`` は冪等 (確定 D)。

        Raises:
            RoomNotFoundError: Room が存在しない場合。
        """
        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))

            empire_id = await self._room_repo.find_empire_id_by_room_id(room_id)
            if empire_id is None:  # pragma: no cover — 直前の find_by_id で存在確認済み
                raise RoomNotFoundError(str(room_id))

            archived_room = room.archive()
            await self._room_repo.save(archived_room, empire_id)

    async def assign_agent(
        self,
        room_id: RoomId,
        agent_id: AgentId,
        role: str,
        custom_refs: list[dict[str, Any]] | None = None,
    ) -> Room:
        """Room に Agent を割り当てる (REQ-RM-HTTP-006).

        Raises:
            RoomNotFoundError: Room が存在しない場合。
            RoomArchivedError: Room がアーカイブ済みの場合 (R1-5)。
            AgentNotFoundError: Agent が存在しない場合。
            RoomDeliverableMatchingError: deliverable coverage チェック失敗 (§確定 G)。
            RoomInvariantViolation: (agent_id, role) 重複 / capacity 超過。
        """
        role_enum = Role(role)  # AgentAssignRequest.role の _validate_role で事前検証済み

        # dict → domain VO への変換（router は domain 型を import しない Q-3 遵守）
        custom_refs_domain: tuple[DeliverableTemplateRef, ...] | None = None
        if custom_refs is not None:
            custom_refs_domain = tuple(
                DeliverableTemplateRef.model_validate(d) for d in custom_refs
            )

        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))
            if room.archived:
                raise RoomArchivedError(str(room_id))

            agent = await self._agent_repo.find_by_id(agent_id)
            if agent is None:
                raise AgentNotFoundError(str(agent_id))

            empire_id = await self._room_repo.find_empire_id_by_room_id(room_id)
            if empire_id is None:  # pragma: no cover — 直前の find_by_id で存在確認済み
                raise RoomNotFoundError(str(room_id))

            # §確定 G: deliverable coverage チェック（matching_svc が注入された場合のみ）
            if self._matching_svc is not None:
                workflow = await self._workflow_repo.find_by_id(room.workflow_id)
                effective_refs = await self._matching_svc.resolve_effective_refs(
                    room_id, empire_id, role_enum, custom_refs_domain
                )
                if workflow is not None:
                    missing = self._matching_svc.validate_coverage(workflow, effective_refs)
                    if missing:
                        raise RoomDeliverableMatchingError(str(room_id), str(role_enum), missing)

            membership = AgentMembership(
                agent_id=agent_id,
                role=role_enum,
                joined_at=datetime.now(UTC),
            )
            updated_room = room.add_member(membership)
            await self._room_repo.save(updated_room, empire_id)

            # §確定 G ステップ 9: custom_refs が指定された場合 RoomRoleOverride を同一 Tx 内で保存
            if custom_refs_domain is not None and self._override_repo is not None:
                await self._override_repo.save(
                    RoomRoleOverride(
                        room_id=room_id,
                        role=role_enum,
                        deliverable_template_refs=custom_refs_domain,
                    )
                )
        return updated_room

    async def unassign_agent(
        self,
        room_id: RoomId,
        agent_id: AgentId,
        role: str,
    ) -> None:
        """Room から Agent の役割割り当てを解除する (REQ-RM-HTTP-007).

        無効な role 文字列は ``RoomInvariantViolation(kind='member_not_found')``
        に変換して 404 を返す (確定 E: 型バリデーションを domain に委ねる)。

        Raises:
            RoomNotFoundError: Room が存在しない場合。
            RoomArchivedError: Room がアーカイブ済みの場合 (R1-5)。
            RoomInvariantViolation: membership が存在しない場合 / 無効 role (404)。
        """
        try:
            role_enum = Role(role)
        except ValueError as err:
            raise RoomInvariantViolation(
                kind="member_not_found",
                message=(
                    f"[FAIL] Member not found: agent_id={agent_id}, role={role}\n"
                    f"Next: Verify the (agent_id, role) pair via GET /rooms/{{room_id}}; "
                    f"the role value may be invalid."
                ),
                detail={"agent_id": str(agent_id), "role": role},
            ) from err

        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))
            if room.archived:
                raise RoomArchivedError(str(room_id))

            empire_id = await self._room_repo.find_empire_id_by_room_id(room_id)
            if empire_id is None:  # pragma: no cover — 直前の find_by_id で存在確認済み
                raise RoomNotFoundError(str(room_id))

            updated_room = room.remove_member(agent_id, role_enum)
            await self._room_repo.save(updated_room, empire_id)


__all__ = ["RoomService"]
