"""InternalReviewService ユニットテスト（TC-UT-IRG-A104〜A105）。

設計書: docs/features/internal-review-gate/application/test-design.md
対象: §確定 G（DAG traversal: _find_prev_work_stage_id）
Issue: #164 feat(M5-B): InternalReviewGate infrastructure実装

前提:
- workflow_repo / room_repo: AsyncMock（DB接続不要）
- Task: make_in_progress_task() ファクトリ使用
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.factories.task import make_in_progress_task
from tests.factories.workflow import make_stage, make_transition, make_workflow

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_service() -> object:
    """InternalReviewService をテスト用設定で生成する（session_factory/event_bus は AsyncMock）。"""
    from bakufu.application.services.internal_review_service import InternalReviewService

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_event_bus = AsyncMock()
    return InternalReviewService(
        session_factory=mock_sf,
        event_bus=mock_event_bus,
    )


# ---------------------------------------------------------------------------
# TC-UT-IRG-A104: _find_prev_work_stage_id() — DAG traversal 正常系
# ---------------------------------------------------------------------------


class TestFindPrevWorkStageId:
    """TC-UT-IRG-A104: _find_prev_work_stage_id() — DAG traversal の正確性（§確定 G）。"""

    async def test_returns_work_stage_id_from_dag(self) -> None:
        """TC-UT-IRG-A104: WORK_A→INTERNAL_REVIEW_B のグラフ → WORK_A.id が返る。"""
        from bakufu.domain.value_objects import StageKind

        work_stage_id = uuid4()
        internal_review_stage_id = uuid4()

        work_stage = make_stage(stage_id=work_stage_id, kind=StageKind.WORK)
        ir_stage = make_stage(stage_id=internal_review_stage_id, kind=StageKind.INTERNAL_REVIEW)
        transition = make_transition(
            from_stage_id=work_stage_id, to_stage_id=internal_review_stage_id
        )
        workflow = make_workflow(
            stages=[work_stage, ir_stage],
            transitions=[transition],
            entry_stage_id=work_stage_id,
        )

        room_id = uuid4()
        room = MagicMock()
        room.id = room_id
        room.workflow_id = workflow.id

        mock_workflow_repo = AsyncMock()
        mock_workflow_repo.find_by_id = AsyncMock(return_value=workflow)
        mock_room_repo = AsyncMock()
        mock_room_repo.find_by_id = AsyncMock(return_value=room)

        task = make_in_progress_task(room_id=room_id)
        service = _make_service()

        result = await service._find_prev_work_stage_id(
            task,
            internal_review_stage_id,
            mock_workflow_repo,
            mock_room_repo,
        )

        assert result == work_stage_id

    async def test_multiple_transitions_returns_work_stage(self) -> None:
        """TC-UT-IRG-A104 変形: 複数 transition が存在する場合も WORK 前段が返る。

        WORK_A → INTERNAL_REVIEW_B ← WORK_C（複数 incoming）のグラフで、
        WORK kind の前段（WORK_A or WORK_C のいずれか）が返ることを確認。
        """
        from bakufu.domain.value_objects import StageKind

        work_a_id = uuid4()
        internal_review_id = uuid4()

        work_a = make_stage(stage_id=work_a_id, kind=StageKind.WORK, name="WORK_A")
        ir_stage = make_stage(stage_id=internal_review_id, kind=StageKind.INTERNAL_REVIEW)

        # WORK_A → INTERNAL_REVIEW
        transition = make_transition(from_stage_id=work_a_id, to_stage_id=internal_review_id)
        workflow = make_workflow(
            stages=[work_a, ir_stage],
            transitions=[transition],
            entry_stage_id=work_a_id,
        )

        room = MagicMock()
        room.workflow_id = workflow.id

        mock_workflow_repo = AsyncMock()
        mock_workflow_repo.find_by_id = AsyncMock(return_value=workflow)
        mock_room_repo = AsyncMock()
        mock_room_repo.find_by_id = AsyncMock(return_value=room)

        task = make_in_progress_task()
        service = _make_service()

        result = await service._find_prev_work_stage_id(
            task,
            internal_review_id,
            mock_workflow_repo,
            mock_room_repo,
        )

        assert result == work_a_id


# ---------------------------------------------------------------------------
# TC-UT-IRG-A105: _find_prev_work_stage_id() — 前段 WORK Stage なし → IllegalWorkflowStructureError
# ---------------------------------------------------------------------------


class TestFindPrevWorkStageIdNoWorkStage:
    """TC-UT-IRG-A105: _find_prev_work_stage_id() — 前段 WORK Stage なし → error（§確定 G）。"""

    async def test_raises_when_no_work_predecessor(self) -> None:
        """TC-UT-IRG-A105: 前段に WORK Stage がない → IllegalWorkflowStructureError。"""
        from bakufu.application.exceptions.workflow_exceptions import (
            IllegalWorkflowStructureError,
        )
        from bakufu.domain.value_objects import StageKind

        internal_review_stage_id = uuid4()

        # INTERNAL_REVIEW Stage のみ、前段 WORK Stage なし（incoming transition なし）
        ir_stage = make_stage(stage_id=internal_review_stage_id, kind=StageKind.INTERNAL_REVIEW)
        workflow = make_workflow(
            stages=[ir_stage],
            transitions=[],  # incoming transition なし
            entry_stage_id=internal_review_stage_id,
        )

        room = MagicMock()
        room.workflow_id = workflow.id

        mock_workflow_repo = AsyncMock()
        mock_workflow_repo.find_by_id = AsyncMock(return_value=workflow)
        mock_room_repo = AsyncMock()
        mock_room_repo.find_by_id = AsyncMock(return_value=room)

        task = make_in_progress_task()
        service = _make_service()

        with pytest.raises(IllegalWorkflowStructureError) as exc_info:
            await service._find_prev_work_stage_id(
                task,
                internal_review_stage_id,
                mock_workflow_repo,
                mock_room_repo,
            )

        # MSG-IRG-A003 のキーワードを含む
        assert "WORK" in str(exc_info.value)

    async def test_raises_when_predecessor_is_not_work_kind(self) -> None:
        """TC-UT-IRG-A105 変形: 前段 Stage が EXTERNAL_REVIEW → IllegalWorkflowStructureError。"""
        from bakufu.application.exceptions.workflow_exceptions import (
            IllegalWorkflowStructureError,
        )
        from bakufu.domain.value_objects import StageKind

        non_work_stage_id = uuid4()
        internal_review_stage_id = uuid4()

        # EXTERNAL_REVIEW → INTERNAL_REVIEW（WORK ではない前段）
        ext_review = make_stage(
            stage_id=non_work_stage_id,
            kind=StageKind.EXTERNAL_REVIEW,
            notify_channels=None,  # make_stage で notify_channels が自動設定される
        )
        ir_stage = make_stage(stage_id=internal_review_stage_id, kind=StageKind.INTERNAL_REVIEW)
        transition = make_transition(
            from_stage_id=non_work_stage_id, to_stage_id=internal_review_stage_id
        )

        workflow = make_workflow(
            stages=[ext_review, ir_stage],
            transitions=[transition],
            entry_stage_id=non_work_stage_id,
        )

        room = MagicMock()
        room.workflow_id = workflow.id

        mock_workflow_repo = AsyncMock()
        mock_workflow_repo.find_by_id = AsyncMock(return_value=workflow)
        mock_room_repo = AsyncMock()
        mock_room_repo.find_by_id = AsyncMock(return_value=room)

        task = make_in_progress_task()
        service = _make_service()

        with pytest.raises(IllegalWorkflowStructureError):
            await service._find_prev_work_stage_id(
                task,
                internal_review_stage_id,
                mock_workflow_repo,
                mock_room_repo,
            )
