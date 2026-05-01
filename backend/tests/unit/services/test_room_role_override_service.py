"""RoomRoleOverrideService ユニットテスト (TC-UT-RMS-014〜020).

Covers:
  upsert_override:
    TC-UT-RMS-014  Room 不在 → RoomNotFoundError
    TC-UT-RMS-015  Room archived → RoomArchivedError
    TC-UT-RMS-016  正常 → RoomRoleOverride 返却（room_id / role 一致）

  delete_override:
    TC-UT-RMS-017  Room 不在 → RoomNotFoundError
    TC-UT-RMS-018  override 不在 → no-op（例外なし）

  find_overrides:
    TC-UT-RMS-019  Room 不在 → RoomNotFoundError
    TC-UT-RMS-020  空リスト → 正常（[] を返す）

外部 I/O (room_repo / override_repo / session) は AsyncMock + MagicMock でモックする。
返却値は factory 経由のオブジェクトを使用（assumed mock 禁止）。

Issue: #120
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
    room_repo: AsyncMock | None = None,
    override_repo: AsyncMock | None = None,
    session: MagicMock | None = None,
) -> object:
    from bakufu.application.services.room_role_override_service import RoomRoleOverrideService

    return RoomRoleOverrideService(
        room_repo=room_repo if room_repo is not None else AsyncMock(),
        override_repo=override_repo if override_repo is not None else AsyncMock(),
        session=session if session is not None else _make_mock_session(),
    )


# ===========================================================================
# upsert_override
# ===========================================================================


class TestUpsertOverrideErrors:
    """TC-UT-RMS-014/015: 異常系 — Room 不在・アーカイブ済み。"""

    async def test_room_not_found_raises_room_not_found_error(self) -> None:
        """TC-UT-RMS-014: room_repo が None を返す → RoomNotFoundError。"""
        from bakufu.application.exceptions.room_exceptions import RoomNotFoundError

        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo)

        with pytest.raises(RoomNotFoundError):
            await service.upsert_override(uuid4(), "DEVELOPER", [])  # type: ignore[attr-defined]

    async def test_room_archived_raises_room_archived_error(self) -> None:
        """TC-UT-RMS-015: Room が archived=True → RoomArchivedError。"""
        from bakufu.application.exceptions.room_exceptions import RoomArchivedError

        from tests.factories.room import make_archived_room

        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=make_archived_room())
        service = _make_service(room_repo=room_repo)

        with pytest.raises(RoomArchivedError):
            await service.upsert_override(uuid4(), "DEVELOPER", [])  # type: ignore[attr-defined]


class TestUpsertOverrideNormal:
    """TC-UT-RMS-016: 正常 → RoomRoleOverride 返却。"""

    async def test_normal_upsert_returns_room_role_override(self) -> None:
        """TC-UT-RMS-016: 正常 Room + override_repo.save → RoomRoleOverride を返す。"""
        from bakufu.domain.room.value_objects import RoomRoleOverride

        from tests.factories.room import make_room

        room_id = uuid4()
        room = make_room(room_id=room_id)
        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=room)
        override_repo = AsyncMock()
        override_repo.save = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo, override_repo=override_repo)

        result = await service.upsert_override(room_id, "DEVELOPER", [])  # type: ignore[attr-defined]

        assert isinstance(result, RoomRoleOverride)

    async def test_normal_upsert_result_room_id_matches(self) -> None:
        """TC-UT-RMS-016 補足: 返却された RoomRoleOverride の room_id が引数と一致する。"""
        from tests.factories.room import make_room

        room_id = uuid4()
        room = make_room(room_id=room_id)
        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=room)
        override_repo = AsyncMock()
        override_repo.save = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo, override_repo=override_repo)

        result = await service.upsert_override(room_id, "DEVELOPER", [])  # type: ignore[attr-defined]

        assert str(result.room_id) == str(room_id)

    async def test_normal_upsert_result_role_matches(self) -> None:
        """TC-UT-RMS-016 補足: 返却された RoomRoleOverride の role が引数と一致する。"""
        from tests.factories.room import make_room

        room = make_room()
        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=room)
        override_repo = AsyncMock()
        override_repo.save = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo, override_repo=override_repo)

        result = await service.upsert_override(uuid4(), "TESTER", [])  # type: ignore[attr-defined]

        assert str(result.role) == "TESTER"


# ===========================================================================
# delete_override
# ===========================================================================


class TestDeleteOverrideErrors:
    """TC-UT-RMS-017: 異常系 — Room 不在。"""

    async def test_room_not_found_raises_room_not_found_error(self) -> None:
        """TC-UT-RMS-017: room_repo が None を返す → RoomNotFoundError。"""
        from bakufu.application.exceptions.room_exceptions import RoomNotFoundError

        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo)

        with pytest.raises(RoomNotFoundError):
            await service.delete_override(uuid4(), "DEVELOPER")  # type: ignore[attr-defined]


class TestDeleteOverrideNoOp:
    """TC-UT-RMS-018: override 不在 → no-op（例外なし、REQ-RM-MATCH-004 no-op 仕様）。"""

    async def test_not_existing_override_no_exception(self) -> None:
        """TC-UT-RMS-018: override_repo.delete が呼ばれても例外なし（delete の結果は void）。"""
        from tests.factories.room import make_room

        room = make_room()
        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=room)
        override_repo = AsyncMock()
        override_repo.delete = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo, override_repo=override_repo)

        # no-op は例外なし
        result = await service.delete_override(uuid4(), "DEVELOPER")  # type: ignore[attr-defined]

        assert result is None
        override_repo.delete.assert_called_once()


# ===========================================================================
# find_overrides
# ===========================================================================


class TestFindOverridesErrors:
    """TC-UT-RMS-019: 異常系 — Room 不在。"""

    async def test_room_not_found_raises_room_not_found_error(self) -> None:
        """TC-UT-RMS-019: room_repo が None を返す → RoomNotFoundError。"""
        from bakufu.application.exceptions.room_exceptions import RoomNotFoundError

        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=None)
        service = _make_service(room_repo=room_repo)

        with pytest.raises(RoomNotFoundError):
            await service.find_overrides(uuid4())  # type: ignore[attr-defined]


class TestFindOverridesEmpty:
    """TC-UT-RMS-020: 空リスト → 正常（REQ-RM-MATCH-005 境界値）。"""

    async def test_empty_overrides_returns_empty_list(self) -> None:
        """TC-UT-RMS-020: override_repo が [] を返す → [] を返す（例外なし）。"""
        from tests.factories.room import make_room

        room = make_room()
        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=room)
        override_repo = AsyncMock()
        override_repo.find_all_by_room = AsyncMock(return_value=[])
        service = _make_service(room_repo=room_repo, override_repo=override_repo)

        result = await service.find_overrides(uuid4())  # type: ignore[attr-defined]

        assert result == []

    async def test_non_empty_overrides_returns_all(self) -> None:
        """TC-UT-RMS-020 補足: 複数 override → 全件返却。"""
        from tests.factories.room import make_room, make_room_role_override

        room = make_room()
        overrides = [make_room_role_override(), make_room_role_override()]
        room_repo = AsyncMock()
        room_repo.find_by_id = AsyncMock(return_value=room)
        override_repo = AsyncMock()
        override_repo.find_all_by_room = AsyncMock(return_value=overrides)
        service = _make_service(room_repo=room_repo, override_repo=override_repo)

        result = await service.find_overrides(uuid4())  # type: ignore[attr-defined]

        assert len(result) == 2
