"""room-matching 結合テスト — assign_agent マッチング系 (TC-IT-RMM-001〜006).

Covers:
  TC-IT-RMM-001  assign_agent + カバレッジ充足（RoleProfile）→ 201
  TC-IT-RMM-002  assign_agent + カバレッジ不足 → 422 / deliverable_matching_failed
  TC-IT-RMM-003  422 レスポンスの missing 構造（stage_id / stage_name / template_id）
  TC-IT-RMM-004  custom_refs で充足 → 201（RoleProfile なしでも通過、§確定B 優先1）
  TC-IT-RMM-005  custom_refs=[] + required → 422（空は「提供なし」明示宣言、§確定B 優先1）
  TC-IT-RMM-006  RoomOverride 設定後 assign_agent → override refs で充足 → 201（§確定B 優先2）

完全ブラックボックス: DB 直接確認・内部状態参照禁止。HTTP 経由のみで検証する。

Issue: #120
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.integration.test_room_matching_http_api.conftest import (
    RmmTestCtx,
    _create_deliverable_template,
    _create_empire,
    _create_room,
    _make_min_version,
    _put_role_profile,
    _seed_agent,
    _seed_workflow_with_required_deliverable,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-RMM-001: assign_agent + カバレッジ充足（RoleProfile）→ 201
# ---------------------------------------------------------------------------
class TestAssignAgentCoverageSatisfied:
    """TC-IT-RMM-001: RoleProfile に required template_id が含まれる → assign_agent 201。"""

    async def test_assign_with_role_profile_coverage_returns_201(self, rmm_ctx: RmmTestCtx) -> None:
        """RoleProfile が required_deliverable を充足する場合 → 201。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        # 実在 DeliverableTemplate が必要（RoleProfile登録時に存在確認あり）
        dt = await _create_deliverable_template(rmm_ctx.client)
        template_id = UUID(str(dt["id"]))
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, template_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)
        await _put_role_profile(rmm_ctx.client, str(empire_id), "DEVELOPER", str(template_id))

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        assert resp.status_code == 201

    async def test_assign_with_role_profile_coverage_member_added(
        self, rmm_ctx: RmmTestCtx
    ) -> None:
        """充足後の GET でメンバーが追加されていることをラウンドトリップ確認。"""
        empire = await _create_empire(rmm_ctx.client, name="ラウンドトリップ幕府")
        empire_id = UUID(str(empire["id"]))
        dt = await _create_deliverable_template(rmm_ctx.client, name="ラウンドトリップテンプレ")
        template_id = UUID(str(dt["id"]))
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, template_id)
        room = await _create_room(
            rmm_ctx.client, str(empire_id), str(wf.id), name="ラウンドトリップ室"
        )
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)
        await _put_role_profile(rmm_ctx.client, str(empire_id), "DEVELOPER", str(template_id))
        await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )

        get_resp = await rmm_ctx.client.get(f"/api/rooms/{room['id']}")
        assert len(get_resp.json()["members"]) == 1


# ---------------------------------------------------------------------------
# TC-IT-RMM-002: assign_agent + カバレッジ不足 → 422
# ---------------------------------------------------------------------------
class TestAssignAgentCoverageInsufficient:
    """TC-IT-RMM-002: RoleProfile 未設定、required_deliverable あり → 422。"""

    async def test_assign_without_coverage_returns_422(self, rmm_ctx: RmmTestCtx) -> None:
        """RoleProfile なし（effective_refs=空）で required_deliverable → 422。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()  # 実在不要（matching は UUID 比較のみ）
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        assert resp.status_code == 422

    async def test_assign_without_coverage_error_code(self, rmm_ctx: RmmTestCtx) -> None:
        """422 レスポンスの error.code == 'deliverable_matching_failed'（§確定F）。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        assert resp.json()["error"]["code"] == "deliverable_matching_failed"


# ---------------------------------------------------------------------------
# TC-IT-RMM-003: 422 missing 構造確認
# ---------------------------------------------------------------------------
class TestAssignAgentMissingStructure:
    """TC-IT-RMM-003: 422 missing 要素に stage_id/stage_name/template_id が含まれる。"""

    async def test_missing_contains_stage_id(self, rmm_ctx: RmmTestCtx) -> None:
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        missing = resp.json()["error"]["detail"]["missing"]
        assert len(missing) >= 1
        assert "stage_id" in missing[0]

    async def test_missing_contains_stage_name(self, rmm_ctx: RmmTestCtx) -> None:
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        missing = resp.json()["error"]["detail"]["missing"]
        assert "stage_name" in missing[0]

    async def test_missing_contains_template_id(self, rmm_ctx: RmmTestCtx) -> None:
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        missing = resp.json()["error"]["detail"]["missing"]
        assert missing[0]["template_id"] == str(required_id)


