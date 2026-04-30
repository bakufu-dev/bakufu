"""required_deliverables VO 契約 + Stage 不変条件 (Issue #117).

対象:
- TC-UT-VO-WF-005〜007: DeliverableRequirement VO (構築 / frozen 不変性)
- TC-UT-WF-061〜064: Stage.required_deliverables (空 / 1 件 / 重複 / from_dict)
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import StageInvariantViolation
from bakufu.domain.value_objects import DeliverableRequirement
from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer
from bakufu.domain.workflow import Workflow

from tests.factories.workflow import build_v_model_payload, make_stage


def _make_ref(template_id: object | None = None) -> DeliverableTemplateRef:
    """妥当な DeliverableTemplateRef を 1 件組み立てるヘルパ。"""
    tid = template_id if template_id is not None else uuid4()
    return DeliverableTemplateRef(
        template_id=tid,
        minimum_version=SemVer(major=1, minor=0, patch=0),
    )


def _make_req(*, optional: bool = False) -> DeliverableRequirement:
    """妥当な DeliverableRequirement を 1 件組み立てるヘルパ。"""
    return DeliverableRequirement(template_ref=_make_ref(), optional=optional)


# ---------------------------------------------------------------------------
# TC-UT-VO-WF-005 / 006 / 007: DeliverableRequirement VO
# ---------------------------------------------------------------------------
class TestDeliverableRequirementVO:
    """DeliverableRequirement VO 構築 + frozen 不変性 (TC-UT-VO-WF-005〜007)."""

    def test_construction_optional_false(self) -> None:
        """TC-UT-VO-WF-005: optional=False(デフォルト)で構築成功し、フィールドが保持される。"""
        req = _make_req(optional=False)
        assert req.optional is False
        assert isinstance(req.template_ref, DeliverableTemplateRef)

    def test_construction_optional_true(self) -> None:
        """TC-UT-VO-WF-006: optional=True で構築成功し、フィールドが保持される。"""
        req = _make_req(optional=True)
        assert req.optional is True

    def test_frozen_assignment_raises(self) -> None:
        """TC-UT-VO-WF-007: frozen=True — 直接代入は TypeError を送出する。"""
        req = _make_req()
        with pytest.raises((TypeError, Exception)):
            req.optional = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-UT-WF-061 / 062: Stage.required_deliverables 正常系
# ---------------------------------------------------------------------------
class TestStageRequiredDeliverablesHappyPath:
    """Stage.required_deliverables の正常系 (TC-UT-WF-061 / 062)."""

    def test_empty_tuple_constructs(self) -> None:
        """TC-UT-WF-061: required_deliverables=() で Stage 構築成功 (R1-17: 空は合法)。"""
        stage = make_stage(required_deliverables=())
        assert stage.required_deliverables == ()

    def test_single_item_constructs(self) -> None:
        """TC-UT-WF-062: required_deliverables 1 件で構築成功、len == 1。"""
        req = _make_req()
        stage = make_stage(required_deliverables=(req,))
        assert len(stage.required_deliverables) == 1
        assert stage.required_deliverables[0] == req


# ---------------------------------------------------------------------------
# TC-UT-WF-063: 重複 template_id で StageInvariantViolation
# ---------------------------------------------------------------------------
class TestStageRequiredDeliverablesDuplicate:
    """Stage.required_deliverables 内 template_id 重複 → 不変条件違反 (TC-UT-WF-063)."""

    def test_duplicate_template_id_raises_stage_invariant_violation(self) -> None:
        """TC-UT-WF-063: 同一 template_id を持つ DeliverableRequirement 2 件は
        StageInvariantViolation(kind='duplicate_required_deliverable') を raise する。
        Workflow 構築前に Stage レベルで検出される (R1-17)。
        """
        shared_id = uuid4()
        ref_a = DeliverableTemplateRef(
            template_id=shared_id,
            minimum_version=SemVer(major=1, minor=0, patch=0),
        )
        ref_b = DeliverableTemplateRef(
            template_id=shared_id,
            minimum_version=SemVer(major=2, minor=0, patch=0),
        )
        req_a = DeliverableRequirement(template_ref=ref_a, optional=False)
        req_b = DeliverableRequirement(template_ref=ref_b, optional=True)

        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_deliverables=(req_a, req_b))

        err = excinfo.value
        assert err.kind == "duplicate_required_deliverable"

    def test_msg_wf_013_exact_wording(self) -> None:
        """TC-UT-WF-063: MSG-WF-013 の文言が完全一致。
        ``[FAIL] Stage {stage_id} required_deliverables has duplicate template_id: {template_id}``
        """
        shared_id = uuid4()
        ref = _make_ref(template_id=shared_id)
        req = DeliverableRequirement(template_ref=ref, optional=False)

        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_deliverables=(req, req))

        err = excinfo.value
        stage_id_str = str(err.detail["stage_id"])
        template_id_str = str(err.detail["template_id"])
        expected_message = (
            f"[FAIL] Stage {stage_id_str} required_deliverables "
            f"has duplicate template_id: {template_id_str}"
        )
        assert err.message == expected_message

    def test_detail_keys_are_whitelisted(self) -> None:
        """TC-UT-WF-063: detail は {"stage_id": str, "template_id": str} のキーのみ (A09)。"""
        shared_id = uuid4()
        ref = _make_ref(template_id=shared_id)
        req = DeliverableRequirement(template_ref=ref, optional=False)

        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_deliverables=(req, req))

        detail = excinfo.value.detail
        assert set(detail.keys()) == {"stage_id", "template_id"}, (
            f"detail keys must be exactly {{stage_id, template_id}}, got {set(detail.keys())}"
        )
        assert isinstance(detail["stage_id"], str)
        assert isinstance(detail["template_id"], str)


# ---------------------------------------------------------------------------
# TC-UT-WF-064: from_dict で required_deliverables ペイロード
# ---------------------------------------------------------------------------
class TestFromDictWithRequiredDeliverables:
    """from_dict が required_deliverables 含む Stage ペイロードを受理する (TC-UT-WF-064)."""

    def test_from_dict_with_required_deliverables_payload(self) -> None:
        """TC-UT-WF-064: required_deliverables を含む Stage ペイロードで Workflow 構築成功。
        stages[n].required_deliverables に 1 件の DeliverableRequirement が含まれる (R1-17)。
        """
        payload = build_v_model_payload()
        stages = cast("list[dict[str, object]]", payload["stages"])
        template_id = uuid4()
        stages[0]["required_deliverables"] = [
            {
                "template_ref": {
                    "template_id": str(template_id),
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                },
                "optional": False,
            }
        ]
        workflow = Workflow.from_dict(payload)
        stage = workflow.stages[0]
        assert len(stage.required_deliverables) == 1
        assert stage.required_deliverables[0].template_ref.template_id == template_id
        assert stage.required_deliverables[0].optional is False
