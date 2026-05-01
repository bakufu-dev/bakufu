"""TemplateLibrarySeeder — 起動時グローバルテンプレート seed + Empire RoleProfile プリセット適用。

Application 層サービス。Repository Protocol のみに依存し、インフラ実装を知らない。
コンストラクタで Repository Factory を DI 注入することで Infrastructure 具体実装から
独立する（Clean Architecture 依存規則）。UoW 境界（async with session.begin():）は
自クラスが管理する。

_seed_global_templates は Bootstrap._stage_3b_seed_template_library() からのみ呼ぶ
（§確定 H）。seed_role_profiles_for_empire は HTTP API / CLI からも呼べる。

設計書: docs/features/deliverable-template/template-library/detailed-design.md
§確定E（all-or-nothing Tx）/ §確定F（TOCTOU対策・skip戦略）/ §確定H（Bootstrap限定）
"""

from __future__ import annotations

import logging
import uuid as _uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.application.ports.role_profile_repository import RoleProfileRepository
from bakufu.application.services.template_library.definitions import (
    BAKUFU_ROLE_NS,
    PRESET_ROLE_TEMPLATE_MAP,
    WELL_KNOWN_TEMPLATES,
)
from bakufu.domain.deliverable_template.role_profile import RoleProfile
from bakufu.domain.value_objects.enums import Role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate
    from bakufu.domain.value_objects.identifiers import EmpireId
    from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef

logger = logging.getLogger(__name__)


class TemplateLibrarySeeder:
    """グローバルテンプレート seed と Empire プリセット RoleProfile 適用を担うサービス。

    コンストラクタで Repository Factory callable を受け取る。各メソッド内で
    session_factory から session を生成し、factory 経由で Repository インスタンスを
    作成することで Infrastructure 実装への直接依存を排除する。

    Args:
        template_repo_factory: AsyncSession を受け取り DeliverableTemplateRepository を
            返す callable。Bootstrap のコンポジションルートで具体実装を注入する。
        role_profile_repo_factory: AsyncSession を受け取り RoleProfileRepository を
            返す callable。同上。
    """

    def __init__(
        self,
        template_repo_factory: Callable[[AsyncSession], DeliverableTemplateRepository],
        role_profile_repo_factory: Callable[[AsyncSession], RoleProfileRepository],
    ) -> None:
        self._template_repo_factory = template_repo_factory
        self._role_profile_repo_factory = role_profile_repo_factory

    async def _seed_global_templates(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> int:
        """WELL_KNOWN_TEMPLATES 12 件を 1 トランザクションで UPSERT する（§確定 E）。

        1 件でも失敗した場合は全ロールバック。Bootstrap に例外を伝播させて起動中断。

        Args:
            session_factory: AsyncSession を生成するファクトリ。

        Returns:
            upserted 件数（常に len(WELL_KNOWN_TEMPLATES) = 12）。
        """
        async with session_factory() as session, session.begin():
            count = await self._upsert_templates(session, list(WELL_KNOWN_TEMPLATES))
        return count

    async def seed_role_profiles_for_empire(
        self,
        empire_id: EmpireId,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """PRESET_ROLE_TEMPLATE_MAP の 4 Role を指定 Empire に適用する（§確定 F）。

        既存 RoleProfile がある Role は skip（上書きしない）。
        TOCTOU: IntegrityError catch → skip（§確定 F TOCTOU 対策）。

        Args:
            empire_id: 適用対象の Empire ID。
            session_factory: AsyncSession を生成するファクトリ。
        """
        for role in (Role.LEADER, Role.DEVELOPER, Role.TESTER, Role.REVIEWER):
            refs = PRESET_ROLE_TEMPLATE_MAP[role]
            async with session_factory() as session, session.begin():
                saved = await self._upsert_role_profile_if_absent(session, empire_id, role, refs)
            if saved:
                logger.info(
                    "[INFO] stage 3b: saved preset RoleProfile for %s in empire %s",
                    role.value,
                    empire_id,
                )
            else:
                logger.info(
                    "[INFO] stage 3b: skip preset RoleProfile for %s in empire %s (already exists)",
                    role.value,
                    empire_id,
                )

    async def _upsert_templates(
        self,
        session: AsyncSession,
        templates: list[DeliverableTemplate],
    ) -> int:
        """各テンプレートを DeliverableTemplateRepository.save() 経由で UPSERT する。

        Args:
            session: 呼び元が begin() 済みの AsyncSession。
            templates: UPSERT 対象の DeliverableTemplate リスト。

        Returns:
            upserted 件数。
        """
        repo = self._template_repo_factory(session)
        for template in templates:
            await repo.save(template)
        return len(templates)

    async def _upsert_role_profile_if_absent(
        self,
        session: AsyncSession,
        empire_id: EmpireId,
        role: Role,
        refs: list[DeliverableTemplateRef],
    ) -> bool:
        """RoleProfile が存在しない場合のみ save する。

        §確定 F TOCTOU 対策: IntegrityError を catch して skip 扱い（戻り値 False）。
        「既に存在する → skip」という意味論と一致する Fail Secure 方向の処理。

        Args:
            session: 呼び元が begin() 済みの AsyncSession。
            empire_id: 対象 Empire。
            role: 対象 Role。
            refs: プリセット DeliverableTemplateRef リスト。

        Returns:
            True: save 成功。False: 既存のためスキップ（IntegrityError を含む）。
        """
        repo = self._role_profile_repo_factory(session)

        # 存在確認 — 既存の場合は skip（CEO の業務判断を破壊しない）
        existing = await repo.find_by_empire_and_role(empire_id, role)
        if existing is not None:
            return False

        # §確定 C: UUID5(BAKUFU_ROLE_NS, f"{empire_id}:{role.value}") で決定論的生成
        profile_id = _uuid.uuid5(BAKUFU_ROLE_NS, f"{empire_id}:{role.value}")
        role_profile = RoleProfile.model_validate(
            {
                "id": profile_id,
                "empire_id": empire_id,
                "role": role,
                "deliverable_template_refs": [
                    {
                        "template_id": ref.template_id,
                        "minimum_version": {
                            "major": ref.minimum_version.major,
                            "minor": ref.minimum_version.minor,
                            "patch": ref.minimum_version.patch,
                        },
                    }
                    for ref in refs
                ],
            }
        )

        try:
            await repo.save(role_profile)
        except IntegrityError:
            # §確定 F TOCTOU: find と save の間に並行 INSERT が先行した場合。
            # UNIQUE(empire_id, role) 違反 → skip（Fail Secure 方向）。
            return False

        return True


__all__ = ["TemplateLibrarySeeder"]
