"""Directive 構築 + 境界値テスト
(TC-UT-DR-001 / 002 / 003 / 004 / 014 / 015)。

REQ-DR-001 (構築) + ``text`` 長境界 + NFC
正規化 + 意図的な **ノンストリップ** 契約 +
コンストラクターパス Repository ハイドレーション (§確定 C) + tz-aware 強制をカバー。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.directive import Directive
from bakufu.domain.exceptions import DirectiveInvariantViolation
from pydantic import ValidationError

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestDefaultConstruction:
    """TC-UT-DR-001: ファクトリーデフォルトは task_id=None の有効 Directive。"""

    def test_default_directive_has_no_task_link(self) -> None:
        """TC-UT-DR-001: ファクトリーデフォルト は task_id=None で構築。"""
        directive = make_directive()
        assert directive.task_id is None

    def test_default_directive_has_tz_aware_created_at(self) -> None:
        """TC-UT-DR-001: ファクトリーデフォルト は tz-aware datetime を含む。"""
        directive = make_directive()
        assert directive.created_at.tzinfo is not None

    def test_default_directive_text_is_short_with_dollar_prefix(self) -> None:
        """TC-UT-DR-001: デフォルト text は アプリケーション層 ``$`` 規約に従う。"""
        directive = make_directive()
        assert directive.text.startswith("$ ")


class TestTextBoundary:
    """TC-UT-DR-002: text 長境界 0 / 1 / 10000 / 10001 (確定 B)。"""

    @pytest.mark.parametrize("length", [1, 10_000])
    def test_valid_lengths_succeed(self, length: int) -> None:
        """TC-UT-DR-002: text 長 1 と 10000 は成功。"""
        directive = make_directive(text="a" * length)
        assert len(directive.text) == length

    def test_empty_text_raises_text_range(self) -> None:
        """TC-UT-DR-002: text 長 0 は detail.length=0 で text_range を発火。"""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="")
        assert excinfo.value.kind == "text_range"
        assert excinfo.value.detail.get("length") == 0

    def test_oversized_text_raises_text_range(self) -> None:
        """TC-UT-DR-002: text 長 10001 は detail.length=10001 で text_range を発火。"""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="a" * 10_001)
        assert excinfo.value.kind == "text_range"
        assert excinfo.value.detail.get("length") == 10_001


class TestNfcNormalization:
    """TC-UT-DR-003: NFC 正規化は合成・分解形を統一 (確定 B)。"""

    def test_composed_and_decomposed_forms_collapse(self) -> None:
        """TC-UT-DR-003: 合成・分解形は同じ NFC 文字列を生成。"""
        composed = "ダリオ要件"
        decomposed = "ダリオ要件"
        d_composed = make_directive(text=composed)
        d_decomposed = make_directive(text=decomposed)
        assert d_composed.text == d_decomposed.text


class TestStripIsNotApplied:
    """TC-UT-DR-004: text は NFC のみ、ストリップなし — 先頭/末尾改行を保持。"""

    def test_leading_and_trailing_newlines_are_preserved(self) -> None:
        """TC-UT-DR-004: '\\n# Directive\\n\\nbody\\n\\n' は逐語的に保持。

        CEO directives は複数段落構造に依存する可能性; ストリップは
        インテント を静かに書き換える。Confirmation B はこれを
        文書化設計選択として fix。
        """
        text = "\n# Directive\n\nbody\n\n"
        directive = make_directive(text=text)
        assert directive.text == text


class TestRepositoryHydrationViaConstructor:
    """TC-UT-DR-014: コンストラクタは ``task_id=existing TaskId`` を受け入れ (§確定 C)。"""

    def test_directive_can_be_constructed_with_task_id(self) -> None:
        """TC-UT-DR-014: Repository ハイドレーション状態 ``task_id != None`` は清潔に構築。"""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        assert directive.task_id == existing_task_id


class TestCreatedAtMustBeTzAware:
    """TC-UT-DR-015: naïve datetime は pydantic.ValidationError を発火 (MSG-DR-003)。"""

    def test_naive_datetime_is_rejected(self) -> None:
        """TC-UT-DR-015: ``created_at=datetime.utcnow()`` (naïve) → ValidationError。"""
        # Pydantic は ``_require_tz_aware`` ValueError を
        # ``after`` validator 内のアサートが存在するとき
        # ``ValidationError`` として表示。
        with pytest.raises(ValidationError):
            Directive(
                id=uuid4(),
                text="$ test",
                target_room_id=uuid4(),
                created_at=datetime(2026, 4, 27, 10, 0, 0),  # naïve
                task_id=None,
            )

    def test_tz_aware_utc_datetime_succeeds(self) -> None:
        """TC-UT-DR-015 補足: tz-aware UTC datetime が唯一許可形。"""
        directive = make_directive(created_at=datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC))
        assert directive.created_at.tzinfo is not None
