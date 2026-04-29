"""Task 構築テスト (TC-UT-TS-001 / 002 / 014 / 040 / 044 / 045 / 053)。

``docs/features/task/test-design.md`` §Task 構築 準拠。構築時のデフォルト、
``TaskStatus`` の 6 ケースの再水和、frozen + 構造的等価性、NFC-without-strip
``last_error`` 正規化 (§確定 C)、frozen インスタンスの代入拒否、``extra='forbid'``、
kind enum を経由しないフィールドの type エラークラス (§確定 J) を網羅する。
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.task import Task
from bakufu.domain.value_objects import TaskStatus
from pydantic import ValidationError

from tests.factories.task import (
    is_synthetic,
    make_awaiting_review_task,
    make_blocked_task,
    make_cancelled_task,
    make_done_task,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# TC-UT-TS-001: デフォルト値での構築
# ---------------------------------------------------------------------------
class TestTaskDefaults:
    """TC-UT-TS-001: factory のデフォルト Task は構造的に PENDING かつ空。"""

    def test_default_task_is_pending_with_empty_state(self) -> None:
        """デフォルト: status=PENDING, assigned=[], deliverables={}, last_error=None。"""
        task = make_task()
        assert task.status == TaskStatus.PENDING
        assert task.assigned_agent_ids == []
        assert task.deliverables == {}
        assert task.last_error is None
        assert task.created_at <= task.updated_at

    def test_factory_marks_instance_synthetic(self) -> None:
        """factory の出力は :func:`is_synthetic` に登録される。"""
        task = make_task()
        assert is_synthetic(task)


# ---------------------------------------------------------------------------
# TC-UT-TS-002: 6 種類の TaskStatus すべてへの再水和
# ---------------------------------------------------------------------------
class TestRehydrateAllStatuses:
    """TC-UT-TS-002: 6 種類の TaskStatus 値それぞれが問題なく構築できる。

    Repository の hydration は永続化された任意の status を着地させられねばならない ──
    BLOCKED は ``last_error`` を要し、それ以外の status は
    ``last_error is None`` を要する。
    """

    def test_pending_constructs(self) -> None:
        assert make_task(status=TaskStatus.PENDING).status == TaskStatus.PENDING

    def test_in_progress_constructs(self) -> None:
        assert make_in_progress_task().status == TaskStatus.IN_PROGRESS

    def test_awaiting_external_review_constructs(self) -> None:
        assert make_awaiting_review_task().status == TaskStatus.AWAITING_EXTERNAL_REVIEW

    def test_blocked_requires_last_error(self) -> None:
        task = make_blocked_task(last_error="some failure")
        assert task.status == TaskStatus.BLOCKED
        assert task.last_error == "some failure"

    def test_done_constructs(self) -> None:
        assert make_done_task().status == TaskStatus.DONE

    def test_cancelled_constructs(self) -> None:
        assert make_cancelled_task().status == TaskStatus.CANCELLED


# ---------------------------------------------------------------------------
# TC-UT-TS-014: frozen + 構造的等価性 + ハッシュ
# ---------------------------------------------------------------------------
class TestFrozenStructuralEquality:
    """TC-UT-TS-014: 同じ属性の Task は ``==`` で、ハッシュも同一。"""

    def test_same_attributes_compare_equal(self) -> None:
        """同一属性を持つ 2 つの Task インスタンスは ``==``。"""
        common_id = uuid4()
        common_room = uuid4()
        common_directive = uuid4()
        common_stage = uuid4()
        ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        a = make_task(
            task_id=common_id,
            room_id=common_room,
            directive_id=common_directive,
            current_stage_id=common_stage,
            created_at=ts,
            updated_at=ts,
        )
        b = make_task(
            task_id=common_id,
            room_id=common_room,
            directive_id=common_directive,
            current_stage_id=common_stage,
            created_at=ts,
            updated_at=ts,
        )
        assert a == b


# ---------------------------------------------------------------------------
# TC-UT-TS-040: last_error の NFC-without-strip 正規化 (§確定 C)
# ---------------------------------------------------------------------------
class TestLastErrorNormalization:
    """TC-UT-TS-040: ``last_error`` は NFC 正規化されるが strip **されない**。

    LLM のスタックトレースはインデント保持のために先頭空白に依存する。
    strip すれば診断情報が静かに破壊される。§確定 C の契約は
    「NFC 正規化、決して strip しない」。
    """

    def test_leading_and_trailing_whitespace_preserved(self) -> None:
        """改行 + 先頭/末尾スペースが正規化を生き残る。"""
        raw = "AuthExpired:\n  at line 1\n  at line 2\n"
        task = make_blocked_task(last_error=raw)
        # post-validator は mode='before' のため、フィールド型チェックの前に走る。
        # 値は NFC を通過するが、先頭/末尾の空白文字はすべて保持される。
        assert task.last_error is not None
        assert task.last_error == unicodedata.normalize("NFC", raw)
        assert task.last_error.startswith("AuthExpired:")
        assert task.last_error.endswith("\n")
        assert "  at line 1" in task.last_error  # 先頭スペース保持

    def test_decomposed_form_normalizes_to_composed_form(self) -> None:
        """合成形の文字は NFC 後に分解形と等価になる。"""
        composed = "café: error"  # NFC 合成形 (é = U+00E9)
        decomposed = "café: error"  # NFC 分解形 (e + COMBINING ACCENT)
        task_composed = make_blocked_task(last_error=composed)
        task_decomposed = make_blocked_task(last_error=decomposed)
        # 双方が同じ NFC 文字列に正規化されるため、フィールド値は
        # バイト等価で一致する。
        assert task_composed.last_error == task_decomposed.last_error


# ---------------------------------------------------------------------------
# TC-UT-TS-044: frozen インスタンス ── 直接の属性代入を拒否
# ---------------------------------------------------------------------------
class TestFrozenInstance:
    """TC-UT-TS-044: ``task.<attr> = value`` は frozen Pydantic model で例外を起こす。"""

    def test_status_assignment_rejected(self) -> None:
        """直接の ``task.status = ...`` は Pydantic frozen により拒否される。"""
        task = make_task()
        with pytest.raises(ValidationError):
            task.status = TaskStatus.IN_PROGRESS  # pyright: ignore[reportAttributeAccessIssue]

    def test_assigned_agents_assignment_rejected(self) -> None:
        """直接の ``task.assigned_agent_ids = ...`` は拒否される。"""
        task = make_task()
        with pytest.raises(ValidationError):
            task.assigned_agent_ids = [uuid4()]  # pyright: ignore[reportAttributeAccessIssue]

    def test_last_error_assignment_rejected(self) -> None:
        """直接の ``task.last_error = ...`` は拒否される。"""
        task = make_blocked_task()
        with pytest.raises(ValidationError):
            task.last_error = "new"  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# TC-UT-TS-045: extra='forbid' は未知フィールドを拒否
# ---------------------------------------------------------------------------
class TestExtraForbid:
    """TC-UT-TS-045: 構築時の未知フィールドは拒否される。"""

    def test_unknown_field_rejected_via_model_validate(self) -> None:
        """``Task.model_validate({..., 'unknown': 'x'})`` が ValidationError。"""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Task.model_validate(
                {
                    "id": uuid4(),
                    "room_id": uuid4(),
                    "directive_id": uuid4(),
                    "current_stage_id": uuid4(),
                    "created_at": now,
                    "updated_at": now,
                    "unknown_field": "should-be-rejected",
                }
            )


# ---------------------------------------------------------------------------
# TC-UT-TS-053: 型エラーは pydantic.ValidationError として現れる (§確定 J)
# ---------------------------------------------------------------------------
class TestTypeErrorsRaisePydanticValidationError:
    """TC-UT-TS-053: 型形式の失敗は ``pydantic.ValidationError`` を用いる（kind 概念なし）。

    §確定 J の契約: 構造的 / フィールド型の誤りは純粋な Pydantic validation error であり、
    7 種類の ``TaskInvariantViolation`` kind はアグリゲートの不変条件のみが発行する。
    Pydantic エラーをカスタム例外でラップする仮想的なリファクタリングが
    docs の見直しを強制するよう、本テストでこの分担を固定する。
    """

    def test_naive_datetime_rejected(self) -> None:
        """timezone を持たない ``created_at`` は拒否される。"""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            make_task(created_at=naive)

    def test_unknown_status_string_rejected(self) -> None:
        """enum でない status 文字列は Pydantic enum 強制により拒否される。"""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Task.model_validate(
                {
                    "id": uuid4(),
                    "room_id": uuid4(),
                    "directive_id": uuid4(),
                    "current_stage_id": uuid4(),
                    "status": "UNKNOWN_STATUS_VALUE",
                    "created_at": now,
                    "updated_at": now,
                }
            )

    def test_non_uuid_id_rejected(self) -> None:
        """``id`` が不正な UUID 形式の文字列は拒否される。"""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Task.model_validate(
                {
                    "id": "not-a-uuid",
                    "room_id": uuid4(),
                    "directive_id": uuid4(),
                    "current_stage_id": uuid4(),
                    "created_at": now,
                    "updated_at": now,
                }
            )


# ---------------------------------------------------------------------------
# Smoke: factory 経由で created_at > updated_at が例外（不変条件側でも検証あり）
# ---------------------------------------------------------------------------
class TestTimestampOrderSmoke:
    """構築時のタイムスタンプ違反は即座に表面化する。"""

    def test_created_after_updated_rejected_at_construction(self) -> None:
        """``created_at > updated_at`` は ``TaskInvariantViolation`` を起こす。"""
        from bakufu.domain.exceptions import TaskInvariantViolation

        ts_old = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
        ts_new = ts_old - timedelta(seconds=1)
        with pytest.raises(TaskInvariantViolation):
            make_task(created_at=ts_old, updated_at=ts_new)
