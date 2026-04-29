"""room / http-api ユニットテスト — サービス検証 (TC-UT-RM-HTTP-006).

Covers:
  TC-UT-RM-HTTP-006  RoomService.__init__ 4 repo 構造 (Q-3)

Issue: #57
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestRoomServiceInit:
    """TC-UT-RM-HTTP-006: RoomService.__init__ 4 repo 構造 (detailed-design.md §確定G)."""

    def _make_mock_session(self) -> Any:
        """begin() が async context-manager を返す MagicMock session."""
        from unittest.mock import AsyncMock

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=None)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.begin = MagicMock(return_value=mock_cm)
        return mock_session

    async def test_service_constructs_successfully(self) -> None:
        from bakufu.application.services.room_service import RoomService

        service = RoomService(
            room_repo=MagicMock(),
            empire_repo=MagicMock(),
            workflow_repo=MagicMock(),
            agent_repo=MagicMock(),
            session=self._make_mock_session(),
        )
        assert service is not None

    async def test_service_stores_room_repo(self) -> None:
        """_room_repo に room_repo が格納される."""
        from bakufu.application.services.room_service import RoomService

        mock_room_repo = MagicMock()
        service = RoomService(
            room_repo=mock_room_repo,
            empire_repo=MagicMock(),
            workflow_repo=MagicMock(),
            agent_repo=MagicMock(),
            session=self._make_mock_session(),
        )
        assert service._room_repo is mock_room_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_empire_repo(self) -> None:
        """_empire_repo に empire_repo が格納される."""
        from bakufu.application.services.room_service import RoomService

        mock_empire_repo = MagicMock()
        service = RoomService(
            room_repo=MagicMock(),
            empire_repo=mock_empire_repo,
            workflow_repo=MagicMock(),
            agent_repo=MagicMock(),
            session=self._make_mock_session(),
        )
        assert service._empire_repo is mock_empire_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_workflow_repo(self) -> None:
        """_workflow_repo に workflow_repo が格納される."""
        from bakufu.application.services.room_service import RoomService

        mock_workflow_repo = MagicMock()
        service = RoomService(
            room_repo=MagicMock(),
            empire_repo=MagicMock(),
            workflow_repo=mock_workflow_repo,
            agent_repo=MagicMock(),
            session=self._make_mock_session(),
        )
        assert service._workflow_repo is mock_workflow_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_agent_repo(self) -> None:
        """_agent_repo に agent_repo が格納される."""
        from bakufu.application.services.room_service import RoomService

        mock_agent_repo = MagicMock()
        service = RoomService(
            room_repo=MagicMock(),
            empire_repo=MagicMock(),
            workflow_repo=MagicMock(),
            agent_repo=mock_agent_repo,
            session=self._make_mock_session(),
        )
        assert service._agent_repo is mock_agent_repo  # pyright: ignore[reportPrivateUsage]
