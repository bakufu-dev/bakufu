"""RoomMatchingService ユニットテスト (TC-UT-RMS-001〜013).

Covers:
  validate_coverage:
    TC-UT-RMS-001  全 Stage 充足 → 空リスト（§確定A, E）
    TC-UT-RMS-002  required_deliverables なし → 空リスト（境界値）
    TC-UT-RMS-003  optional=True のみ → 空リスト（§確定E）
    TC-UT-RMS-004  1 件不足 → missing=[1 件]（§確定A）
    TC-UT-RMS-005  複数 Stage 複数不足 → 全件収集（§確定C）
    TC-UT-RMS-006  effective_refs 空タプル + required あり → 全件不足（境界値）
    TC-UT-RMS-007  missing 要素の stage_id / stage_name / template_id 正確性（§確定F）

  resolve_effective_refs:
    TC-UT-RMS-008  custom_refs not None → 即返却（§確定B 優先1）
    TC-UT-RMS-009  custom_refs 空タプル → 空タプル返却（§確定B 優先1 境界値）
    TC-UT-RMS-010  RoomOverride あり → override.refs（§確定B 優先2）
    TC-UT-RMS-011  Override なし / RoleProfile あり → profile.refs（§確定B 優先3）
    TC-UT-RMS-012  両方なし → 空タプル（§確定B 優先4）
    TC-UT-RMS-013  RoomOverride 存在時 RoleProfile は呼ばれない（短絡評価）

validate_coverage は純粋同期関数（I/O なし）。resolve_effective_refs は async。
外部 I/O (repo) は AsyncMock でモックし、factory 経由の値を返却させる（assumed mock 禁止）。

Issue: #120
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from bakufu.application.services.room_matching_service import RoomMatchingService


def _make_service(
    override_repo: AsyncMock | None = None,
    role_profile_repo: AsyncMock | None = None,
) -> RoomMatchingService:
    from bakufu.application.services.room_matching_service import RoomMatchingService

    return RoomMatchingService(
        override_repo=override_repo if override_repo is not None else AsyncMock(),
        role_profile_repo=role_profile_repo if role_profile_repo is not None else AsyncMock(),
    )


# ===========================================================================
# validate_coverage（同期 — pytest.mark.asyncio 不要）
# ===========================================================================


class TestValidateCoverageNormal:
    """TC-UT-RMS-001/002/003: 正常系・境界値 — 空リストを返すケース。"""

    def test_all_stages_covered_returns_empty(self) -> None:
        """TC-UT-RMS-001: 全 Stage の required_deliverable が effective_refs でカバー → []。"""
        from tests.factories.deliverable_template import make_deliverable_template_ref
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        dr = make_deliverable_requirement()
        template_id = dr.template_ref.template_id
        stage = make_stage(required_deliverables=(dr,))
        wf = make_workflow(stages=[stage])
        ref = make_deliverable_template_ref(template_id=template_id)

        service = _make_service()
        result = service.validate_coverage(wf, (ref,))  # type: ignore[attr-defined]
        assert result == []

    def test_no_required_deliverables_returns_empty(self) -> None:
        """TC-UT-RMS-002: required_deliverables なし → [](境界値: stages 走査しても不足なし)。"""
        from tests.factories.workflow import make_stage, make_workflow

        stage = make_stage()  # required_deliverables=() がデフォルト
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert result == []

    def test_optional_deliverables_not_checked(self) -> None:
        """TC-UT-RMS-003: optional=True の deliverable は検証対象外（§確定E）→ []。"""
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        dr_optional = make_deliverable_requirement(optional=True)
        stage = make_stage(required_deliverables=(dr_optional,))
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert result == []


class TestValidateCoverageMissing:
    """TC-UT-RMS-004/005/006: 不足あり → RoomDeliverableMismatch のリストを返す。"""

    def test_one_missing_returns_list_of_one(self) -> None:
        """TC-UT-RMS-004: 1 Stage / 1 required 不足 → missing=[1 件]（§確定A）。"""
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        dr = make_deliverable_requirement()  # optional=False
        stage = make_stage(required_deliverables=(dr,))
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert len(result) == 1

    def test_multiple_stages_multiple_missing_all_collected(self) -> None:
        """TC-UT-RMS-005: 複数 Stage × 複数不足 → 全件一括収集（§確定C: Fail Fast ≠ 即終了）。"""
        from tests.factories.workflow import (
            make_deliverable_requirement,
            make_stage,
            make_transition,
            make_workflow,
        )

        dr1 = make_deliverable_requirement()
        dr2 = make_deliverable_requirement()
        dr3 = make_deliverable_requirement()
        stage1 = make_stage(required_deliverables=(dr1,))
        stage2 = make_stage(required_deliverables=(dr2, dr3))
        transition = make_transition(from_stage_id=stage1.id, to_stage_id=stage2.id)
        wf = make_workflow(
            stages=[stage1, stage2], transitions=[transition], entry_stage_id=stage1.id
        )

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert len(result) == 3  # dr1, dr2, dr3 全件収集

    def test_empty_effective_refs_returns_all_required_as_missing(self) -> None:
        """TC-UT-RMS-006: effective_refs=() + required → 全件不足（境界値）。"""
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        dr = make_deliverable_requirement()
        stage = make_stage(required_deliverables=(dr,))
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert len(result) >= 1


class TestValidateCoverageMissingAttributes:
    """TC-UT-RMS-007: missing 要素の stage_id / stage_name / template_id の正確性（§確定F）。"""

    def test_mismatch_has_correct_stage_id(self) -> None:
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        dr = make_deliverable_requirement()
        stage = make_stage(name="テストステージ", required_deliverables=(dr,))
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert result[0].stage_id == str(stage.id)

    def test_mismatch_has_correct_stage_name(self) -> None:
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        dr = make_deliverable_requirement()
        stage = make_stage(name="ステージ名確認", required_deliverables=(dr,))
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert result[0].stage_name == "ステージ名確認"

    def test_mismatch_has_correct_template_id(self) -> None:
        from tests.factories.workflow import make_deliverable_requirement, make_stage, make_workflow

        template_id = uuid4()
        dr = make_deliverable_requirement(template_id=template_id)
        stage = make_stage(required_deliverables=(dr,))
        wf = make_workflow(stages=[stage])

        service = _make_service()
        result = service.validate_coverage(wf, ())  # type: ignore[attr-defined]
        assert result[0].template_id == str(template_id)


# ===========================================================================
# resolve_effective_refs（async）
# ===========================================================================


@pytest.mark.asyncio
class TestResolveEffectiveRefsPriority1:
    """TC-UT-RMS-008/009: custom_refs not None → 即返却（§確定B 優先1）。"""

    async def test_custom_refs_not_none_returns_immediately(self) -> None:
        """TC-UT-RMS-008: custom_refs != None → repos 一切呼ばない。"""
        from tests.factories.deliverable_template import make_deliverable_template_ref

        override_repo = AsyncMock()
        role_profile_repo = AsyncMock()
        service = _make_service(override_repo, role_profile_repo)

        ref = make_deliverable_template_ref()
        custom = (ref,)
        result = await service.resolve_effective_refs(uuid4(), uuid4(), "DEVELOPER", custom)  # type: ignore[attr-defined]

        assert result == custom
        override_repo.find_by_room_and_role.assert_not_called()
        role_profile_repo.find_by_empire_and_role.assert_not_called()

    async def test_custom_refs_empty_tuple_returns_empty(self) -> None:
        """TC-UT-RMS-009: custom_refs=() → 空タプルを即返却（repos 不使用、境界値）。"""
        override_repo = AsyncMock()
        role_profile_repo = AsyncMock()
        service = _make_service(override_repo, role_profile_repo)

        result = await service.resolve_effective_refs(uuid4(), uuid4(), "DEVELOPER", ())  # type: ignore[attr-defined]

        assert result == ()
        override_repo.find_by_room_and_role.assert_not_called()
        role_profile_repo.find_by_empire_and_role.assert_not_called()


@pytest.mark.asyncio
class TestResolveEffectiveRefsPriority2:
    """TC-UT-RMS-010/013: RoomOverride あり → override.refs（§確定B 優先2）。"""

    async def test_room_override_found_returns_override_refs(self) -> None:
        """TC-UT-RMS-010: override が存在 → override.deliverable_template_refs を返す。"""
        from tests.factories.deliverable_template import make_deliverable_template_ref
        from tests.factories.room import make_room_role_override

        ref = make_deliverable_template_ref()
        override = make_room_role_override(deliverable_template_refs=(ref,))

        override_repo = AsyncMock()
        override_repo.find_by_room_and_role = AsyncMock(return_value=override)
        role_profile_repo = AsyncMock()
        service = _make_service(override_repo, role_profile_repo)

        result = await service.resolve_effective_refs(uuid4(), uuid4(), "DEVELOPER", None)  # type: ignore[attr-defined]

        assert result == (ref,)

    async def test_room_override_found_role_profile_not_called(self) -> None:
        """TC-UT-RMS-013: override 存在時 RoleProfile は参照されない（短絡評価）。"""
        from tests.factories.room import make_room_role_override

        override = make_room_role_override()
        override_repo = AsyncMock()
        override_repo.find_by_room_and_role = AsyncMock(return_value=override)
        role_profile_repo = AsyncMock()
        service = _make_service(override_repo, role_profile_repo)

        await service.resolve_effective_refs(uuid4(), uuid4(), "TESTER", None)  # type: ignore[attr-defined]

        role_profile_repo.find_by_empire_and_role.assert_not_called()


@pytest.mark.asyncio
class TestResolveEffectiveRefsPriority3:
    """TC-UT-RMS-011: Override なし / RoleProfile あり → profile.refs（§確定B 優先3）。"""

    async def test_no_override_role_profile_found_returns_profile_refs(self) -> None:
        """TC-UT-RMS-011: override=None, RoleProfile あり → profile.deliverable_template_refs。"""
        from tests.factories.deliverable_template import (
            make_deliverable_template_ref,
            make_role_profile,
        )

        ref = make_deliverable_template_ref()
        profile = make_role_profile(deliverable_template_refs=(ref,))

        override_repo = AsyncMock()
        override_repo.find_by_room_and_role = AsyncMock(return_value=None)
        role_profile_repo = AsyncMock()
        role_profile_repo.find_by_empire_and_role = AsyncMock(return_value=profile)
        service = _make_service(override_repo, role_profile_repo)

        result = await service.resolve_effective_refs(uuid4(), uuid4(), "DEVELOPER", None)  # type: ignore[attr-defined]

        assert result == (ref,)


@pytest.mark.asyncio
class TestResolveEffectiveRefsPriority4:
    """TC-UT-RMS-012: 両方なし → 空タプル（§確定B 優先4 / フォールバック）。"""

    async def test_no_override_no_profile_returns_empty_tuple(self) -> None:
        """TC-UT-RMS-012: override=None / profile=None → () を返す（例外なし）。"""
        override_repo = AsyncMock()
        override_repo.find_by_room_and_role = AsyncMock(return_value=None)
        role_profile_repo = AsyncMock()
        role_profile_repo.find_by_empire_and_role = AsyncMock(return_value=None)
        service = _make_service(override_repo, role_profile_repo)

        result = await service.resolve_effective_refs(uuid4(), uuid4(), "REVIEWER", None)  # type: ignore[attr-defined]

        assert result == ()
