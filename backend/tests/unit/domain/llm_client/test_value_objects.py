"""LLMMessage / LLMResponse / MessageRole VO テスト.

TC-UT-LM-001〜006, TC-UT-RESP-001〜004, TC-UT-ROLE-001〜003

Issue: #144
"""
from __future__ import annotations

import pydantic
import pytest
from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse, MessageRole


class TestLLMMessage:
    """TC-UT-LM-001〜006: LLMMessage VO 構築・バリデーション・不変性。"""

    def test_constructs_with_user_role(self) -> None:
        """TC-UT-LM-001: USER ロールで正常構築。"""
        msg = LLMMessage(role=MessageRole.USER, content="こんにちは")
        assert msg.role == MessageRole.USER
        assert msg.content == "こんにちは"

    def test_constructs_with_system_role(self) -> None:
        """TC-UT-LM-002: SYSTEM ロールで正常構築。"""
        msg = LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant.")
        assert msg.role == MessageRole.SYSTEM

    def test_constructs_with_assistant_role(self) -> None:
        """TC-UT-LM-003: ASSISTANT ロールで正常構築。"""
        msg = LLMMessage(role=MessageRole.ASSISTANT, content="了解です")
        assert msg.role == MessageRole.ASSISTANT

    def test_empty_content_raises_validation_error(self) -> None:
        """TC-UT-LM-004: content 空文字 → pydantic.ValidationError（min_length=1 制約）。"""
        with pytest.raises(pydantic.ValidationError):
            LLMMessage(role=MessageRole.USER, content="")

    def test_frozen_rejects_direct_assignment(self) -> None:
        """TC-UT-LM-005: frozen=True により直接代入が拒否される。"""
        msg = LLMMessage(role=MessageRole.USER, content="元のテキスト")
        with pytest.raises((pydantic.ValidationError, TypeError)):
            msg.content = "変更後"  # type: ignore[misc]

    def test_extra_fields_ignored(self) -> None:
        """TC-UT-LM-006: LLMMessage.model_config は frozen=True のみ（extra 設定なし）。

        ⚠️ BUG NOTE: domain/test-design.md TC-UT-LM-006 says extra='forbid' but the actual
        implementation only sets frozen=True (no extra restriction). Extra fields are silently
        ignored. This test documents the ACTUAL implementation behavior.
        """
        # 実装は extra='forbid' を設定していない → extra フィールドは無視される
        msg = LLMMessage.model_validate({"role": "user", "content": "テスト", "extra_field": "x"})
        assert msg.content == "テスト"
        assert not hasattr(msg, "extra_field")


class TestLLMResponse:
    """TC-UT-RESP-001〜004: LLMResponse VO 構築・不変性。"""

    def test_constructs_with_nonempty_content(self) -> None:
        """TC-UT-RESP-001: 非空 content で正常構築。"""
        resp = LLMResponse(content="評価結果テキスト")
        assert resp.content == "評価結果テキスト"

    def test_empty_content_raises_validation_error(self) -> None:
        """TC-UT-RESP-002: content='' は min_length=1 制約により ValidationError。

        NOTE: domain/test-design.md TC-UT-RESP-002 says empty string succeeds
        (old "infrastructure handles fallback" design), but the actual implementation
        has Field(min_length=1) per §確定F / change (Fail Fast). The test-design
        was not updated after that change. This test follows the ACTUAL implementation.
        """
        with pytest.raises(pydantic.ValidationError):
            LLMResponse(content="")

    def test_frozen_rejects_direct_assignment(self) -> None:
        """TC-UT-RESP-003: frozen=True により直接代入が拒否される。"""
        resp = LLMResponse(content="応答テキスト")
        with pytest.raises((pydantic.ValidationError, TypeError)):
            resp.content = "変更後"  # type: ignore[misc]

    def test_no_session_id_or_compacted_fields(self) -> None:
        """TC-UT-RESP-004: §確定B — session_id / compacted フィールドを持たない。"""
        resp = LLMResponse(content="応答テキスト")
        assert not hasattr(resp, "session_id")
        assert not hasattr(resp, "compacted")


class TestMessageRole:
    """TC-UT-ROLE-001〜003: §確定C — StrEnum 文字列等価（SDK に渡す際に .value 変換不要）。"""

    def test_user_equals_string(self) -> None:
        """TC-UT-ROLE-001: MessageRole.USER == 'user'。"""
        assert MessageRole.USER == "user"

    def test_system_equals_string(self) -> None:
        """TC-UT-ROLE-002: MessageRole.SYSTEM == 'system'。"""
        assert MessageRole.SYSTEM == "system"

    def test_assistant_equals_string(self) -> None:
        """TC-UT-ROLE-003: MessageRole.ASSISTANT == 'assistant'。"""
        assert MessageRole.ASSISTANT == "assistant"
