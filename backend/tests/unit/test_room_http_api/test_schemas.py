"""room / http-api ユニットテスト — スキーマ検証 (TC-UT-RM-HTTP-001~004).

Covers:
  TC-UT-RM-HTTP-001  RoomCreate スキーマ検証 (Q-3)
  TC-UT-RM-HTTP-002  RoomUpdate スキーマ検証 (Q-3)
  TC-UT-RM-HTTP-003  AgentAssignRequest スキーマ検証 (Q-3)
  TC-UT-RM-HTTP-004  RoomResponse / MemberResponse / RoomListResponse シリアライズ (Q-3)

Issue: #57
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError


class TestRoomCreateSchema:
    """TC-UT-RM-HTTP-001: RoomCreate スキーマ検証 (name / description / prompt_kit) (Q-3)。"""

    def test_valid_name_workflow_id_passes(self) -> None:
        """(a) name="Vモデル開発室", workflow_id=uuid4() → バリデーション通過."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        schema = RoomCreate(name="Vモデル開発室", workflow_id=uuid4())
        assert schema.name == "Vモデル開発室"

    def test_empty_name_raises(self) -> None:
        """(b) name="" → min_length=1 違反 → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        with pytest.raises(ValidationError):
            RoomCreate(name="", workflow_id=uuid4())

    def test_name_too_long_raises(self) -> None:
        """(c) name='x'*81 → max_length=80 違反 → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        with pytest.raises(ValidationError):
            RoomCreate(name="x" * 81, workflow_id=uuid4())

    def test_name_80_chars_passes(self) -> None:
        """Boundary: 80 文字は上限に等しく通過すべき."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        schema = RoomCreate(name="a" * 80, workflow_id=uuid4())
        assert len(schema.name) == 80

    def test_description_too_long_raises(self) -> None:
        """(d) description='x'*501 → max_length=500 違反 → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        with pytest.raises(ValidationError):
            RoomCreate(name="X", workflow_id=uuid4(), description="x" * 501)

    def test_prompt_kit_too_long_raises(self) -> None:
        """(e) prompt_kit_prefix_markdown='x'*10001 → max_length=10000 違反 → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        with pytest.raises(ValidationError):
            RoomCreate(name="X", workflow_id=uuid4(), prompt_kit_prefix_markdown="x" * 10001)

    def test_extra_field_raises(self) -> None:
        """(f) extra_field='z' → extra='forbid' → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        with pytest.raises(ValidationError):
            RoomCreate.model_validate(
                {"name": "X", "workflow_id": str(uuid4()), "extra_field": "z"}
            )

    def test_default_description_is_empty_string(self) -> None:
        """description 省略 → デフォルト ''."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        schema = RoomCreate(name="X", workflow_id=uuid4())
        assert schema.description == ""

    def test_default_prompt_kit_is_empty_string(self) -> None:
        """prompt_kit_prefix_markdown 省略 → デフォルト ''."""
        from bakufu.interfaces.http.schemas.room import RoomCreate

        schema = RoomCreate(name="X", workflow_id=uuid4())
        assert schema.prompt_kit_prefix_markdown == ""


class TestRoomUpdateSchema:
    """TC-UT-RM-HTTP-002: RoomUpdate — オプションフィールドによる部分更新。"""

    def test_valid_name_passes(self) -> None:
        """(a) name='新名前' → 通過."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        schema = RoomUpdate(name="新名前")
        assert schema.name == "新名前"

    def test_name_none_passes(self) -> None:
        """(b) name=None → 通過 (変更なし)."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        schema = RoomUpdate(name=None)
        assert schema.name is None

    def test_empty_name_raises(self) -> None:
        """(c) name='' → min_length=1 違反 → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        with pytest.raises(ValidationError):
            RoomUpdate(name="")

    def test_description_none_passes(self) -> None:
        """(d) description=None → 通過 (変更なし)."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        schema = RoomUpdate(description=None)
        assert schema.description is None

    def test_all_fields_none_passes(self) -> None:
        """(e) 全フィールド None → 通過 (全変更なし)."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        schema = RoomUpdate()
        assert schema.name is None
        assert schema.description is None
        assert schema.prompt_kit_prefix_markdown is None

    def test_extra_field_raises(self) -> None:
        """(f) extra_field='z' → extra='forbid' → ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        with pytest.raises(ValidationError):
            RoomUpdate.model_validate({"name": "X", "extra_field": "z"})

    def test_default_all_none(self) -> None:
        """全フィールド省略時のデフォルトは None."""
        from bakufu.interfaces.http.schemas.room import RoomUpdate

        schema = RoomUpdate()
        assert schema.name is None
        assert schema.description is None
        assert schema.prompt_kit_prefix_markdown is None


class TestAgentAssignRequestSchema:
    """TC-UT-RM-HTTP-003: AgentAssignRequest の role バリデーション（_validate_role）。"""

    def test_valid_role_leader_passes(self) -> None:
        """(a) agent_id=uuid4(), role='LEADER' → 通過."""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        schema = AgentAssignRequest(agent_id=uuid4(), role="LEADER")
        assert schema.role == "LEADER"

    def test_all_valid_roles_pass(self) -> None:
        """有効 role 全10値が通過することを確認。"""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        valid_roles = frozenset(
            {
                "LEADER",
                "DEVELOPER",
                "TESTER",
                "REVIEWER",
                "UX",
                "SECURITY",
                "ASSISTANT",
                "DISCUSSANT",
                "WRITER",
                "SITE_ADMIN",
            }
        )
        for role in valid_roles:
            schema = AgentAssignRequest(agent_id=uuid4(), role=role)
            assert schema.role == role

    def test_empty_role_raises(self) -> None:
        """(b) role='' → _validate_role: '' not in _VALID_ROLES → ValidationError."""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        with pytest.raises(ValidationError):
            AgentAssignRequest(agent_id=uuid4(), role="")

    def test_role_too_long_raises(self) -> None:
        """(c) role='x'*51 → max_length=50 or _validate_role → ValidationError."""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        with pytest.raises(ValidationError):
            AgentAssignRequest(agent_id=uuid4(), role="x" * 51)

    def test_invalid_role_value_raises(self) -> None:
        """Jensen 確認要件: assign_agent 無効 role → ValidationError (schema レベル, HTTP 422)."""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        with pytest.raises(ValidationError):
            AgentAssignRequest(agent_id=uuid4(), role="NOT_A_ROLE")

    def test_lowercase_role_raises(self) -> None:
        """小文字 'leader' も _VALID_ROLES 外なので ValidationError."""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        with pytest.raises(ValidationError):
            AgentAssignRequest(agent_id=uuid4(), role="leader")

    def test_extra_field_raises(self) -> None:
        """(d) extra_field='z' → extra='forbid' → ValidationError."""
        from bakufu.interfaces.http.schemas.room import AgentAssignRequest

        with pytest.raises(ValidationError):
            AgentAssignRequest.model_validate(
                {"agent_id": str(uuid4()), "role": "LEADER", "extra_field": "z"}
            )


class TestRoomResponseSchema:
    """TC-UT-RM-HTTP-004: RoomResponse / MemberResponse / RoomListResponse シリアライズ."""

    def _make_mock_membership(self, agent_id: object = None, role: str = "LEADER") -> Any:
        """MemberResponse.model_validate に渡せる AgentMembership 風オブジェクトを返す."""
        from unittest.mock import MagicMock

        m = MagicMock()
        m.agent_id = agent_id if agent_id is not None else uuid4()
        m.role = role
        m.joined_at = datetime.now(UTC)
        return m

    def _make_mock_room(
        self,
        name: str = "Vモデル開発室",
        members: list[Any] | None = None,
        archived: bool = False,
    ) -> Any:
        """RoomResponse._flatten_room が duck-typing で読み取る Room 風オブジェクト."""
        from unittest.mock import MagicMock

        r = MagicMock()
        r.id = uuid4()
        r.name = name
        r.description = ""
        r.workflow_id = uuid4()
        r.members = members if members is not None else []
        r.prompt_kit.prefix_markdown = "テストプロンプト"
        r.archived = archived
        return r

    def test_room_response_id_is_str(self) -> None:
        """model_validate(room) → id が str (UUID 文字列)."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room()
        resp = RoomResponse.model_validate(mock_room)
        assert isinstance(resp.id, str)

    def test_room_response_workflow_id_is_str(self) -> None:
        """workflow_id が str (UUID 文字列)."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room()
        resp = RoomResponse.model_validate(mock_room)
        assert isinstance(resp.workflow_id, str)

    def test_room_response_archived_is_bool(self) -> None:
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room(archived=True)
        resp = RoomResponse.model_validate(mock_room)
        assert resp.archived is True

    def test_room_response_members_is_list(self) -> None:
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room(members=[self._make_mock_membership()])
        resp = RoomResponse.model_validate(mock_room)
        assert isinstance(resp.members, list)
        assert len(resp.members) == 1

    def test_member_response_agent_id_is_str(self) -> None:
        """MemberResponse.agent_id は str (UUID → str 変換)."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        agent_id = uuid4()
        mock_room = self._make_mock_room(members=[self._make_mock_membership(agent_id=agent_id)])
        resp = RoomResponse.model_validate(mock_room)
        assert resp.members[0].agent_id == str(agent_id)

    def test_member_response_role_is_str(self) -> None:
        """MemberResponse.role は str."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room(members=[self._make_mock_membership(role="REVIEWER")])
        resp = RoomResponse.model_validate(mock_room)
        assert resp.members[0].role == "REVIEWER"

    def test_member_response_joined_at_is_iso8601_str(self) -> None:
        """MemberResponse.joined_at は ISO 8601 str (_coerce_joined_at)."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room(members=[self._make_mock_membership()])
        resp = RoomResponse.model_validate(mock_room)
        joined_at = resp.members[0].joined_at
        assert isinstance(joined_at, str)
        assert "T" in joined_at  # ISO 8601 は "T" 区切りを含む

    def test_room_response_prompt_kit_prefix_markdown_flattened(self) -> None:
        """prompt_kit.prefix_markdown が prompt_kit_prefix_markdown にフラット化される."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        mock_room = self._make_mock_room()
        resp = RoomResponse.model_validate(mock_room)
        assert resp.prompt_kit_prefix_markdown == "テストプロンプト"

    def test_room_list_response_total_matches_items_len(self) -> None:
        """RoomListResponse.total が len(items) と一致。"""
        from bakufu.interfaces.http.schemas.room import RoomListResponse, RoomResponse

        rooms = [
            RoomResponse.model_validate(self._make_mock_room(name=f"部屋{i}")) for i in range(3)
        ]
        resp = RoomListResponse(items=rooms, total=len(rooms))
        assert resp.total == 3
        assert len(resp.items) == 3

    def test_room_response_extra_field_raises(self) -> None:
        """extra='forbid': 未知フィールドは ValidationError."""
        from bakufu.interfaces.http.schemas.room import RoomResponse

        with pytest.raises(ValidationError):
            RoomResponse.model_validate(
                {
                    "id": str(uuid4()),
                    "name": "X",
                    "description": "",
                    "workflow_id": str(uuid4()),
                    "members": [],
                    "prompt_kit_prefix_markdown": "",
                    "archived": False,
                    "extra": "z",
                }
            )
