"""Empire アグリゲートルートのユニット + 結合テスト.

``docs/features/empire/test-design.md`` の TC-UT-EM-001〜023 と
TC-IT-EM-001〜002 を網羅する。テストは機能面 (構築、name 境界値、hire、
キャパシティ、archive、pre-validate ロールバック、frozen 契約、MSG 文言、
ライフサイクル統合) ごとに ``Test*`` クラスにグルーピングしている。
各テストの docstring にトレース用アンカー (TC-ID, REQ-ID, 該当する場合は
MSG-ID) を記載する。

統合シナリオは ``integration/`` 配下ではなく本ファイルに置く ──
このアグリゲートは純粋ドメイン (外部 I/O ゼロ) であり、test-design が
意図的に「Aggregate 内部ラウンドトリップ」ケースをここに集約しているため。
"""

from __future__ import annotations

import unicodedata
from uuid import uuid4

import pytest
from bakufu.domain.empire import MAX_AGENTS, MAX_ROOMS, Empire
from bakufu.domain.exceptions import EmpireInvariantViolation
from bakufu.domain.value_objects import AgentRef, Role, RoomRef
from pydantic import ValidationError

from tests.factories.empire import make_agent_ref, make_empire, make_room_ref

# ===========================================================================
# REQ-EM-001 ── 構築 + name 正規化
# ===========================================================================


class TestEmpireConstruction:
    """Empire(id, name) 初期化契約 (TC-UT-EM-001)。"""

    def test_minimal_empire_has_empty_rooms_and_agents(self) -> None:
        """TC-UT-EM-001: 最小構成の Empire(id, name) は rooms=[] / agents=[] を返す。"""
        empire = make_empire(name="山田の幕府")
        assert empire.rooms == [] and empire.agents == []

    def test_construction_preserves_input_name(self) -> None:
        """TC-UT-EM-001: NFC+strip パイプライン後も Empire.name が入力を反映する。"""
        empire = make_empire(name="山田の幕府")
        assert empire.name == "山田の幕府"


class TestEmpireNameBoundaries:
    """Empire.name 長さ契約 (TC-UT-EM-002, MSG-EM-001)。"""

    @pytest.mark.parametrize("valid_length", [1, 80])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-EM-002: 1 文字 / 80 文字の name で構築に成功する。"""
        empire = make_empire(name="a" * valid_length)
        assert len(empire.name) == valid_length

    @pytest.mark.parametrize("invalid_name", ["", "a" * 81, "   "])
    def test_rejects_zero_eightyone_or_whitespace_only(self, invalid_name: str) -> None:
        """TC-UT-EM-002: 0 文字 / 81 文字 / 空白のみの name は例外発火。"""
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            make_empire(name=invalid_name)
        assert excinfo.value.kind == "name_range"


class TestEmpireNameNormalization:
    """NFC + strip パイプライン (TC-UT-EM-003, Confirmation B)。"""

    def test_decomposed_kana_is_normalized_to_nfc(self) -> None:
        """TC-UT-EM-003: 濁点付きの分解仮名が NFC 形へ正規化される。"""
        # 'がが' は実際に分解可能: U+304C → U+304B U+3099 (仮名 + 結合濁点)。
        # 純カタカナの「テスト」には分解形が無く、NFC パイプラインを示せない。
        composed = "がが"
        decomposed = unicodedata.normalize("NFD", composed)
        assert decomposed != composed  # 入力が実際に分解形であることを確認
        empire = make_empire(name=decomposed)
        assert empire.name == composed

    def test_surrounding_whitespace_is_stripped(self) -> None:
        """TC-UT-EM-003: 前後の空白は保存前に strip される。"""
        empire = make_empire(name="  山田の幕府  ")
        assert empire.name == "山田の幕府"


# ===========================================================================
# REQ-EM-002 ── hire_agent
# ===========================================================================


class TestHireAgent:
    """hire_agent 契約 (TC-UT-EM-004 / 005 / 006)。"""

    def test_appends_new_agent_to_list(self) -> None:
        """TC-UT-EM-004: hire_agent は agent を追加した新 Empire を返す。"""
        empire = make_empire()
        agent = make_agent_ref()
        updated = empire.hire_agent(agent)
        assert updated.agents == [agent]

    def test_does_not_mutate_original_aggregate(self) -> None:
        """TC-UT-EM-004: 元 Empire の agents は hire_agent 後も空のまま。"""
        empire = make_empire()
        empire.hire_agent(make_agent_ref())
        assert empire.agents == []

    def test_three_consecutive_distinct_hires_all_persist(self) -> None:
        """TC-UT-EM-005: hire_agent をチェーンすると 3 件の別 agent が全て残る。"""
        empire = make_empire()
        a1, a2, a3 = make_agent_ref(), make_agent_ref(), make_agent_ref()
        final = empire.hire_agent(a1).hire_agent(a2).hire_agent(a3)
        assert {ref.agent_id for ref in final.agents} == {
            a1.agent_id,
            a2.agent_id,
            a3.agent_id,
        }

    def test_rejects_duplicate_agent_id(self) -> None:
        """TC-UT-EM-006: 同一 agent_id の再採用は agent_duplicate を発火する。"""
        empire = make_empire()
        agent = make_agent_ref()
        after_first_hire = empire.hire_agent(agent)
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            duplicate = AgentRef(agent_id=agent.agent_id, name="別名", role=Role.LEADER)
            after_first_hire.hire_agent(duplicate)
        assert excinfo.value.kind == "agent_duplicate"


class TestHireAgentCapacity:
    """hire_agent キャパシティ境界 (TC-UT-EM-007, Confirmation C)。"""

    def test_succeeds_at_max_agents(self) -> None:
        """TC-UT-EM-007: MAX_AGENTS まで hire は成功する。"""
        empire = make_empire()
        for _ in range(MAX_AGENTS):
            empire = empire.hire_agent(make_agent_ref())
        assert len(empire.agents) == MAX_AGENTS

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-EM-007: (MAX_AGENTS+1) 番目の hire は capacity_exceeded を発火する。"""
        empire = make_empire()
        for _ in range(MAX_AGENTS):
            empire = empire.hire_agent(make_agent_ref())
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.hire_agent(make_agent_ref())
        assert excinfo.value.kind == "capacity_exceeded"


