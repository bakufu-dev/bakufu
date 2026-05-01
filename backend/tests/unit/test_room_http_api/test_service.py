"""room / http-api ユニットテスト — サービス検証 (TC-UT-RM-HTTP-006).

Covers:
  TC-UT-RM-HTTP-006  RoomService.__init__ 6 repo 構造 (Q-3, §確定H)

Issue: #57
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
class TestRoomServiceInit:
    """TC-UT-RM-HTTP-006: RoomService.__init__ 6 repo 構造 (detailed-design.md §確定H)."""

    def _make_mock_session(self) -> Any:
        """begin() が async context-manager を返す MagicMock session."""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=None)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.begin = MagicMock(return_value=mock_cm)
        return mock_session

    def _make_service(self, **overrides: Any) -> Any:
        """§確定H で凍結された 6 引数を揃えて RoomService を構築するヘルパー。"""
        from bakufu.application.services.room_service import RoomService

        defaults: dict[str, Any] = {
            "room_repo": MagicMock(),
            "empire_repo": MagicMock(),
            "workflow_repo": MagicMock(),
            "agent_repo": MagicMock(),
            "session": self._make_mock_session(),
            "matching_svc": AsyncMock(),
            "override_repo": AsyncMock(),
        }
        defaults.update(overrides)
        return RoomService(**defaults)

    async def test_service_constructs_successfully(self) -> None:
        service = self._make_service()
        assert service is not None

    async def test_service_stores_room_repo(self) -> None:
        """_room_repo に room_repo が格納される."""
        mock_room_repo = MagicMock()
        service = self._make_service(room_repo=mock_room_repo)
        assert service._room_repo is mock_room_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_empire_repo(self) -> None:
        """_empire_repo に empire_repo が格納される."""
        mock_empire_repo = MagicMock()
        service = self._make_service(empire_repo=mock_empire_repo)
        assert service._empire_repo is mock_empire_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_workflow_repo(self) -> None:
        """_workflow_repo に workflow_repo が格納される."""
        mock_workflow_repo = MagicMock()
        service = self._make_service(workflow_repo=mock_workflow_repo)
        assert service._workflow_repo is mock_workflow_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_agent_repo(self) -> None:
        """_agent_repo に agent_repo が格納される."""
        mock_agent_repo = MagicMock()
        service = self._make_service(agent_repo=mock_agent_repo)
        assert service._agent_repo is mock_agent_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_matching_svc(self) -> None:
        """_matching_svc に matching_svc が格納される (§確定H)."""
        mock_matching_svc = AsyncMock()
        service = self._make_service(matching_svc=mock_matching_svc)
        assert service._matching_svc is mock_matching_svc  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_override_repo(self) -> None:
        """_override_repo に override_repo が格納される (§確定H)."""
        mock_override_repo = AsyncMock()
        service = self._make_service(override_repo=mock_override_repo)
        assert service._override_repo is mock_override_repo  # pyright: ignore[reportPrivateUsage]
