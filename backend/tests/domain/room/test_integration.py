"""Room + PromptKit + AgentMembership + Exception 全体のラウンド
トリップシナリオ (TC-IT-RM-001 / 002)。

room 機能は domain のみで外部 I/O なし。ここで「integration」は
*aggregate 内モジュール統合* を意味する： 非空メンバーリストをまたぐ
チェーン動作。元の Room は各ステップで変更されずに観察される
(frozen + pre-validate rebuild, Confirmation A)。

これらのテストは意図的に production constructors / behaviors を直接組み合わせる —
mocks なし、test-only back doors なし — 記載された受け入れ基準
1, 4, 7, 10, 11 を単一シーケンスで実行。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.value_objects import Role

from tests.factories.room import (
    make_agent_membership,
    make_leader_membership,
    make_prompt_kit,
    make_room,
)


class TestRoomLifecycleRoundTrip:
    """TC-IT-RM-001: 全 behaviors を通した Room ライフサイクル完全実行。"""

    def test_full_lifecycle_preserves_immutability(self) -> None:
        """TC-IT-RM-001: add → add → update → remove → archive シーケンス。"""
        # Step 1: 空の Room。
        room0 = make_room(members=[])
        assert room0.members == []
        assert room0.archived is False

        # Step 2: leader を追加。
        leader = make_leader_membership(agent_id=uuid4())
        room1 = room0.add_member(leader)
        assert len(room1.members) == 1

        # Step 3: developer を追加。
        developer = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        room2 = room1.add_member(developer)
        assert len(room2.members) == 2

        # Step 4: PromptKit を置換。
        new_kit = make_prompt_kit(prefix_markdown="# V-Model Room policy\n\nbe rigorous")
        room3 = room2.update_prompt_kit(new_kit)
        assert "V-Model Room policy" in room3.prompt_kit.prefix_markdown

        # Step 5: developer を削除。
        room4 = room3.remove_member(developer.agent_id, developer.role)
        assert len(room4.members) == 1
        assert room4.members[0].agent_id == leader.agent_id

        # Step 6: archive。
        room5 = room4.archive()
        assert room5.archived is True

        # Frozen contract: 各 earlier Room はステップを超えて変更されない。
        assert room0.members == []
        assert len(room1.members) == 1
        assert len(room2.members) == 2
        assert "V-Model Room policy" not in room2.prompt_kit.prefix_markdown
        assert room4.archived is False


class TestAddMemberFailureThenSuccess:
    """TC-IT-RM-002: add_member は duplicate で失敗、別ペアで成功。"""

    def test_failure_does_not_block_subsequent_success(self) -> None:
        """TC-IT-RM-002: pre-validate isolation は次の add をきれいに進ませる。"""
        leader = make_leader_membership(agent_id=uuid4())
        room = make_room(members=[leader])

        # First call: duplicate ペアは失敗。
        with pytest.raises(RoomInvariantViolation) as excinfo:
            room.add_member(make_leader_membership(agent_id=leader.agent_id))
        assert excinfo.value.kind == "member_duplicate"

        # 元の Room は変更されない。
        assert len(room.members) == 1

        # Second call: 異なるペアは成功。
        new_developer = make_agent_membership(agent_id=uuid4(), role=Role.DEVELOPER)
        new_room = room.add_member(new_developer)
        assert len(new_room.members) == 2
        # ペア set は予想通り。
        pairs = {(m.agent_id, m.role) for m in new_room.members}
        assert (leader.agent_id, Role.LEADER) in pairs
        assert (new_developer.agent_id, Role.DEVELOPER) in pairs
