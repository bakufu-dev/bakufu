"""workflow / http-api ユニットテスト — サービス検証 (TC-UT-WFH-010).

Covers:
  TC-UT-WFH-010  WorkflowService.__init__ 3 引数構造 (detailed-design.md §確定G)

Issue: #58
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestWorkflowServiceInit:
    """TC-UT-WFH-010: WorkflowService.__init__ 3 引数構造 (§確定G)。"""

    def _make_mock_session(self) -> Any:
        from unittest.mock import AsyncMock

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=None)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.begin = MagicMock(return_value=mock_cm)
        return mock_session

    async def test_service_constructs_successfully(self) -> None:
        from bakufu.application.services.workflow_service import WorkflowService

        service = WorkflowService(
            workflow_repo=MagicMock(),
            room_repo=MagicMock(),
            session=self._make_mock_session(),
        )
        assert service is not None

    async def test_service_stores_workflow_repo(self) -> None:
        """_workflow_repo に workflow_repo が格納される。"""
        from bakufu.application.services.workflow_service import WorkflowService

        mock_repo = MagicMock()
        service = WorkflowService(
            workflow_repo=mock_repo,
            room_repo=MagicMock(),
            session=self._make_mock_session(),
        )
        assert service._workflow_repo is mock_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_room_repo(self) -> None:
        """_room_repo に room_repo が格納される。"""
        from bakufu.application.services.workflow_service import WorkflowService

        mock_repo = MagicMock()
        service = WorkflowService(
            workflow_repo=MagicMock(),
            room_repo=mock_repo,
            session=self._make_mock_session(),
        )
        assert service._room_repo is mock_repo  # pyright: ignore[reportPrivateUsage]

    async def test_service_stores_session(self) -> None:
        """_session に session が格納される。"""
        from bakufu.application.services.workflow_service import WorkflowService

        mock_session = self._make_mock_session()
        service = WorkflowService(
            workflow_repo=MagicMock(),
            room_repo=MagicMock(),
            session=mock_session,
        )
        assert service._session is mock_session  # pyright: ignore[reportPrivateUsage]
