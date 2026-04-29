"""PromptKit Value Object テスト (TC-UT-RM-019 / 024、Confirmations B / G)。

PromptKit は NFC 正規化 (strip なし — Markdown 本体は
先頭/末尾の空白を保持) と 10000 文字上限に保持される
単一属性 frozen VO。長さ違反は
:class:`RoomInvariantViolation` **ではなく** Room §確定 I
二段階キャッチに従い :class:`pydantic.ValidationError` として表示。
"""

from __future__ import annotations

import pytest
from bakufu.domain.room import PROMPT_KIT_PREFIX_MAX, PromptKit
from pydantic import ValidationError

from tests.factories.room import make_prompt_kit, make_room


class TestPromptKitBoundary:
    """TC-UT-RM-019: 0 / 10000 / 10001 + 先頭/末尾改行保持。"""

    @pytest.mark.parametrize("length", [0, PROMPT_KIT_PREFIX_MAX])
    def test_valid_lengths_succeed(self, length: int) -> None:
        """TC-UT-RM-019: 長さ 0 と 10000 の prefix_markdown は成功。"""
        kit = make_prompt_kit(prefix_markdown="a" * length)
        assert len(kit.prefix_markdown) == length

    def test_oversized_prefix_raises_validation_error(self) -> None:
        """TC-UT-RM-019: 10001 文字は §確定 I に従い pydantic.ValidationError を発火。"""
        with pytest.raises(ValidationError) as excinfo:
            make_prompt_kit(prefix_markdown="a" * (PROMPT_KIT_PREFIX_MAX + 1))
        # Confirmation I は PromptKit 長さエラーが **RoomInvariantViolation パスを
        # 通わない** ことを fix。MSG-RM-007 wording は test_msg_wording.py で
        # アサート。
        assert "PromptKit.prefix_markdown" in str(excinfo.value)

    def test_prompt_kit_preserves_leading_and_trailing_newlines(self) -> None:
        """TC-UT-RM-019 + 018: PromptKit は NFC のみ適用 — 改行を保持。

        Markdown セマンティクス: ``\\n# Heading\\n\\nbody\\n\\n`` は
        ボディの末尾空白がプロンプト テンプレートの一部であるため
        ラップ改行を保持。
        """
        text = "\n# Heading\n\nbody\n\n"
        kit = make_prompt_kit(prefix_markdown=text)
        assert kit.prefix_markdown == text


class TestPromptKitStructuralEquality:
    """TC-UT-RM-024: PromptKit / Room frozen → 構造的等価 + ハッシュ可能。"""

    def test_two_prompt_kits_with_same_attrs_compare_equal(self) -> None:
        """TC-UT-RM-024: 同じ prefix の 2 つの PromptKit は等価。"""
        a = PromptKit(prefix_markdown="hello")
        b = PromptKit(prefix_markdown="hello")
        assert a == b

    def test_two_prompt_kits_with_same_attrs_hash_equal(self) -> None:
        """TC-UT-RM-024: 構造的に等価な PromptKit はハッシュを共有。"""
        a = PromptKit(prefix_markdown="hello")
        b = PromptKit(prefix_markdown="hello")
        assert hash(a) == hash(b)

    def test_two_rooms_with_same_attrs_compare_equal(self) -> None:
        """TC-UT-RM-024: 同じ属性の 2 つの Room は等価。"""
        from uuid import uuid4

        room_id = uuid4()
        workflow_id = uuid4()
        a = make_room(room_id=room_id, workflow_id=workflow_id)
        b = make_room(room_id=room_id, workflow_id=workflow_id)
        assert a == b
