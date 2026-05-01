"""RoomMatchingService — Room-level deliverable template matching (Issue #120)。"""

from __future__ import annotations

from bakufu.application.exceptions.room_exceptions import RoomDeliverableMismatch
from bakufu.application.ports.role_profile_repository import RoleProfileRepository
from bakufu.application.ports.room_role_override_repository import RoomRoleOverrideRepository
from bakufu.domain.value_objects import DeliverableTemplateRef, EmpireId, RoomId
from bakufu.domain.value_objects.enums import Role
from bakufu.domain.workflow.workflow import Workflow


class RoomMatchingService:
    """Room-level deliverable coverage チェックを提供するサービス。

    ``validate_coverage`` は純粋同期関数。I/O は ``resolve_effective_refs`` のみ。
    """

    def __init__(
        self,
        override_repo: RoomRoleOverrideRepository,
        role_profile_repo: RoleProfileRepository,
    ) -> None:
        self._override_repo = override_repo
        self._role_profile_repo = role_profile_repo

    def validate_coverage(
        self,
        workflow: Workflow,
        effective_refs: tuple[DeliverableTemplateRef, ...],
    ) -> list[RoomDeliverableMismatch]:
        """必須 deliverable がすべて effective_refs でカバーされているか検証する (§確定 E)。

        optional=False の DeliverableRequirement のみを対象とする。
        不足があれば全件を収集して返す（fail-fast = full list, not first failure）。

        Args:
            workflow: チェック対象の Workflow Aggregate。
            effective_refs: ロールが提供する DeliverableTemplateRef のタプル。

        Returns:
            不足 deliverable の :class:`RoomDeliverableMismatch` リスト。空なら問題なし。
        """
        covered_ids = {ref.template_id for ref in effective_refs}
        missing: list[RoomDeliverableMismatch] = []

        for stage in workflow.stages:
            for dr in stage.required_deliverables:
                if dr.optional:
                    continue
                if dr.template_ref.template_id not in covered_ids:
                    missing.append(
                        RoomDeliverableMismatch(
                            stage_id=str(stage.id),
                            stage_name=stage.name,
                            template_id=str(dr.template_ref.template_id),
                        )
                    )

        return missing

    async def resolve_effective_refs(
        self,
        room_id: RoomId,
        empire_id: EmpireId,
        role: Role,
        custom_refs: tuple[DeliverableTemplateRef, ...] | None,
    ) -> tuple[DeliverableTemplateRef, ...]:
        """ロールの effective_refs を優先度順に解決する。

        Priority: custom_refs > RoomRoleOverride > RoleProfile > empty tuple

        Args:
            room_id: 対象 Room の ID。
            empire_id: 対象 Empire の ID。
            role: チェック対象のロール。
            custom_refs: リクエスト時に指定されたカスタム refs（None = 指定なし）。

        Returns:
            解決された DeliverableTemplateRef のタプル。
        """
        # Priority 1: custom_refs が明示指定された場合はそれを使用する
        if custom_refs is not None:
            return custom_refs

        # Priority 2: RoomRoleOverride が存在する場合はそれを使用する
        override = await self._override_repo.find_by_room_and_role(room_id, role)
        if override is not None:
            return override.deliverable_template_refs

        # Priority 3: RoleProfile が存在する場合はそれを使用する
        profile = await self._role_profile_repo.find_by_empire_and_role(empire_id, role)
        if profile is not None:
            return profile.deliverable_template_refs

        # Priority 4: 何も見つからない場合は空タプルを返す
        return ()


__all__ = ["RoomMatchingService"]
