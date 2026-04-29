"""ExternalReviewGate invariant + auto-mask + Next: ヒントテスト.

TC-UT-GT-007 / 008 / 009 / 010 / 011 / 021〜025 ── 5 つの ``_validate_*``
ヘルパ (4 つは model_validator で使用 + 1 つはセーフティネット)、
§確定 H の webhook auto-mask、§確定 J / room §確定 I 踏襲の
**Next: ヒント物理保証** を MSG-GT-001〜005 全 5 メッセージに対して検証する。

§確定 C の **audit_trail append-only** 契約は最も重大度が高い ──
4 つの改ざんパターン (既存編集 / 先頭挿入 / 削除 / 並び替え) いずれも
``audit_trail_append_only`` を発火しなければならない。§確定 D の
**deliverable_snapshot 三重防御** もここでバリデータセーフティネットとして
動かしている (構造的ガード ── _rebuild_with_state が snapshot 引数を
受け付けないこと ── は test_state_machine の "失敗 approve は snapshot を
変えない" で検証される)。
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.aggregate_validators import (
    MAX_FEEDBACK_LENGTH,
    _validate_audit_trail_append_only,  # pyright: ignore[reportPrivateUsage]
    _validate_decided_at_consistency,  # pyright: ignore[reportPrivateUsage]
    _validate_feedback_text_range,  # pyright: ignore[reportPrivateUsage]
    _validate_snapshot_immutable,  # pyright: ignore[reportPrivateUsage]
)
from bakufu.domain.value_objects import (
    AuditAction,
    ReviewDecision,
)

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_audit_entry,
    make_gate,
)
from tests.factories.task import make_deliverable


# ---------------------------------------------------------------------------
# TC-UT-GT-007: decided_at consistency
# ---------------------------------------------------------------------------
class TestDecidedAtConsistency:
    """TC-UT-GT-007: decision==PENDING ⇔ decided_at が None (MSG-GT-002)。"""

    def test_pending_with_decided_at_raises(self) -> None:
        """PENDING + decided_at が設定済み → 例外発火."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_decided_at_consistency(ReviewDecision.PENDING, datetime.now(UTC))
        assert exc_info.value.kind == "decided_at_inconsistent"

    def test_approved_with_none_decided_at_raises(self) -> None:
        """APPROVED + decided_at が None → 例外発火."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_decided_at_consistency(ReviewDecision.APPROVED, None)
        assert exc_info.value.kind == "decided_at_inconsistent"

    def test_pending_with_none_passes(self) -> None:
        """正当な組み合わせ ── PENDING + None ── は受理される."""
        _validate_decided_at_consistency(ReviewDecision.PENDING, None)

    @pytest.mark.parametrize(
        "decision",
        [ReviewDecision.APPROVED, ReviewDecision.REJECTED, ReviewDecision.CANCELLED],
        ids=lambda d: d.value,
    )
    def test_terminal_with_decided_at_passes(self, decision: ReviewDecision) -> None:
        """terminal な decision + 非 None な decided_at は正当."""
        _validate_decided_at_consistency(decision, datetime.now(UTC))


# ---------------------------------------------------------------------------
# TC-UT-GT-010: feedback_text 長さレンジ
# ---------------------------------------------------------------------------
class TestFeedbackTextRange:
    """TC-UT-GT-010: 0 <= len <= 10000 (MSG-GT-004)。"""

    def test_empty_string_passes(self) -> None:
        """空 feedback（デフォルト）は正当."""
        _validate_feedback_text_range("")

    def test_at_max_length_passes(self) -> None:
        """10000 文字はキャップ上限で受理される."""
        _validate_feedback_text_range("x" * MAX_FEEDBACK_LENGTH)

    def test_over_max_length_raises(self) -> None:
        """10001 文字はキャップ超過."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_feedback_text_range("x" * (MAX_FEEDBACK_LENGTH + 1))
        assert exc_info.value.kind == "feedback_text_range"