# ===========================================================================
# REQ-EM-003 ── establish_room
# ===========================================================================


class TestEstablishRoom:
    """establish_room 契約 (TC-UT-EM-008 / 009)。"""

    def test_appends_new_room_to_list(self) -> None:
        """TC-UT-EM-008: establish_room は room を追加した新 Empire を返す。"""
        empire = make_empire()
        room = make_room_ref()
        updated = empire.establish_room(room)
        assert updated.rooms == [room]

    def test_does_not_mutate_original_aggregate(self) -> None:
        """TC-UT-EM-008: 元 Empire の rooms は establish_room 後も空のまま。"""
        empire = make_empire()
        empire.establish_room(make_room_ref())
        assert empire.rooms == []

    def test_rejects_duplicate_room_id(self) -> None:
        """TC-UT-EM-009: 同一 room_id の再 establish は room_duplicate を発火する。"""
        empire = make_empire()
        room = make_room_ref()
        after_first = empire.establish_room(room)
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            duplicate = RoomRef(room_id=room.room_id, name="別名")
            after_first.establish_room(duplicate)
        assert excinfo.value.kind == "room_duplicate"


class TestEstablishRoomCapacity:
    """establish_room キャパシティ境界 (TC-UT-EM-010, Confirmation C)。"""

    def test_succeeds_at_max_rooms(self) -> None:
        """TC-UT-EM-010: MAX_ROOMS まで establish は成功する。"""
        empire = make_empire()
        for _ in range(MAX_ROOMS):
            empire = empire.establish_room(make_room_ref())
        assert len(empire.rooms) == MAX_ROOMS

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-EM-010: (MAX_ROOMS+1) 番目の establish は capacity_exceeded を発火する。"""
        empire = make_empire()
        for _ in range(MAX_ROOMS):
            empire = empire.establish_room(make_room_ref())
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.establish_room(make_room_ref())
        assert excinfo.value.kind == "capacity_exceeded"


# ===========================================================================
# REQ-EM-004 ── archive_room
# ===========================================================================


class TestArchiveRoom:
    """archive_room 契約 (TC-UT-EM-011 / 012 / 013)。"""

    def test_marks_target_room_as_archived(self) -> None:
        """TC-UT-EM-011: archive_room は対象 RoomRef の archived を True にする。"""
        rooms = [make_room_ref(), make_room_ref(), make_room_ref()]
        empire = make_empire(rooms=rooms)
        target = rooms[1]
        updated = empire.archive_room(target.room_id)
        archived = next(r for r in updated.rooms if r.room_id == target.room_id)
        assert archived.archived is True

    def test_leaves_other_rooms_unchanged(self) -> None:
        """TC-UT-EM-011: 対象以外の room は archived=False のまま維持される。"""
        rooms = [make_room_ref(), make_room_ref(), make_room_ref()]
        empire = make_empire(rooms=rooms)
        target = rooms[1]
        updated = empire.archive_room(target.room_id)
        others = [r for r in updated.rooms if r.room_id != target.room_id]
        assert all(r.archived is False for r in others)

    def test_unknown_room_id_raises_room_not_found(self) -> None:
        """TC-UT-EM-012: 存在しない room_id への archive は room_not_found を発火する。"""
        empire = make_empire(rooms=[make_room_ref()])
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.archive_room(uuid4())
        assert excinfo.value.kind == "room_not_found"

    def test_does_not_physically_delete_target(self) -> None:
        """TC-UT-EM-013: archive_room は rooms 配列長を保つ (論理アーカイブ)。"""
        rooms = [make_room_ref()]
        empire = make_empire(rooms=rooms)
        updated = empire.archive_room(rooms[0].room_id)
        assert len(updated.rooms) == 1


# ===========================================================================
# REQ-EM-005 ── pre-validate ロールバック (Confirmation A)
# ===========================================================================


class TestPreValidateRollback:
    """ミューテーション失敗時、元 Empire は変更されない (TC-UT-EM-014〜016)。"""

    def test_failed_hire_agent_keeps_original_empire(self) -> None:
        """TC-UT-EM-014: hire_agent 失敗は呼び出し側の Empire を変更しない。"""
        agent = make_agent_ref()
        empire = make_empire(agents=[agent])
        with pytest.raises(EmpireInvariantViolation):
            empire.hire_agent(AgentRef(agent_id=agent.agent_id, name="dup", role=Role.LEADER))
        assert empire.agents == [agent]

    def test_failed_establish_room_keeps_original_empire(self) -> None:
        """TC-UT-EM-015: establish_room 失敗は呼び出し側の Empire を変更しない。"""
        room = make_room_ref()
        empire = make_empire(rooms=[room])
        with pytest.raises(EmpireInvariantViolation):
            empire.establish_room(RoomRef(room_id=room.room_id, name="dup"))
        assert empire.rooms == [room]

    def test_failed_archive_room_keeps_archived_flags(self) -> None:
        """TC-UT-EM-016: archive_room 失敗は archived フラグ群を保つ。"""
        room = make_room_ref()
        empire = make_empire(rooms=[room])
        with pytest.raises(EmpireInvariantViolation):
            empire.archive_room(uuid4())
        assert empire.rooms[0].archived is False


# ===========================================================================
# Frozen 契約 + extra='forbid' (REQ-EM-005)
# ===========================================================================


class TestFrozenContract:
    """frozen=True は属性代入を禁ずる (TC-UT-EM-017)。"""

    def test_empire_rejects_attribute_assignment(self) -> None:
        """TC-UT-EM-017: Empire は frozen ── 直接の属性代入は例外発火。"""
        empire = make_empire()
        with pytest.raises(ValidationError):
            empire.name = "改竄"  # type: ignore[misc]

    def test_room_ref_rejects_attribute_assignment(self) -> None:
        """TC-UT-EM-017: RoomRef は frozen ── 直接の属性代入は例外発火。"""
        ref = make_room_ref()
        with pytest.raises(ValidationError):
            ref.archived = True  # type: ignore[misc]

    def test_agent_ref_rejects_attribute_assignment(self) -> None:
        """TC-UT-EM-017: AgentRef は frozen ── 直接の属性代入は例外発火。"""
        ref = make_agent_ref()
        with pytest.raises(ValidationError):
            ref.role = Role.LEADER  # type: ignore[misc]


class TestExtraForbid:
    """extra='forbid' は未知フィールドを拒絶する (TC-UT-EM-018)。"""

    def test_model_validate_rejects_unknown_field(self) -> None:
        """TC-UT-EM-018: extra='forbid' は構築時に未知フィールドを拒絶する。"""
        payload: dict[str, object] = {
            "id": str(uuid4()),
            "name": "ok",
            "rooms": [],
            "agents": [],
            "unknown_field": "should-be-rejected",
        }
        with pytest.raises(ValidationError):
            Empire.model_validate(payload)


# ===========================================================================
# MSG-EM-001〜005 ── 文言の厳密一致アサート
# ===========================================================================


class TestMessageWording:
    """メッセージ文字列が detailed-design §MSG と完全一致する (TC-UT-EM-019〜023)。"""

    def test_msg_em_001_for_oversized_name(self) -> None:
        """TC-UT-EM-019: MSG-EM-001 文言が '[FAIL] Empire name ...' に一致する。"""
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            make_empire(name="a" * 81)
        assert excinfo.value.message == "[FAIL] Empire name must be 1-80 characters (got 81)"

    def test_msg_em_001_for_whitespace_only_reports_post_strip_length(self) -> None:
        """TC-UT-EM-019: NFC+strip パイプラインは空白のみ入力で長さ 0 を報告する。"""
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            make_empire(name="   ")
        assert excinfo.value.message == "[FAIL] Empire name must be 1-80 characters (got 0)"

    def test_msg_em_002_includes_duplicate_agent_id(self) -> None:
        """TC-UT-EM-020: MSG-EM-002 文言は重複 agent_id を含む。"""
        agent = make_agent_ref()
        empire = make_empire(agents=[agent])
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.hire_agent(AgentRef(agent_id=agent.agent_id, name="x", role=Role.LEADER))
        assert excinfo.value.message == f"[FAIL] Agent already hired: agent_id={agent.agent_id}"

    def test_msg_em_003_includes_duplicate_room_id(self) -> None:
        """TC-UT-EM-021: MSG-EM-003 文言は重複 room_id を含む。"""
        room = make_room_ref()
        empire = make_empire(rooms=[room])
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.establish_room(RoomRef(room_id=room.room_id, name="x"))
        assert excinfo.value.message == f"[FAIL] Room already established: room_id={room.room_id}"

    def test_msg_em_004_includes_missing_room_id(self) -> None:
        """TC-UT-EM-022: MSG-EM-004 文言は欠落した room_id を含む。"""
        empire = make_empire()
        unknown = uuid4()
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.archive_room(unknown)
        assert excinfo.value.message == f"[FAIL] Room not found in Empire: room_id={unknown}"

    def test_msg_em_005_uses_invariant_violation_prefix(self) -> None:
        """TC-UT-EM-023: MSG-EM-005 は '[FAIL] Empire invariant violation:' で始まる。"""
        empire = make_empire()
        for _ in range(MAX_AGENTS):
            empire = empire.hire_agent(make_agent_ref())
        with pytest.raises(EmpireInvariantViolation) as excinfo:
            empire.hire_agent(make_agent_ref())
        assert excinfo.value.message.startswith("[FAIL] Empire invariant violation:")


# ===========================================================================
# 統合シナリオ ── Aggregate 内部のラウンドトリップ (TC-IT-EM-001 / 002)
# ===========================================================================


class TestEmpireLifecycleIntegration:
    """Aggregate 内部のラウンドトリップと耐性 (TC-IT-EM-001 / 002)。"""

    def test_full_lifecycle_hire_establish_archive_round_trip(self) -> None:
        """TC-IT-EM-001: Empire→hire→establish→archive で期待される最終状態に達する。"""
        empire = make_empire()
        agent = make_agent_ref()
        room = make_room_ref()
        after_hire = empire.hire_agent(agent)
        after_establish = after_hire.establish_room(room)
        after_archive = after_establish.archive_room(room.room_id)
        final_room = after_archive.rooms[0]
        assert (
            len(after_archive.agents) == 1
            and len(after_archive.rooms) == 1
            and final_room.archived is True
        )

    def test_full_lifecycle_keeps_intermediates_immutable(self) -> None:
        """TC-IT-EM-001: チェーン中の各中間 Empire は変更されないまま維持される。"""
        empire = make_empire()
        after_hire = empire.hire_agent(make_agent_ref())
        after_hire.establish_room(make_room_ref())  # 戻り値を破棄
        assert empire.agents == [] and empire.rooms == [] and len(after_hire.rooms) == 0

    def test_failed_hire_does_not_block_subsequent_operations(self) -> None:
        """TC-IT-EM-002: hire_agent 失敗後でも Empire は後続変更を受け付ける。"""
        agent = make_agent_ref()
        empire = make_empire(agents=[agent])

        # 1) 重複 hire は失敗するが、元 Empire は無傷。
        with pytest.raises(EmpireInvariantViolation):
            empire.hire_agent(AgentRef(agent_id=agent.agent_id, name="x", role=Role.LEADER))

        # 2) 続けて establish_room が無傷の aggregate に対して成功する。
        new_room = make_room_ref()
        after_establish = empire.establish_room(new_room)

        # 3) 続けて archive_room がさらに変更された aggregate に対して成功する。
        after_archive = after_establish.archive_room(new_room.room_id)
        final_room = after_archive.rooms[0]
        assert (
            len(empire.agents) == 1
            and len(after_establish.rooms) == 1
            and final_room.archived is True
        )
