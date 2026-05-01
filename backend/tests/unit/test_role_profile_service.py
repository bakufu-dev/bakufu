"""RoleProfileService ユニットテスト (TC-UT-RPS-001〜006).

Covers:
  TC-UT-RPS-001  find_by_empire_and_role → repo が None → RoleProfileNotFoundError
  TC-UT-RPS-002  upsert → Empire 不在 → EmpireNotFoundError
  TC-UT-RPS-003  upsert → ref 不在 → DeliverableTemplateNotFoundError
  TC-UT-RPS-004  upsert → 既存あり → 既存 id 保持 (§確定C)
  TC-UT-RPS-005  upsert → 既存なし → 新規 id 生成 (§確定C)
  TC-UT-RPS-006  delete → 不在 → RoleProfileNotFoundError (§確定E)

Issue: #122
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _make_mock_session() -> MagicMock:
    """async with session.begin(): をサポートするモック session を生成する。"""
    mock_session = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _make_service(
    rp_repo: AsyncMock,
    dt_repo: AsyncMock,
    empire_repo: AsyncMock,
) -> object:
    """RoleProfileService を AsyncMock repos + モック session で構築する。"""
    from bakufu.application.services.role_profile_service import RoleProfileService

    return RoleProfileService(
        rp_repo=rp_repo,
        dt_repo=dt_repo,
        empire_repo=empire_repo,
        session=_make_mock_session(),
    )


# ---------------------------------------------------------------------------
# TC-UT-RPS-001: find_by_empire_and_role → None → RoleProfileNotFoundError
# ---------------------------------------------------------------------------
class TestFindByEmpireAndRole:
    """TC-UT-RPS-001: repo が None を返す → RoleProfileNotFoundError。"""

    async def test_find_raises_when_not_found(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            RoleProfileNotFoundError,
        )
        from bakufu.application.services.role_profile_service import RoleProfileService
        from bakufu.domain.value_objects.enums import Role

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=None)

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=AsyncMock(),
            empire_repo=AsyncMock(),
            session=_make_mock_session(),
        )

        with pytest.raises(RoleProfileNotFoundError):
            await service.find_by_empire_and_role(uuid4(), Role.DEVELOPER)

    async def test_find_returns_profile_when_found(self) -> None:
        from bakufu.application.services.role_profile_service import RoleProfileService
        from bakufu.domain.value_objects.enums import Role

        from tests.factories.deliverable_template import make_role_profile

        profile = make_role_profile()
        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=profile)

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=AsyncMock(),
            empire_repo=AsyncMock(),
            session=_make_mock_session(),
        )

        result = await service.find_by_empire_and_role(uuid4(), Role.DEVELOPER)
        assert result is profile


# ---------------------------------------------------------------------------
# TC-UT-RPS-002: upsert → Empire 不在 → EmpireNotFoundError
# ---------------------------------------------------------------------------
class TestUpsertEmpireNotFound:
    """TC-UT-RPS-002: empire_repo が None → EmpireNotFoundError。"""

    async def test_upsert_raises_on_empire_not_found(self) -> None:
        from bakufu.application.exceptions.empire_exceptions import EmpireNotFoundError

        empire_repo = AsyncMock()
        empire_repo.find_by_id = AsyncMock(return_value=None)

        service = _make_service(AsyncMock(), AsyncMock(), empire_repo)
        with pytest.raises(EmpireNotFoundError):
            await service.upsert(uuid4(), "DEVELOPER", refs=[])  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TC-UT-RPS-003: upsert → ref 不在 → DeliverableTemplateNotFoundError
# ---------------------------------------------------------------------------
class TestUpsertRefNotFound:
    """TC-UT-RPS-003: dt_repo が None → DeliverableTemplateNotFoundError (kind=role_profile_ref)。

    kind が "role_profile_ref" であることを検証する。
    """

    async def test_upsert_raises_on_ref_not_found(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            DeliverableTemplateNotFoundError,
        )

        from tests.factories.empire import make_empire

        empire = make_empire()
        empire_repo = AsyncMock()
        empire_repo.find_by_id = AsyncMock(return_value=empire)

        dt_repo = AsyncMock()
        dt_repo.find_by_id = AsyncMock(return_value=None)

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=None)

        service = _make_service(rp_repo, dt_repo, empire_repo)
        ref_id = uuid4()

        with pytest.raises(DeliverableTemplateNotFoundError) as exc_info:
            await service.upsert(  # type: ignore[attr-defined]
                empire.id,
                "DEVELOPER",
                refs=[
                    {
                        "template_id": ref_id,
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    }
                ],
            )
        assert exc_info.value.kind == "role_profile_ref"


# ---------------------------------------------------------------------------
# TC-UT-RPS-004: upsert — 既存あり → 既存 id 保持 (§確定C)
# ---------------------------------------------------------------------------
class TestUpsertExistingIdPreservation:
    """TC-UT-RPS-004: 既存 RoleProfile がある場合 → id を引き継ぐ (§確定C)。"""

    async def test_upsert_preserves_existing_id(self) -> None:
        from bakufu.application.services.role_profile_service import RoleProfileService

        from tests.factories.deliverable_template import make_role_profile
        from tests.factories.empire import make_empire

        existing_id = uuid4()
        existing_profile = make_role_profile(profile_id=existing_id)
        empire = make_empire()

        empire_repo = AsyncMock()
        empire_repo.find_by_id = AsyncMock(return_value=empire)

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=existing_profile)
        rp_repo.save = AsyncMock()

        dt_repo = AsyncMock()

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=dt_repo,
            empire_repo=empire_repo,
            session=_make_mock_session(),
        )

        result = await service.upsert(empire.id, "DEVELOPER", refs=[])
        # 既存 id が保持されていること (§確定C)
        assert result.id == existing_id

    async def test_upsert_preserves_id_on_second_call(self) -> None:
        """save に渡された RoleProfile の id が existing_id と一致する。"""
        from bakufu.application.services.role_profile_service import RoleProfileService

        from tests.factories.deliverable_template import make_role_profile
        from tests.factories.empire import make_empire

        existing_id = uuid4()
        existing_profile = make_role_profile(profile_id=existing_id)
        empire = make_empire()

        empire_repo = AsyncMock()
        empire_repo.find_by_id = AsyncMock(return_value=empire)

        saved_profiles: list[object] = []

        async def _save(profile: object) -> None:
            saved_profiles.append(profile)

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=existing_profile)
        rp_repo.save = _save

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=AsyncMock(),
            empire_repo=empire_repo,
            session=_make_mock_session(),
        )

        await service.upsert(empire.id, "DEVELOPER", refs=[])
        assert len(saved_profiles) == 1
        assert saved_profiles[0].id == existing_id  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TC-UT-RPS-005: upsert — 既存なし → 新規 id 生成 (§確定C)
# ---------------------------------------------------------------------------
class TestUpsertNewIdGeneration:
    """TC-UT-RPS-005: 既存 RoleProfile がない場合 → 新規 id を生成 (§確定C)。"""

    async def test_upsert_generates_new_id_when_not_exists(self) -> None:
        from bakufu.application.services.role_profile_service import RoleProfileService

        from tests.factories.empire import make_empire

        empire = make_empire()

        empire_repo = AsyncMock()
        empire_repo.find_by_id = AsyncMock(return_value=empire)

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=None)
        rp_repo.save = AsyncMock()

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=AsyncMock(),
            empire_repo=empire_repo,
            session=_make_mock_session(),
        )

        result = await service.upsert(empire.id, "DEVELOPER", refs=[])
        # 新規 id が生成されていること
        import uuid

        assert isinstance(result.id, uuid.UUID)

    async def test_upsert_generates_different_id_each_time_when_no_existing(self) -> None:
        """既存なし → 呼び出しごとに新規 id（2 回呼ぶと異なる id）。"""
        from bakufu.application.services.role_profile_service import RoleProfileService

        from tests.factories.empire import make_empire

        empire = make_empire()

        empire_repo = AsyncMock()
        empire_repo.find_by_id = AsyncMock(return_value=empire)

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=None)
        rp_repo.save = AsyncMock()

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=AsyncMock(),
            empire_repo=empire_repo,
            session=_make_mock_session(),
        )

        r1 = await service.upsert(empire.id, "DEVELOPER", refs=[])
        r2 = await service.upsert(empire.id, "DEVELOPER", refs=[])
        # 毎回 None を返すため、毎回異なる新規 id が生成される
        assert r1.id != r2.id


# ---------------------------------------------------------------------------
# TC-UT-RPS-006: delete — 不在 → RoleProfileNotFoundError (§確定E)
# ---------------------------------------------------------------------------
class TestDelete:
    """TC-UT-RPS-006: repo が None → RoleProfileNotFoundError (§確定E)。"""

    async def test_delete_raises_when_not_found(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            RoleProfileNotFoundError,
        )
        from bakufu.application.services.role_profile_service import RoleProfileService

        rp_repo = AsyncMock()
        rp_repo.find_by_empire_and_role = AsyncMock(return_value=None)

        service = RoleProfileService(
            rp_repo=rp_repo,
            dt_repo=AsyncMock(),
            empire_repo=AsyncMock(),
            session=_make_mock_session(),
        )

        with pytest.raises(RoleProfileNotFoundError):
            await service.delete(uuid4(), "DEVELOPER")