# ---------------------------------------------------------------------------
# TC-UT-GT-009: audit_trail append-only ── 4 改ざんパターン
# ---------------------------------------------------------------------------
class TestAuditTrailAppendOnly:
    """TC-UT-GT-009: 4 改ざんパターン（§確定 C inputs/expectations 表）.

    末尾追加だけではない audit_trail の任意の改変は
    audit_trail_append_only を発火する。設計書で列挙される 4 ケース:

    1. **modification**: 既存エントリの内容編集。
    2. **prepend**: 既存より前に新エントリを挿入。
    3. **delete**: 既存エントリの削除。
    4. **reorder**: 既存エントリの並び替え。
    """

    def test_construction_with_no_previous_accepts_any_list(self) -> None:
        """previous=None（構築時）は寛容 ── 初期 trail を固定."""
        # 構築時は None でない任意のリストを受理する。
        _validate_audit_trail_append_only(None, [])
        _validate_audit_trail_append_only(None, [make_audit_entry(action=AuditAction.VIEWED)])

    def test_legal_append_passes(self) -> None:
        """厳密な追加（previous + 新エントリ 1 件）のみが正当な mutation."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1]
        current = [e1, e2]
        _validate_audit_trail_append_only(previous, current)

    # 改ざんパターン 1: modification
    def test_existing_entry_modification_raises(self) -> None:
        """既存エントリの内容編集は拒絶される."""
        e1 = make_audit_entry(action=AuditAction.VIEWED, comment="original")
        previous = [e1]
        # e1 を別エントリ（異なる uuid + comment）に置換。
        # 既存監査エントリの「typo を修正」しようとするケースを表す。
        e1_modified = make_audit_entry(
            action=AuditAction.VIEWED,
            comment="rewritten",
        )
        current = [e1_modified]
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 改ざんパターン 2: prepend
    def test_prepend_raises(self) -> None:
        """先頭への新エントリ挿入は既存をずらす。拒絶される."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        previous = [e1]
        e_prepended = make_audit_entry(action=AuditAction.APPROVED)
        current = [e_prepended, e1]
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 改ざんパターン 3: delete
    def test_delete_raises(self) -> None:
        """既存エントリの削除は trail を縮める。拒絶される."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1, e2]
        current = [e1]  # e2 を削除
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 改ざんパターン 4: reorder
    def test_reorder_raises(self) -> None:
        """既存エントリの並び替えは拒絶される."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1, e2]
        current = [e2, e1]  # 入れ替え
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"

    # 複合: 削除 + 追加（先頭が破壊されているため依然違法）
    def test_delete_then_append_raises(self) -> None:
        """既存エントリ削除と新エントリ追加の組み合わせも違法."""
        e1 = make_audit_entry(action=AuditAction.VIEWED)
        e2 = make_audit_entry(action=AuditAction.APPROVED)
        previous = [e1, e2]
        e_new = make_audit_entry(action=AuditAction.VIEWED)
        current = [e1, e_new]  # e2 削除、e_new 追加（長さ一致でも違法）
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only(previous, current)
        assert exc_info.value.kind == "audit_trail_append_only"


