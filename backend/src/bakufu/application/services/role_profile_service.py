"""RoleProfileService — RoleProfile Aggregate 操作の application 層サービス。

``docs/features/deliverable-template/http-api/detailed-design.md`` に従って実装する。

設計メモ:

* ``upsert`` は冪等（§確定 C）: 同一 (empire_id, role) で複数回呼んでも同一 id を保持。
* Empire 存在確認、DeliverableTemplate ref 存在確認を事前に行う。
* ``delete`` は ``find_by_empire_and_role`` で Fail Fast してから Repository に委譲。
* **interfaces 層との境界**: router が domain 型を import しないよう、
  ``upsert`` は ``DeliverableTemplateRefDict`` / ``str`` 形式で受け取り、
  service 内部で domain VO へ変換する。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.deliverable_template_exceptions import (
    DeliverableTemplateNotFoundError,
    RoleProfileNotFoundError,
)
from bakufu.application.exceptions.empire_exceptions import EmpireNotFoundError
from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.application.ports.role_profile_repository import RoleProfileRepository
from bakufu.application.services.deliverable_template_service import DeliverableTemplateRefDict
from bakufu.domain.deliverable_template import RoleProfile
from bakufu.domain.value_objects import EmpireId
from bakufu.domain.value_objects.enums import Role
from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef


class RoleProfileService:
    """RoleProfile Aggregate 操作の thin サービス。

    session は repository とともに注入され、サービスが write 操作向けに自前の
    Unit-of-Work トランザクションを開いて commit できるようにする。read-only 操作は
    明示的な ``begin()`` なしで session 上で直接実行する。
    """

    def __init__(
        self,
        rp_repo: RoleProfileRepository,
        dt_repo: DeliverableTemplateRepository,
        empire_repo: EmpireRepository,
        session: AsyncSession,
    ) -> None:
        self._rp_repo = rp_repo
        self._dt_repo = dt_repo
        self._empire_repo = empire_repo
        self._session = session

    async def find_all_by_empire(self, empire_id: EmpireId) -> list[RoleProfile]:
        """Empire に紐づく全 RoleProfile を返す（REQ-RP-HTTP-001）。

        Args:
            empire_id: 対象 Empire の UUID。

        Returns:
            0 件以上の RoleProfile リスト（ORDER BY role ASC）。

        Raises:
            EmpireNotFoundError: ``empire_id`` の Empire が存在しない場合。
        """
        empire = await self._empire_repo.find_by_id(empire_id)
        if empire is None:
            raise EmpireNotFoundError(str(empire_id))
        return await self._rp_repo.find_all_by_empire(empire_id)

    async def find_by_empire_and_role(self, empire_id: EmpireId, role: Role) -> RoleProfile:
        """Empire × Role に対応する RoleProfile を返す（REQ-RP-HTTP-002）。

        Args:
            empire_id: 対象 Empire の UUID。
            role: 対象 Role。

        Returns:
            RoleProfile。

        Raises:
            RoleProfileNotFoundError: 対象 RoleProfile が存在しない場合。
        """
        result = await self._rp_repo.find_by_empire_and_role(empire_id, role)
        if result is None:
            raise RoleProfileNotFoundError(str(empire_id), role.value)
        return result

    async def find_by_empire_and_role_str(self, empire_id: EmpireId, role: str) -> RoleProfile:
        """Empire × Role（文字列）に対応する RoleProfile を返す。

        router から直接 role 文字列を受け取る版。内部で ``Role`` に変換する。

        Args:
            empire_id: 対象 Empire の UUID。
            role: 対象 Role 文字列（``Role`` StrEnum 値）。

        Returns:
            RoleProfile。

        Raises:
            ValueError: ``role`` が不正な Role 値の場合。
            RoleProfileNotFoundError: 対象 RoleProfile が存在しない場合。
        """
        role_enum = Role(role)
        return await self.find_by_empire_and_role(empire_id, role_enum)

    async def upsert(
        self,
        empire_id: EmpireId,
        role: str,
        refs: list[DeliverableTemplateRefDict],
    ) -> RoleProfile:
        """RoleProfile を Upsert する（REQ-RP-HTTP-003 / §確定 C 冪等設計）。

        既存の RoleProfile が存在する場合は同一 id を引き継ぐ。存在しない場合は
        新規 uuid4() を生成する。

        Args:
            empire_id: 対象 Empire の UUID。
            role: 対象 Role 文字列（``Role`` StrEnum 値）。
            refs: DeliverableTemplateRef リスト（dict 形式、完全置換）。

        Returns:
            Upsert 後の RoleProfile。

        Raises:
            EmpireNotFoundError: Empire が存在しない場合。
            DeliverableTemplateNotFoundError: refs に存在しない template_id が
                含まれる場合（kind="role_profile_ref"）。
            RoleProfileInvariantViolation: 重複参照がある場合。
        """
        role_enum = Role(role)
        ref_tuple = tuple(self._to_ref(r) for r in refs)

        # BUG-001: read も含め全操作を単一の begin() 内で完結させる (EmpireService パターン)。
        # empire_repo / dt_repo / rp_repo の各 find が autobegin を起動したあとに
        # begin() を呼ぶと "InvalidRequestError: A transaction is already begun" が発生するため。
        async with self._session.begin():
            # Empire 存在確認
            empire = await self._empire_repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))

            # 各 ref の参照整合性確認
            for ref in ref_tuple:
                existing_template = await self._dt_repo.find_by_id(ref.template_id)
                if existing_template is None:
                    raise DeliverableTemplateNotFoundError(
                        str(ref.template_id), kind="role_profile_ref"
                    )

            # 既存 RoleProfile を検索（冪等性のため id を引き継ぐ）
            existing_profile = await self._rp_repo.find_by_empire_and_role(empire_id, role_enum)
            profile_id = existing_profile.id if existing_profile is not None else uuid4()

            profile = RoleProfile.model_validate(
                {
                    "id": profile_id,
                    "empire_id": empire_id,
                    "role": role_enum,
                    "deliverable_template_refs": [
                        {
                            "template_id": ref.template_id,
                            "minimum_version": {
                                "major": ref.minimum_version.major,
                                "minor": ref.minimum_version.minor,
                                "patch": ref.minimum_version.patch,
                            },
                        }
                        for ref in ref_tuple
                    ],
                }
            )
            await self._rp_repo.save(profile)
        return profile

    async def delete(self, empire_id: EmpireId, role: str) -> None:
        """RoleProfile を削除する（REQ-RP-HTTP-004）。

        Args:
            empire_id: 対象 Empire の UUID。
            role: 対象 Role 文字列（``Role`` StrEnum 値）。

        Raises:
            RoleProfileNotFoundError: 対象 RoleProfile が存在しない場合（Fail Fast）。
        """
        role_enum = Role(role)
        # BUG-001: Fail Fast + delete を単一の begin() 内で完結させる (EmpireService パターン)。
        async with self._session.begin():
            profile = await self._rp_repo.find_by_empire_and_role(empire_id, role_enum)
            if profile is None:
                raise RoleProfileNotFoundError(str(empire_id), role_enum.value)
            await self._rp_repo.delete(profile.id)

    @staticmethod
    def _to_ref(d: DeliverableTemplateRefDict) -> DeliverableTemplateRef:
        """DeliverableTemplateRefDict → DeliverableTemplateRef VO に変換する。"""
        mv = d["minimum_version"]
        return DeliverableTemplateRef.model_validate(
            {
                "template_id": d["template_id"],
                "minimum_version": {
                    "major": mv["major"],
                    "minor": mv["minor"],
                    "patch": mv["patch"],
                },
            }
        )


__all__ = ["RoleProfileService"]
