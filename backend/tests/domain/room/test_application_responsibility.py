"""アプリケーション層責任境界テスト (TC-UT-RM-027〜030)。

Room §確定 R1-A / R1-D / R1-E は **Aggregate 内部不変は構造のみ**:
``(agent_id, role)`` 一意性、容量、アーカイブ終端、名前長、説明長。
Cross-aggregate 関心事 — ``name`` Empire スコープ一意性、
``workflow_id`` 参照整合性、``LEADER`` 必須 by Workflow、
Agent 存在 — は外部知識を要求するため ``RoomService`` /
``EmpireService`` に存在。これらテストはその境界を fix し
将来のリファクタリングが集約レベルチェックを Room 集約に
静かにプッシュできないようにする (Norman PR #16 / Steve PR #16
エージェント機能用のクリーン保持に努力)。
"""

from __future__ import annotations

from uuid import uuid4

from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_room,
)


class TestNameUniquenessNotEnforcedByAggregate:
    """TC-UT-RM-027: Aggregate は同じ名前で 2 つの Room を構築。"""

    def test_two_rooms_with_same_name_both_construct(self) -> None:
        """TC-UT-RM-027: Empire スコープ名一意性は RoomService 責任。

        Aggregate は Repository ハンドルを持たないため、
        **ローカル** 不変のみを強制できる。Empire スコープ一意性は
        ``RoomService.create()`` の Repository SELECT パターン。
        """
        room_a = make_room(name="Vモデル開発室", room_id=uuid4())
        room_b = make_room(name="Vモデル開発室", room_id=uuid4())
        assert room_a.name == room_b.name
        assert room_a.id != room_b.id


class TestWorkflowReferentialIntegrityNotEnforcedByAggregate:
    """TC-UT-RM-028: 集約レベルで任意の UUID が workflow_id として受け入れられる。"""

    def test_arbitrary_workflow_id_constructs(self) -> None:
        """TC-UT-RM-028: Workflow 存在は Room ではなく RoomService で検証。"""
        # UUID は任意 — このID を持つ Workflow は存在しない。
        # 参照整合性はアプリケーション層スコープのため Aggregate は受け入れ。
        room = make_room(workflow_id=uuid4())
        assert room.workflow_id is not None


class TestLeaderRequirementNotEnforcedByAggregate:
    """TC-UT-RM-029: LEADER ロールメンバーなし Room は構築 (チャットルームシナリオ)。"""

    def test_room_without_leader_constructs(self) -> None:
        """TC-UT-RM-029: LEADER 必須 by Workflow は RoomService 責任。

        一部 Workflow (カジュアルチャットまたはディスカッション専用フロー等)
        は LEADER を要求しない。Aggregate は Repository なしで
        Workflow.required_role を読めないため チェック全体をスキップ。
        Agent §確定 I が ``provider_kind`` MVP ゲートに使用する同じパターン。
        """
        room = make_room(members=[])
        assert all(m.role != Role.LEADER for m in room.members)


class TestAgentExistenceNotEnforcedByAggregate:
    """TC-UT-RM-030: AgentMembership は任意の UUID を agent_id として受け入れ。"""

    def test_room_with_unknown_agent_id_constructs(self) -> None:
        """TC-UT-RM-030: Agent 存在は RoomService.add_member() で検証。

        Aggregate レベルでは ``agent_id`` はタイプ化された UUID スロット。
        それが実際の Agent 行に解決するかは Repository 関心事、
        Aggregate が観察できる不変ではない。
        """
        unknown_agent_id = uuid4()
        m = make_agent_membership(agent_id=unknown_agent_id, role=Role.DEVELOPER)
        room = make_room(members=[m])
        assert room.members[0].agent_id == unknown_agent_id