# ---------------------------------------------------------------------------
# TC-UT-GT-008: deliverable_snapshot 不変性バリデータ (§確定 D セーフティネット)
# ---------------------------------------------------------------------------
class TestSnapshotImmutableValidator:
    """TC-UT-GT-008: §確定 D snapshot 不変性のバリデータセーフティネット.

    構造的ガードは _rebuild_with_state の引数集合に
    deliverable_snapshot が無いこと。本バリデータはその契約が漏れた
    場合の失敗経路セーフティネット。ここでは直接テストする。
    """

    def test_construction_with_no_previous_accepts_any_snapshot(self) -> None:
        """previous=None は寛容 ── 初期 snapshot を固定."""
        _validate_snapshot_immutable(None, make_deliverable())

    def test_same_snapshot_passes(self) -> None:
        """同値 snapshot はラウンドトリップに耐える（Pydantic frozen の
        ==）."""
        d = make_deliverable()
        # 同じインスタンスを再利用。Pydantic frozen モデルは値で比較
        _validate_snapshot_immutable(d, d)

    def test_different_snapshot_raises(self) -> None:
        """rebuild 時に別 snapshot を渡すと snapshot_immutable を発火."""
        d1 = make_deliverable(body_markdown="original")
        d2 = make_deliverable(body_markdown="replaced")
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_snapshot_immutable(d1, d2)
        assert exc_info.value.kind == "snapshot_immutable"


# ---------------------------------------------------------------------------
# §確定 D 三重防御の挙動確認
# ---------------------------------------------------------------------------
class TestSnapshotImmutableViaBehaviors:
    """§確定 D: 4 つの behavior メソッド全てが
    deliverable_snapshot をバイト等価に保つ.

    これは **構造的保証** テスト。1 つの Gate に対して 4 メソッドを歩き、
    snapshot フィールドが事後にバイト等価であることを確認。バリデータが
    任意の漏洩を検出する一方で、各メソッドを独立にテストすることで、
    リファクタリング中にあるメソッドが誤って snapshot kwarg を受け付ける
    ケースを捕える。
    """

    def test_approve_preserves_snapshot(self) -> None:
        """approve は deliverable_snapshot をバイト等価に保つ."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.approve(uuid4(), "ok", decided_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot

    def test_reject_preserves_snapshot(self) -> None:
        """reject は deliverable_snapshot をバイト等価に保つ."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.reject(uuid4(), "rev", decided_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot

    def test_cancel_preserves_snapshot(self) -> None:
        """cancel は deliverable_snapshot をバイト等価に保つ."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.cancel(uuid4(), "withdrawn", decided_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot

    def test_record_view_preserves_snapshot(self) -> None:
        """record_view は deliverable_snapshot をバイト等価に保つ."""
        gate = make_gate(deliverable_snapshot=make_deliverable(body_markdown="locked"))
        snapshot = gate.deliverable_snapshot
        out = gate.record_view(uuid4(), viewed_at=datetime.now(UTC))
        assert out.deliverable_snapshot == snapshot


# ---------------------------------------------------------------------------
# TC-UT-GT-011: ExternalReviewGateInvariantViolation auto-mask (§確定 H)
# ---------------------------------------------------------------------------
class TestExceptionAutoMasksDiscordWebhooks:
    """TC-UT-GT-011: feedback / detail 内の webhook URL が構築時に
    masking される.

    §確定 H の契約は ExternalReviewGateInvariantViolation.__init__。
    auto-mask は kind や detail 形状に依らず常時発動。特定バリデータには
    依存しない。secret を含むペイロードで例外を直接構築し、message と
    detail（再帰的）の両方で生トークンが redaction sentinel に置換
    されていることをアサート。
    """

    _SECRET = "https://discord.com/api/webhooks/123456789012345678/SneakyToken-xyz"
    _REDACT_SENTINEL = "<REDACTED:DISCORD_WEBHOOK>"
    _RAW_TOKEN = "SneakyToken-xyz"

    def test_webhook_redacted_in_message_and_detail(self) -> None:
        """message と再帰的な detail 値の両方で生トークンが消える."""
        exc = ExternalReviewGateInvariantViolation(
            kind="audit_trail_append_only",
            message=f"[FAIL] secret in message: {self._SECRET}\nNext: re-input.",
            detail={
                "feedback_value": self._SECRET,
                "nested": {"target": self._SECRET},
                "as_list": [self._SECRET, "ok"],
            },
        )

        # message: 生トークン消滅、sentinel 出現
        assert self._RAW_TOKEN not in exc.message
        assert self._REDACT_SENTINEL in exc.message
        # detail: 全ネスト値が masking される
        flat = repr(exc.detail)
        assert self._RAW_TOKEN not in flat
        assert self._REDACT_SENTINEL in flat


# ---------------------------------------------------------------------------
# TC-UT-GT-021〜025: 5 つの MSG kind + Next: ヒント物理保証 (§確定 J)
# ---------------------------------------------------------------------------
class TestNextHintPhysicalGuarantee:
    """ExternalReviewGateViolationKind の全 5 値で str(exc) に
    'Next:' が含まれる.

    room §確定 I 踏襲の契約: あらゆるエラーメッセージは 2 行構造
    （[FAIL] <fact>\nNext: <action>）を持つ。"Next:" in str(exc)
    のアサートが落ちる場合、開発者が 1 行 MSG を書いて運用者向け
    フィードバック契約を破った証拠となる。
    """

    def test_decision_already_decided_carries_next_hint(self) -> None:
        """TC-UT-GT-021: MSG-GT-001（decision_already_decided）."""
        gate = make_approved_gate()
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            gate.approve(uuid4(), "double", decided_at=datetime.now(UTC) + timedelta(seconds=1))
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "decided once" in s

    def test_decided_at_inconsistent_carries_next_hint(self) -> None:
        """TC-UT-GT-022: MSG-GT-002（decided_at_inconsistent）."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_decided_at_consistency(ReviewDecision.APPROVED, None)
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Repository row integrity" in s

    def test_snapshot_immutable_carries_next_hint(self) -> None:
        """TC-UT-GT-023: MSG-GT-003（snapshot_immutable）."""
        d1 = make_deliverable(body_markdown="a")
        d2 = make_deliverable(body_markdown="b")
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_snapshot_immutable(d1, d2)
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "frozen at Gate creation" in s

    def test_feedback_text_range_carries_next_hint(self) -> None:
        """TC-UT-GT-024: MSG-GT-004（feedback_text_range）."""
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_feedback_text_range("x" * (MAX_FEEDBACK_LENGTH + 1))
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "Trim" in s

    def test_audit_trail_append_only_carries_next_hint(self) -> None:
        """TC-UT-GT-025: MSG-GT-005（audit_trail_append_only）."""
        e1 = make_audit_entry()
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_audit_trail_append_only([e1], [])  # 削除パターン
        s = str(exc_info.value)
        assert s.startswith("[FAIL]")
        assert "Next:" in s
        assert "append" in s.lower()


