"""Workflow Repository: required_deliverables のラウンドトリップ + A08 防御確認 (Issue #117).

TC-IT-WFR-025 / 026 / 027:
- TC-IT-WFR-025: required_deliverables を含む Stage が save → find_by_id でラウンドトリップ
- TC-IT-WFR-026: _stage_from_row が DeliverableRequirement.model_validate 経由で復元 (A08)
  — json.loads → list[dict] → model_validate の経路を物理確認
- TC-IT-WFR-027: required_deliverables=() の Stage が空 tuple でラウンドトリップ

§確定 C (docs/features/workflow/repository/detailed-design.md):
  _from_row: json.loads → list[dict] → [DeliverableRequirement.model_validate(d) for d in ...]
  生 dict を Stage コンストラクタに直接渡すことは禁止。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.domain.value_objects import DeliverableRequirement
from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from sqlalchemy import text

from tests.factories.workflow import make_stage, make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


def _make_req(
    *,
    optional: bool = False,
    major: int = 1,
    minor: int = 0,
    patch: int = 0,
) -> DeliverableRequirement:
    """テスト用 DeliverableRequirement ヘルパ。"""
    return DeliverableRequirement(
        template_ref=DeliverableTemplateRef(
            template_id=uuid4(),
            minimum_version=SemVer(major=major, minor=minor, patch=patch),
        ),
        optional=optional,
    )


# ---------------------------------------------------------------------------
# TC-IT-WFR-025: required_deliverables ラウンドトリップ
# ---------------------------------------------------------------------------
class TestRequiredDeliverablesRoundTrip:
    """TC-IT-WFR-025: required_deliverables の save → find_by_id ラウンドトリップ。"""

    async def test_empty_required_deliverables_round_trips(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-025a / TC-IT-WFR-027: required_deliverables=() が空 tuple でラウンドトリップ。

        R1-17: 空リストは合法。
        """
        stage = make_stage(required_deliverables=())
        workflow = make_workflow(stages=[stage], entry_stage_id=stage.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        assert len(restored.stages) == 1
        assert restored.stages[0].required_deliverables == ()

    async def test_single_required_deliverable_round_trips(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-025b: required_deliverables 1 件が同値でラウンドトリップ。"""
        req = _make_req(optional=False, major=2, minor=3, patch=1)
        stage = make_stage(required_deliverables=(req,))
        workflow = make_workflow(stages=[stage], entry_stage_id=stage.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        assert len(restored.stages) == 1
        r = restored.stages[0].required_deliverables
        assert len(r) == 1
        assert r[0].template_ref.template_id == req.template_ref.template_id
        assert r[0].template_ref.minimum_version.major == 2
        assert r[0].template_ref.minimum_version.minor == 3
        assert r[0].template_ref.minimum_version.patch == 1
        assert r[0].optional is False

    async def test_multiple_required_deliverables_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-025c: required_deliverables 複数件が件数・同値でラウンドトリップ。"""
        req_a = _make_req(optional=False)
        req_b = _make_req(optional=True, major=1, minor=2, patch=0)
        stage = make_stage(required_deliverables=(req_a, req_b))
        workflow = make_workflow(stages=[stage], entry_stage_id=stage.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        r = restored.stages[0].required_deliverables
        assert len(r) == 2
        # template_id の一致確認（順序はステージ保存順）
        template_ids = {dr.template_ref.template_id for dr in r}
        expected_ids = {req_a.template_ref.template_id, req_b.template_ref.template_id}
        assert template_ids == expected_ids
        # optional 値の一致確認（idで引き当て）
        restored_by_id = {dr.template_ref.template_id: dr for dr in r}
        assert restored_by_id[req_a.template_ref.template_id].optional is False
        assert restored_by_id[req_b.template_ref.template_id].optional is True

    async def test_required_deliverables_type_is_tuple(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-025d: 復元後の required_deliverables は tuple[DeliverableRequirement, ...]。"""
        req = _make_req()
        stage = make_stage(required_deliverables=(req,))
        workflow = make_workflow(stages=[stage], entry_stage_id=stage.id)

        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert restored is not None
        rd = restored.stages[0].required_deliverables
        assert isinstance(rd, tuple), f"expected tuple, got {type(rd)}"
        assert all(isinstance(d, DeliverableRequirement) for d in rd)


# ---------------------------------------------------------------------------
# TC-IT-WFR-026: _stage_from_row の A08 防御（model_validate 経由を物理確認）
# ---------------------------------------------------------------------------
class TestStageFromRowA08Defense:
    """TC-IT-WFR-026: _stage_from_row は DeliverableRequirement.model_validate を経由する (A08)。

    §確定 C: json.loads → list[dict] → [DeliverableRequirement.model_validate(d) for d in ...]
    生 dict を Stage コンストラクタに直接渡すことは禁止。

    テスト戦略: DB に valid な required_deliverables_json を直接 INSERT し、
    _stage_from_row を介して復元された Stage が DeliverableRequirement インスタンス
    であることを確認する。型・フィールド値の完全一致で model_validate が通った証拠とする。
    """

    async def test_stage_from_row_deserializes_via_model_validate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-026: DB 生 JSON から復元した Stage.required_deliverables が
        DeliverableRequirement インスタンスで、フィールド値が正しい。
        """
        template_id = uuid4()
        payload = json.dumps(
            [
                {
                    "template_ref": {
                        "template_id": str(template_id),
                        "minimum_version": {"major": 3, "minor": 1, "patch": 4},
                    },
                    "optional": True,
                }
            ]
        )

        # DB に直接 INSERT して find_by_id で water してみる
        wf_id = uuid4().hex
        stage_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO workflows (id, name, entry_stage_id) VALUES (:id, :name, :entry)"
                ),
                {"id": wf_id, "name": "a08-test-wf", "entry": stage_id},
            )
            await session.execute(
                text(
                    "INSERT INTO workflow_stages "
                    "(workflow_id, stage_id, name, kind, roles_csv, "
                    "required_deliverables_json, completion_policy_json, "
                    "notify_channels_json) "
                    "VALUES (:wf_id, :s_id, :name, :kind, :roles, "
                    ":deliverable, :policy, :channels)"
                ),
                {
                    "wf_id": wf_id,
                    "s_id": stage_id,
                    "name": "a08-test-stage",
                    "kind": "WORK",
                    "roles": "DEVELOPER",
                    "deliverable": payload,
                    "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                    "channels": "[]",
                },
            )

        from uuid import UUID

        async with session_factory() as session:
            restored = await SqliteWorkflowRepository(session).find_by_id(UUID(wf_id))

        assert restored is not None
        assert len(restored.stages) == 1
        rd = restored.stages[0].required_deliverables
        assert len(rd) == 1

        # model_validate を経由した証拠: DeliverableRequirement インスタンス
        assert isinstance(rd[0], DeliverableRequirement), (
            "[FAIL] required_deliverables の要素が DeliverableRequirement でない。\n"
            "Next: _stage_from_row が model_validate を経由していることを確認せよ (§確定 C A08)。"
        )
        # template_id の型と値
        assert rd[0].template_ref.template_id == template_id, (
            f"[FAIL] template_id mismatch: {rd[0].template_ref.template_id} != {template_id}"
        )
        # SemVer フィールド
        assert rd[0].template_ref.minimum_version.major == 3
        assert rd[0].template_ref.minimum_version.minor == 1
        assert rd[0].template_ref.minimum_version.patch == 4
        # optional フィールド
        assert rd[0].optional is True, (
            "[FAIL] optional=True が復元されていない。model_validate 経路の確認が必要。"
        )

    async def test_stage_from_row_invalid_json_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-026b: required_deliverables_json が不正な場合 ValidationError を送出。

        A08 Fail-Fast: model_validate が型バリデーションを強制する。raw dict 直渡しでは
        検出されないデータ破損を起動時に検出できる。
        """
        import pydantic

        # template_id が UUID 形式でない壊れたペイロード
        bad_payload = json.dumps(
            [
                {
                    "template_ref": {
                        "template_id": "not-a-uuid",
                        "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                    },
                    "optional": False,
                }
            ]
        )

        wf_id = uuid4().hex
        stage_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO workflows (id, name, entry_stage_id) VALUES (:id, :name, :entry)"
                ),
                {"id": wf_id, "name": "a08-fail-wf", "entry": stage_id},
            )
            await session.execute(
                text(
                    "INSERT INTO workflow_stages "
                    "(workflow_id, stage_id, name, kind, roles_csv, "
                    "required_deliverables_json, completion_policy_json, "
                    "notify_channels_json) "
                    "VALUES (:wf_id, :s_id, :name, :kind, :roles, "
                    ":deliverable, :policy, :channels)"
                ),
                {
                    "wf_id": wf_id,
                    "s_id": stage_id,
                    "name": "a08-fail-stage",
                    "kind": "WORK",
                    "roles": "DEVELOPER",
                    "deliverable": bad_payload,
                    "policy": '{"kind": "approved_by_reviewer", "description": ""}',
                    "channels": "[]",
                },
            )

        from uuid import UUID

        with pytest.raises((pydantic.ValidationError, ValueError)):
            async with session_factory() as session:
                await SqliteWorkflowRepository(session).find_by_id(UUID(wf_id))
