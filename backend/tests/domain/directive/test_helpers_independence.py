"""モジュールレベルヘルパー独立性 (Boy Scout 双防御対称性)。

agent / room 前例: あらゆる Aggregate レベル不変ヘルパーは
モジュールスコープに存在し、テストが ``import`` して直接呼び出し可能。
agent / room ``test_helpers_independence.py`` パターンをミラーリング。
これらテストはヘルパー署名とエントリポイント契約を freeze —
Aggregate はその上の薄いディスパッチであり、
ヘルパをモデル_validator に内置するリファクタはこのテストファイルも
アップデート必須。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.directive import (
    MAX_TEXT_LENGTH,
    MIN_TEXT_LENGTH,
    _validate_task_link_immutable,
    _validate_text_range,
)
from bakufu.domain.exceptions import DirectiveInvariantViolation


class TestValidateTextRange:
    """``_validate_text_range`` はモジュールレベル純粋関数。"""

    @pytest.mark.parametrize("length", [MIN_TEXT_LENGTH, MAX_TEXT_LENGTH])
    def test_valid_lengths_return_none(self, length: int) -> None:
        """有効長は発火せず ``None`` を返す。"""
        result = _validate_text_range("a" * length)
        assert result is None

    @pytest.mark.parametrize("length", [0, MAX_TEXT_LENGTH + 1])
    def test_invalid_lengths_raise_text_range(self, length: int) -> None:
        """範囲外の長さは ``DirectiveInvariantViolation(kind='text_range')`` を発火。"""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            _validate_text_range("a" * length)
        assert excinfo.value.kind == "text_range"


class TestValidateTaskLinkImmutable:
    """``_validate_task_link_immutable`` はモジュールレベル純粋関数 (確定 C / D)。"""

    def test_existing_none_passes(self) -> None:
        """Confirmation C: existing_task_id=None は任意の attempted_task_id を許可。"""
        directive_id = uuid4()
        attempted = uuid4()
        # existing が None のとき ``None`` を返す (発火なし)。
        result = _validate_task_link_immutable(
            directive_id=directive_id,
            existing_task_id=None,
            attempted_task_id=attempted,
        )
        assert result is None

    def test_existing_value_raises_on_different_attempt(self) -> None:
        """Confirmation C: 既存 → 異なる新 task_id は発火。"""
        directive_id = uuid4()
        existing = uuid4()
        attempted = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            _validate_task_link_immutable(
                directive_id=directive_id,
                existing_task_id=existing,
                attempted_task_id=attempted,
            )
        assert excinfo.value.kind == "task_already_linked"

    def test_existing_value_raises_on_identical_attempt(self) -> None:
        """Confirmation D: 既存 == attempted task_id もまだ発火 (冪等性なし)。"""
        directive_id = uuid4()
        same = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            _validate_task_link_immutable(
                directive_id=directive_id,
                existing_task_id=same,
                attempted_task_id=same,
            )
        assert excinfo.value.kind == "task_already_linked"