# ---------------------------------------------------------------------------
# 複合: 完全ライフサイクルを歩いた Gate は監査チェーンを保つ
# ---------------------------------------------------------------------------
class TestAuditTrailChainIntegrity:
    """完全ライフサイクルを歩いても各既存エントリはバイト等価で残る."""

    def test_lifecycle_preserves_all_previous_entries(self) -> None:
        """record_view x 2 → approve は 2 件の VIEWED エントリを逐字保持."""
        gate = make_gate()
        v1 = uuid4()
        v2 = uuid4()
        ts1 = datetime(2026, 4, 28, 10, 0, 0, tzinfo=UTC)
        ts2 = ts1 + timedelta(hours=1)
        ts3 = ts2 + timedelta(hours=1)

        gate = gate.record_view(v1, viewed_at=ts1)
        gate = gate.record_view(v2, viewed_at=ts2)
        # この時点で監査証跡をスナップショット
        before_approve = copy.copy(gate.audit_trail)
        assert len(before_approve) == 2

        # 承認
        gate = gate.approve(uuid4(), "all good", decided_at=ts3)

        # 既存 2 件はバイト等価（§確定 C 契約）
        # 3 番目のエントリが新たな APPROVED 監査行
        assert gate.audit_trail[:2] == before_approve
        assert gate.audit_trail[2].action == AuditAction.APPROVED
        assert len(gate.audit_trail) == 3
