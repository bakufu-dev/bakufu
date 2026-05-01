"""MSG-LC-001〜006 確定文言・プレフィックス物理保証テスト（TC-UT-MSG-001〜006）.

Issue: #144
domain 層の例外クラスに直接メッセージを設定してプレフィックス・プレースホルダを検証する。
"""

from __future__ import annotations

from bakufu.domain.exceptions.llm_client import (
    LLMAPIError,
    LLMAuthError,
    LLMMessageValidationError,
    LLMRateLimitError,
    LLMTimeoutError,
)

# infrastructure 層で使われる確定文言テンプレートを模倣して構築する。
# 実際の文言は infrastructure/anthropic_llm_client.py / openai_llm_client.py で定義。
_MSG_LC_001 = (
    "[FAIL] LLM API call timed out after {timeout_seconds}s (provider={provider})\n"
    "Next: Retry with exponential backoff, or increase BAKUFU_LLM_TIMEOUT_SECONDS."
)
_MSG_LC_002 = (
    "[FAIL] LLM API rate limit exceeded (provider={provider}, retry_after={retry_after}s)\n"
    "Next: Wait {retry_after}s before retrying, or reduce request frequency."
)
_MSG_LC_003 = (
    "[FAIL] LLM API authentication failed (provider={provider})\n"
    "Next: Set BAKUFU_{PROVIDER}_API_KEY to a valid API key and restart."
)
_MSG_LC_004 = (
    "[FAIL] LLM API error (provider={provider}, status={status_code})\n"
    "Next: Check provider status page and inspect raw_error for details."
)
_MSG_LC_005 = (
    "[FAIL] LLMMessage validation failed: field={field} is invalid (provider={provider})\n"
    "Next: Ensure all LLMMessage.content values are non-empty strings."
)


class TestMsgPrefixes:
    """TC-UT-MSG-001〜006: [FAIL]/[WARN] プレフィックスとプレースホルダ展開。"""

    def test_msg_lc_001_timeout_has_fail_prefix_and_values(self) -> None:
        """TC-UT-MSG-001: MSG-LC-001 — [FAIL] プレフィックス + timeout_seconds + provider。"""
        msg = _MSG_LC_001.format(timeout_seconds=30.0, provider="anthropic")
        exc = LLMTimeoutError(message=msg, provider="anthropic", timeout_seconds=30.0)
        assert exc.message.startswith("[FAIL]")
        assert "30.0" in exc.message
        assert "anthropic" in exc.message

    def test_msg_lc_002_rate_limit_has_fail_prefix_and_values(self) -> None:
        """TC-UT-MSG-002: MSG-LC-002 — [FAIL] プレフィックス + retry_after + provider。"""
        msg = _MSG_LC_002.format(provider="anthropic", retry_after=60.0)
        exc = LLMRateLimitError(message=msg, provider="anthropic", retry_after=60.0)
        assert exc.message.startswith("[FAIL]")
        assert "60.0" in exc.message
        assert "anthropic" in exc.message

    def test_msg_lc_003_auth_has_fail_prefix_and_provider(self) -> None:
        """TC-UT-MSG-003: MSG-LC-003 — [FAIL] プレフィックス + provider + API key 文言。"""
        msg = _MSG_LC_003.format(provider="openai", PROVIDER="OPENAI")
        exc = LLMAuthError(message=msg, provider="openai")
        assert exc.message.startswith("[FAIL]")
        assert "openai" in exc.message
        assert "API" in exc.message

    def test_msg_lc_004_api_error_has_fail_prefix_and_status(self) -> None:
        """TC-UT-MSG-004: MSG-LC-004 — [FAIL] プレフィックス + status_code + provider。"""
        msg = _MSG_LC_004.format(provider="anthropic", status_code=503)
        exc = LLMAPIError(message=msg, provider="anthropic", status_code=503)
        assert exc.message.startswith("[FAIL]")
        assert "503" in exc.message
        assert "anthropic" in exc.message

    def test_msg_lc_005_validation_has_fail_prefix_and_field(self) -> None:
        """TC-UT-MSG-005: MSG-LC-005 — [FAIL] プレフィックス + field。"""
        msg = _MSG_LC_005.format(field="content", provider="anthropic")
        exc = LLMMessageValidationError(message=msg, provider="anthropic", field="content")
        assert exc.message.startswith("[FAIL]")
        assert "content" in exc.message

    def test_msg_lc_006_empty_response_is_fail(self) -> None:
        """TC-UT-MSG-006: MSG-LC-006 — [FAIL] プレフィックス（§確定D: Fail Fast に変更済み）。

        元設計の [WARN] → 変更後は [FAIL] に変更。
        infrastructure 層の _MSG_LC_006 テンプレートが [FAIL] で始まることを確認。
        """
        # モジュール全体のソースから _MSG_LC_006 の物理確認
        from pathlib import Path

        import bakufu.infrastructure.llm.anthropic_llm_client as _ac_mod

        src = Path(_ac_mod.__file__).read_text(encoding="utf-8")
        # _MSG_LC_006 テンプレートが [FAIL] で始まることを物理確認
        assert "[FAIL] LLM returned no text content" in src
