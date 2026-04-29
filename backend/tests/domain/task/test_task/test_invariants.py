"""Task invariant + MSG + auto-mask テスト.

TC-UT-TS-009 / 010 / 011 / 041 / 042 / 043 / 046〜052 ── 5 つの
``_validate_*`` ヘルパ、§確定 I の auto-mask、§確定 K
「Aggregate はアプリケーション層の不変条件を強制しない」境界、
および §確定 J / room §確定 I 踏襲の **Next: ヒント物理保証**
を MSG-TS-001〜007 全 7 メッセージに対して検証する。

``docs/features/task/test-design.md`` 準拠。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.aggregate_validators import (
    MAX_ASSIGNED_AGENTS,
    MAX_LAST_ERROR_LENGTH,
    _validate_assigned_agents_capacity,  # pyright: ignore[reportPrivateUsage]
    _validate_assigned_agents_unique,  # pyright: ignore[reportPrivateUsage]
    _validate_blocked_has_last_error,  # pyright: ignore[reportPrivateUsage]
    _validate_last_error_consistency,  # pyright: ignore[reportPrivateUsage]
    _validate_timestamp_order,  # pyright: ignore[reportPrivateUsage]
)
from bakufu.domain.value_objects import TaskStatus

from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# TC-UT-TS-009: assigned_agents_unique
# ---------------------------------------------------------------------------
class TestAssignedAgentsUnique:
    """TC-UT-TS-009: 重複 agent_id は assigned_agents_unique (MSG-TS-003) を発火。"""

    def test_duplicate_agents_raise(self) -> None:
        """同一 AgentId が 2 つ含まれる → MSG-TS-003。"""
        agent_a = uuid4()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_unique([agent_a, uuid4(), agent_a])
        assert exc_info.value.kind == "assigned_agents_unique"
        # detail に重複 (sorted str list) が現れる。
        assert "duplicates" in exc_info.value.detail
        assert str(agent_a) in str(exc_info.value.detail["duplicates"])

    def test_unique_list_passes(self) -> None:
        """重複なしリストは例外を出さずに通る。"""
        # 直接呼び出しは None を返す (バリデータは違反時のみ raise する副作用関数)。
        _validate_assigned_agents_unique([uuid4(), uuid4(), uuid4()])

    def test_via_aggregate_construction_raises(self) -> None:
        """重複 agent を持つ Task を構築するとモデルバリデータ経由で例外発火。"""
        agent_a = uuid4()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            make_in_progress_task(assigned_agent_ids=[agent_a, agent_a])
        assert exc_info.value.kind == "assigned_agents_unique"


# ---------------------------------------------------------------------------
# TC-UT-TS-041: assigned_agents_capacity (MAX = 5)
# ---------------------------------------------------------------------------
class TestAssignedAgentsCapacity:
    """TC-UT-TS-041: ``len > MAX_ASSIGNED_AGENTS`` で例外発火 (MSG-TS-004)。"""

    def test_six_agents_raises(self) -> None:
        """ユニークな 6 件はキャップ 5 を超えるため例外発火。"""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_capacity([uuid4() for _ in range(6)])
        assert exc_info.value.kind == "assigned_agents_capacity"
        assert exc_info.value.detail.get("max") == MAX_ASSIGNED_AGENTS

    def test_five_agents_passes(self) -> None:
        """キャップちょうどのリスト (5 件) は受理される。"""
        _validate_assigned_agents_capacity([uuid4() for _ in range(5)])


# ---------------------------------------------------------------------------
# TC-UT-TS-010: last_error_consistency
# ---------------------------------------------------------------------------
class TestLastErrorConsistency:
    """TC-UT-TS-010: status==BLOCKED と last_error 非空が同値 (MSG-TS-005)。"""

    def test_in_progress_with_last_error_raises(self) -> None:
        """status=IN_PROGRESS + last_error='something' → MSG-TS-005。"""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_last_error_consistency(TaskStatus.IN_PROGRESS, "leftover error")
        assert exc_info.value.kind == "last_error_consistency"

    def test_blocked_with_none_last_error_raises(self) -> None:
        """status=BLOCKED + last_error=None → MSG-TS-005。"""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_last_error_consistency(TaskStatus.BLOCKED, None)
        assert exc_info.value.kind == "last_error_consistency"

    def test_blocked_with_non_empty_last_error_passes(self) -> None:
        """正当な組み合わせ ── BLOCKED + 非空文字列 ── は受理される。"""
        _validate_last_error_consistency(TaskStatus.BLOCKED, "AuthExpired")

    def test_done_with_none_last_error_passes(self) -> None:
        """終端ステータス + last_error=None は正当な終端形。"""
        _validate_last_error_consistency(TaskStatus.DONE, None)


# ---------------------------------------------------------------------------
# TC-UT-TS-051 (also): blocked_requires_last_error 長さチェック
# ---------------------------------------------------------------------------
class TestBlockedRequiresLastError:
    """TC-UT-TS-051: BLOCKED + 0 長 last_error は例外発火 (MSG-TS-006)。

    ``last_error_consistency`` とは別 ── status==BLOCKED で
    last_error が None / 空文字列の場合、構造の不一致は *consistency*
    チェックが先に検出する。本バリデータは consistency 充足下で
    NFC 正規化長が [1, 10000] 範囲に収まることを確認する。
    """

    def test_blocked_with_too_long_last_error_raises(self) -> None:
        """10001 文字の last_error は MAX_LAST_ERROR_LENGTH を超える。"""
        too_long = "x" * (MAX_LAST_ERROR_LENGTH + 1)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_blocked_has_last_error(TaskStatus.BLOCKED, too_long)
        assert exc_info.value.kind == "blocked_requires_last_error"

    def test_non_blocked_status_short_circuits(self) -> None:
        """BLOCKED 以外のステータスは長さチェックをスキップする。"""
        _validate_blocked_has_last_error(TaskStatus.IN_PROGRESS, None)
        _validate_blocked_has_last_error(TaskStatus.DONE, None)


# ---------------------------------------------------------------------------
# TC-UT-TS-052: timestamp_order
# ---------------------------------------------------------------------------
class TestTimestampOrder:
    """TC-UT-TS-052: created_at > updated_at で例外発火 (MSG-TS-007)。"""

    def test_created_after_updated_raises(self) -> None:
        """バリデータは MSG-TS-007 を発し、detail に ISO タイムスタンプを含める。"""
        ts_old = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        ts_new = ts_old - timedelta(seconds=1)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_timestamp_order(ts_old, ts_new)
        assert exc_info.value.kind == "timestamp_order"
        # detail に法定証跡のため ISO タイムスタンプが現れる。
        assert "created_at" in exc_info.value.detail
        assert "updated_at" in exc_info.value.detail


# ---------------------------------------------------------------------------
# TC-UT-TS-011: TaskInvariantViolation auto-mask (§確定 I)
# ---------------------------------------------------------------------------
class TestExceptionAutoMasksDiscordWebhooks:
    """TC-UT-TS-011: ``last_error`` 内の webhook URL が例外でマスクされる。

    BLOCKED 状態の last_error に webhook URL を含む Task を構築し、
    不整合状態の構築によって invariant を発火させる。例外の
    ``str(exc)`` と ``exc.detail`` の双方で、トークンが
    ``<REDACTED:DISCORD_WEBHOOK>`` に置換されていなければならない。
    """

    _SECRET = "https://discord.com/api/webhooks/123456789012345678/CataclysmicSecret-token"
    _REDACT_SENTINEL = "<REDACTED:DISCORD_WEBHOOK>"
    _RAW_TOKEN = "CataclysmicSecret-token"

    def test_webhook_token_redacted_in_message(self) -> None:
        """str(exc) は生トークンを漏らさず、sentinel が現れる。"""
        # consistency 違反経路で webhook URL を渡す。
        # status=IN_PROGRESS + 非空 last_error => MSG-TS-005 で
        # メッセージにフィールド値が含まれる。
        with pytest.raises(TaskInvariantViolation) as exc_info:
            make_in_progress_task(
                last_error=self._SECRET,
                # 実際の MSG は consistency に対して "non-empty" を反復するが、
                # 例外の __init__ は detail の各値に対して事前に auto-mask を
                # 走らせる。IN_PROGRESS Task を非空 last_error で構築すると
                # invariant を発火できる。
            )
        assert self._RAW_TOKEN not in str(exc_info.value), (
            "[FAIL] Raw Discord webhook token leaked into exception message.\n"
            "Next: TaskInvariantViolation.__init__ must apply mask_discord_webhook "
            "to message + mask_discord_webhook_in to detail per §確定 I."
        )

    def test_webhook_token_redacted_in_detail(self) -> None:
        """exc.detail の値が再帰的にマスクされる。

        secret を ``last_error`` に入れ、状態不整合な構築へ遷移して
        違反を発火させる。detail dict の形状はバリデータごとに
        異なるため、いずれの detail 値も生トークンを保持しないことを
        アサートする。
        """
        # blocked_requires_last_error を発火させるには、
        # status=BLOCKED + last_error=secret + 過大長による長さチェック
        # 越えで構築する手もあるが、_validate_blocked_has_last_error を
        # 直接呼び出して secret をメッセージ持ち値として渡す方が容易。
        # ここでは特定バリデータへの結合を避けるため、例外を直接構築する ──
        # §確定 I の契約は TaskInvariantViolation.__init__ にあり、
        # 個別バリデータには無い。
        exc = TaskInvariantViolation(
            kind="blocked_requires_last_error",
            message=f"[FAIL] secret in message: {self._SECRET}\nNext: re-input webhook.",
            detail={
                "last_error_value": self._SECRET,
                "nested": {"target": self._SECRET},
                "as_list": [self._SECRET, "ok"],
            },
        )

        # メッセージ: トークン消滅、sentinel 出現。
        assert self._RAW_TOKEN not in exc.message
        assert self._REDACT_SENTINEL in exc.message
        # detail: 全ての値が再帰的にマスクされる。
        flat = repr(exc.detail)
        assert self._RAW_TOKEN not in flat, (
            f"[FAIL] Raw token leaked into detail: {flat!r}\n"
            f"Next: ensure mask_discord_webhook_in handles dict/list/tuple recursion."
        )
        assert self._REDACT_SENTINEL in flat


# ---------------------------------------------------------------------------
# §確定 G + K: Aggregate 層はアプリケーション不変条件を強制しない
# ---------------------------------------------------------------------------
class TestAggregateDoesNotEnforceApplicationInvariants:
    """TC-UT-TS-042 / 043: Aggregate は跨り Aggregate 参照を検証しない。"""

    def test_commit_deliverable_does_not_check_by_agent_id_membership(self) -> None:
        """TC-UT-TS-042: ``by_agent_id`` は ``assigned_agent_ids`` に含まれなくてよい。

        §確定 G: そのメンバーシップ確認はアプリケーションサービスの
        責務。assigned 集合に含まれない agent を渡しても、
        Aggregate レベルでは成功するはず。
        """
        task = make_in_progress_task(assigned_agent_ids=[uuid4()])
        outsider_agent = uuid4()
        # 確認: outsider は assigned 集合に含まれていない。
        assert outsider_agent not in task.assigned_agent_ids

        d = make_deliverable(stage_id=task.current_stage_id)
        out = task.commit_deliverable(
            stage_id=task.current_stage_id,
            deliverable=d,
            by_agent_id=outsider_agent,
            updated_at=task.updated_at + timedelta(seconds=1),
        )
        assert out.deliverables[task.current_stage_id] == d

    def test_arbitrary_room_id_and_directive_id_accepted(self) -> None:
        """TC-UT-TS-043: 跨り Aggregate 参照のランダム ID でも問題なく構築できる。

        Aggregate は VO 型 ID を保持するだけで、参照先の行が
        存在するかは検証しない (§確定 K)。Repository / TaskService が
        ハイドレート / 構築時に存在性を確認する。Aggregate の責務は
        **自身**の状態整合性に閉じる。
        """
        # ランダム ID ── テストフィクスチャや DB 上にも存在しない値。
        # Aggregate は受理する。
        task = make_task(
            room_id=uuid4(),
            directive_id=uuid4(),
            current_stage_id=uuid4(),
        )
        # 構築成功。参照整合性チェックは発火しない。
        assert task.room_id is not None
        assert task.directive_id is not None
        assert task.current_stage_id is not None


# ---------------------------------------------------------------------------
# TC-UT-TS-046〜052: 2 行 MSG + Next: ヒント物理保証 (§確定 J)
# ---------------------------------------------------------------------------
class TestNextHintPhysicalGuarantee:
    """``TaskViolationKind`` の全 7 値で ``str(exc)`` に 'Next:' が含まれる。

    room §確定 I 踏襲の契約: あらゆるエラーメッセージは 2 行構造
    (``[FAIL] <fact>\\nNext: <action>``) を持つ。``"Next:" in str(exc)``
    のアサートが落ちる場合、開発者が 1 行 MSG を書いて運用者向け
    フィードバック契約を破った証拠となる。

    各 kind は自然なコード経路で発火させる (例外を直接構築しない) ──
    実際に出力される文字列に対してアサートできるようにするため。
    """

    def test_terminal_violation_carries_next_hint(self) -> None:
        """TC-UT-TS-046: MSG-TS-001 (terminal_violation)。"""
        from tests.factories.task import make_done_task

        task = make_done_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.assign([uuid4()], updated_at=task.updated_at + timedelta(seconds=1))
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "DONE/CANCELLED" in s  # ヒントの部分文字列

    def test_state_transition_invalid_carries_next_hint(self) -> None:
        """TC-UT-TS-047: MSG-TS-002 (state_transition_invalid)。"""
        task = make_task()  # PENDING
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.commit_deliverable(
                stage_id=task.current_stage_id,
                deliverable=make_deliverable(),
                by_agent_id=uuid4(),
                updated_at=task.updated_at + timedelta(seconds=1),
            )
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "state_machine.py" in s

    def test_assigned_agents_unique_carries_next_hint(self) -> None:
        """TC-UT-TS-048: MSG-TS-003 (assigned_agents_unique)。"""
        agent = uuid4()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_unique([agent, agent])
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Deduplicate" in s

    def test_assigned_agents_capacity_carries_next_hint(self) -> None:
        """TC-UT-TS-049: MSG-TS-004 (assigned_agents_capacity)。"""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_assigned_agents_capacity([uuid4() for _ in range(6)])
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "split work" in s

    def test_last_error_consistency_carries_next_hint(self) -> None:
        """TC-UT-TS-050: MSG-TS-005 (last_error_consistency)。"""
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_last_error_consistency(TaskStatus.IN_PROGRESS, "oops")
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Repository row integrity" in s

    def test_blocked_requires_last_error_carries_next_hint(self) -> None:
        """TC-UT-TS-051: MSG-TS-006 (blocked_requires_last_error)。

        status=BLOCKED + 空 last_error の直接呼び出し。
        上位の ``Task.block(..., last_error='')`` 経路では
        rebuild 時のモデルバリデータが発火する ── 同じ kind、
        同じヒント。
        """
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_blocked_has_last_error(TaskStatus.BLOCKED, "")
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "1-10000" in s

    def test_timestamp_order_carries_next_hint(self) -> None:
        """TC-UT-TS-052: MSG-TS-007 (timestamp_order)。"""
        ts_old = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        ts_new = ts_old - timedelta(seconds=1)
        with pytest.raises(TaskInvariantViolation) as exc_info:
            _validate_timestamp_order(ts_old, ts_new)
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "updated_at must be" in s


# ---------------------------------------------------------------------------
# Smoke: 生 last_error を持つ BLOCKED Task は secret を保持する
# ---------------------------------------------------------------------------
class TestAggregateKeepsRawLastError:
    """Aggregate は ``last_error`` を生のまま保存する ── masking は Repository 側。

    設計分離の再確認: ``MaskedText`` は ``feature/task-repository`` の
    ``tasks.last_error`` カラムデコレータ。インメモリの Task インスタンスは
    値を事前マスクしてはならない ── さもないと Aggregate が
    法定証跡情報を黙って失う。
    """

    def test_in_memory_task_keeps_secret(self) -> None:
        """``make_blocked_task(last_error=secret)`` はインメモリで生 secret を保持する。"""
        secret = (
            "AuthExpired: https://discord.com/api/webhooks/111122223333444455/RawTokenInMemory-only"
        )
        task = make_blocked_task(last_error=secret)
        assert task.last_error == secret