# ---------------------------------------------------------------------------
# TC-IT-RMM-004: custom_refs で充足 → 201（§確定B 優先1）
# ---------------------------------------------------------------------------
class TestAssignAgentCustomRefsCoverage:
    """TC-IT-RMM-004: custom_refs に required template_id を含める → 201（RoleProfile なし）。"""

    async def test_custom_refs_coverage_returns_201(self, rmm_ctx: RmmTestCtx) -> None:
        """custom_refs に required template_id → 201（§確定B 優先1: リポジトリ参照なし）。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={
                "agent_id": str(agent.id),
                "role": "DEVELOPER",
                "custom_refs": [
                    {"template_id": str(required_id), "minimum_version": _make_min_version()}
                ],
            },
        )
        assert resp.status_code == 201

    async def test_custom_refs_overrides_empty_role_profile(self, rmm_ctx: RmmTestCtx) -> None:
        """custom_refs は RoleProfile より優先される（§確定B 優先1）。RoleProfile 不在でも通過。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        other_id = uuid4()  # RoleProfile には別テンプレが入っている想定（未設定でも同じ）
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={
                "agent_id": str(agent.id),
                "role": "DEVELOPER",
                "custom_refs": [
                    {"template_id": str(required_id), "minimum_version": _make_min_version()}
                ],
            },
        )
        assert resp.status_code == 201
        _ = other_id  # unused — explicit about intent


# ---------------------------------------------------------------------------
# TC-IT-RMM-005: custom_refs=[] + required → 422（§確定B 優先1）
# ---------------------------------------------------------------------------
class TestAssignAgentEmptyCustomRefs:
    """TC-IT-RMM-005: custom_refs=[] は「提供なし」の明示宣言 → 422。

    RoleProfile に充足する refs があっても custom_refs=[] は優先され、
    matching に失敗することを検証する（§確定B 優先1）。
    """

    async def test_empty_custom_refs_ignores_role_profile_returns_422(
        self, rmm_ctx: RmmTestCtx
    ) -> None:
        """custom_refs=[] はフォールバックを無視し空タプルとして確定 → 422。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        # 実在テンプレが必要（RoleProfile 登録バリデーション用）
        dt = await _create_deliverable_template(rmm_ctx.client, name="RP用テンプレ")
        template_id = UUID(str(dt["id"]))
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, template_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)
        # RoleProfile を充足状態にする
        await _put_role_profile(rmm_ctx.client, str(empire_id), "DEVELOPER", str(template_id))

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER", "custom_refs": []},
        )
        assert resp.status_code == 422

    async def test_empty_custom_refs_returns_matching_failed_code(
        self, rmm_ctx: RmmTestCtx
    ) -> None:
        """custom_refs=[] → deliverable_matching_failed（§確定B 優先1 / §確定F）。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        dt = await _create_deliverable_template(rmm_ctx.client, name="RP用テンプレ2")
        template_id = UUID(str(dt["id"]))
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, template_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)
        await _put_role_profile(rmm_ctx.client, str(empire_id), "DEVELOPER", str(template_id))

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER", "custom_refs": []},
        )
        assert resp.json()["error"]["code"] == "deliverable_matching_failed"


# ---------------------------------------------------------------------------
# TC-IT-RMM-006: RoomOverride → 201（§確定B 優先2）
# ---------------------------------------------------------------------------
class TestAssignAgentRoomOverrideCoverage:
    """TC-IT-RMM-006: RoomOverride に required template_id → assign_agent 201（§確定B 優先2）。"""

    async def test_room_override_satisfies_matching_returns_201(self, rmm_ctx: RmmTestCtx) -> None:
        """RoleProfile 不在 + RoomOverride に required_id → 201（override が優先）。"""
        empire = await _create_empire(rmm_ctx.client)
        empire_id = UUID(str(empire["id"]))
        required_id = uuid4()
        wf = await _seed_workflow_with_required_deliverable(rmm_ctx.session_factory, required_id)
        room = await _create_room(rmm_ctx.client, str(empire_id), str(wf.id))
        agent = await _seed_agent(rmm_ctx.session_factory, empire_id)

        # RoomOverride 設定（RoleProfile は未設定）
        await rmm_ctx.client.put(
            f"/api/rooms/{room['id']}/role-overrides/DEVELOPER",
            json={
                "deliverable_template_refs": [
                    {"template_id": str(required_id), "minimum_version": _make_min_version()}
                ]
            },
        )

        resp = await rmm_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "DEVELOPER"},
        )
        assert resp.status_code == 201
