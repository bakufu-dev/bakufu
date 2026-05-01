"""ClaudeCodeLLMClient — Claude Code CLI サブプロセス統合（REQ-LC-015）。

asyncio.create_subprocess_exec でリスト形式引数を使用（shell=True 禁止）。
§確定 CMD-EXEC 準拠。OAuthトークン自動認証（APIキー不要）。

設計書: docs/features/llm-client/infrastructure/basic-design.md REQ-LC-015
"""

from __future__ import annotations

import asyncio
import json

from bakufu.domain.exceptions.llm_provider import (
    LLMProviderAuthError,
    LLMProviderEmptyResponseError,
    LLMProviderProcessError,
    LLMProviderTimeoutError,
)
from bakufu.domain.value_objects.chat_result import ChatResult
from bakufu.infrastructure.security.masking import mask

# 認証失敗 stderr パターン（REQ-LC-015 §エラー時）
_AUTH_PATTERNS = ("OAuth", "unauthorized", "authentication")

# MSG-LC-001: タイムアウト
_MSG_LC_001_TMPL = (
    "[FAIL] LLM CLI call timed out after {timeout_seconds}s (provider=claude-code).\n"
    "Next: Retry with exponential backoff, or increase BAKUFU_LLM_TIMEOUT_SECONDS."
)

# MSG-LC-003: 認証失敗
_MSG_LC_003 = (
    "[FAIL] LLM CLI authentication failed (provider=claude-code).\n"
    "Next: Re-authenticate with `claude` CLI (OAuth token may have expired)."
)

# MSG-LC-004: プロセスエラー
_MSG_LC_004_TMPL = (
    "[FAIL] LLM CLI process error (provider=claude-code, exit_code={exit_code}).\n"
    "Next: Check `claude` CLI availability and stderr for details."
)

# MSG-LC-006: 空応答
_MSG_LC_006 = (
    "[FAIL] LLM CLI returned no text content (provider=claude-code).\n"
    "Next: Retry the request or inspect the claude CLI status."
)


class ClaudeCodeLLMClient:
    """Claude Code CLI サブプロセス統合クライアント（LLMProviderPort 実装）。

    provider = "claude-code"。
    全 CLI 呼び出しは asyncio.create_subprocess_exec リスト形式（§確定 CMD-EXEC）。
    stdout を JSONL stream-json 形式で非同期読み込みし、event_type="result" から応答を抽出。
    """

    provider: str = "claude-code"

    def __init__(self, model_name: str, timeout_seconds: float) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str,
        use_tools: bool = False,
        agent_name: str = "",
        session_id: str | None = None,
    ) -> ChatResult:
        """Claude Code CLI でテキスト補完を実行する。

        Args:
            messages: メッセージリスト。最終 user メッセージをプロンプトとして使用。
            system: システムプロンプト。
            use_tools: True の場合 --permission-mode bypassPermissions を追加。
            agent_name: 未使用（インターフェース互換のため保持）。
            session_id: セッション継続 ID。None の場合は新規セッション。

        Returns:
            ChatResult

        Raises:
            LLMProviderTimeoutError: タイムアウト発生時。
            LLMProviderAuthError: 認証失敗時。
            LLMProviderProcessError: CLI プロセスエラー時。
            LLMProviderEmptyResponseError: 空応答時。
        """
        prompt = self._build_prompt(messages)
        try:
            return await asyncio.wait_for(
                self._run_claude(prompt, system, use_tools, session_id),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMProviderTimeoutError(
                message=_MSG_LC_001_TMPL.format(timeout_seconds=self._timeout_seconds),
                provider=self.provider,
            ) from exc

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        """messages リストから最終ユーザーメッセージをプロンプト文字列に変換する。"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        # フォールバック: 全 content を結合
        return "\n".join(m.get("content", "") for m in messages)

    async def _run_claude(
        self,
        prompt: str,
        system: str,
        use_tools: bool,
        session_id: str | None,
    ) -> ChatResult:
        """claude CLI をサブプロセスで起動し応答を収集する。"""
        cmd: list[str] = [
            "claude",
            "-p",
            prompt,
            "--system-prompt",
            system,
            "--model",
            self._model_name,
            "--output-format",
            "stream-json",
            "--verbose",
        ]

        if use_tools:
            cmd += ["--permission-mode", "bypassPermissions"]
        else:
            cmd += ["--tools", ""]

        if session_id is not None:
            cmd += ["--resume", session_id]

        # §確定 CMD-EXEC: リスト形式、shell=False、env allow-list 管理
        import os

        allowed_keys = {"PATH", "HOME", "LANG", "CLAUDE_HOME"}
        env = {k: v for k, v in os.environ.items() if k in allowed_keys or k.startswith("BAKUFU_")}

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout_bytes, stderr_bytes = await process.communicate()

        if process.returncode != 0:
            stderr_text = mask(stderr_bytes.decode("utf-8", errors="replace"))
            # 認証パターン検出
            if any(p.lower() in stderr_text.lower() for p in _AUTH_PATTERNS):
                raise LLMProviderAuthError(
                    message=_MSG_LC_003,
                    provider=self.provider,
                )
            raise LLMProviderProcessError(
                message=_MSG_LC_004_TMPL.format(exit_code=process.returncode),
                provider=self.provider,
            )

        response_text, result_session_id, compacted = self._parse_stream_json(
            stdout_bytes.decode("utf-8", errors="replace")
        )

        if not response_text:
            raise LLMProviderEmptyResponseError(
                message=_MSG_LC_006,
                provider=self.provider,
            )

        return ChatResult(
            response=response_text,
            session_id=result_session_id,
            compacted=compacted,
        )

    def _parse_stream_json(self, stdout: str) -> tuple[str, str | None, bool]:
        """JSONL stream-json 形式から応答テキスト・session_id・compacted を抽出する。

        event_type="result" の result フィールドに最終テキストが入っている。
        Returns:
            tuple of (response_text, session_id, compacted)
        """
        response_text = ""
        result_session_id: str | None = None
        compacted = False

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type") or event.get("event_type", "")
            if event_type == "result":
                response_text = str(event.get("result", ""))
                result_session_id = event.get("session_id") or result_session_id
                compacted = bool(event.get("is_error", False) is False and event.get("num_turns"))
            elif event_type == "system":
                result_session_id = event.get("session_id") or result_session_id
                if event.get("subtype") == "init":
                    result_session_id = event.get("session_id") or result_session_id

        return response_text, result_session_id, compacted


__all__ = ["ClaudeCodeLLMClient"]
