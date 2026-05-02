"""CodexLLMClient — Codex CLI サブプロセス統合（REQ-LC-016）。

asyncio.create_subprocess_exec でリスト形式引数を使用（shell=True 禁止）。
§確定 CMD-EXEC 準拠。OpenAI サブスクリプション認証（APIキー不要）。

設計書: docs/features/llm-client/infrastructure/basic-design.md REQ-LC-016
"""

from __future__ import annotations

import asyncio
import json
import os

from bakufu.domain.exceptions.llm_provider import (
    LLMProviderAuthError,
    LLMProviderEmptyResponseError,
    LLMProviderProcessError,
    LLMProviderTimeoutError,
)
from bakufu.domain.value_objects.chat_result import ChatResult
from bakufu.infrastructure.security.masking import mask

# 認証失敗 stderr パターン（REQ-LC-016 §エラー時）
_AUTH_PATTERNS = ("auth", "unauthorized", "subscription")

# MSG-LC-001: タイムアウト
_MSG_LC_001_TMPL = (
    "[FAIL] LLM CLI call timed out after {timeout_seconds}s (provider=codex).\n"
    "Next: Retry with exponential backoff, or increase BAKUFU_LLM_TIMEOUT_SECONDS."
)

# MSG-LC-003: 認証失敗
_MSG_LC_003 = (
    "[FAIL] LLM CLI authentication failed (provider=codex).\n"
    "Next: Re-authenticate with Codex CLI (subscription may have expired)."
)

# MSG-LC-004: プロセスエラー
_MSG_LC_004_TMPL = (
    "[FAIL] LLM CLI process error (provider=codex, exit_code={exit_code}).\n"
    "Next: Check `codex` CLI availability and stderr for details."
)

# MSG-LC-006: 空応答
_MSG_LC_006 = (
    "[FAIL] LLM CLI returned no text content (provider=codex).\n"
    "Next: Retry the request or inspect the codex CLI status."
)


class CodexLLMClient:
    """Codex CLI サブプロセス統合クライアント（LLMProviderPort 実装）。

    provider = "codex"。
    §確定 SEC5: --dangerously-bypass-approvals-and-sandbox は --ephemeral と組み合わせて使用。
    全 CLI 呼び出しは asyncio.create_subprocess_exec リスト形式（§確定 CMD-EXEC）。
    stdout を JSONL 形式で非同期読み込みし、item.type == "agent_message" から応答を抽出。
    """

    provider: str = "codex"

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
        """Codex CLI でテキスト補完を実行する。

        Args:
            messages: メッセージリスト。最終 user メッセージをプロンプトとして使用。
            system: システムプロンプト（Codex では prompt に統合）。
            use_tools: 未使用（Codex は --dangerously-bypass-approvals-and-sandbox で対応）。
            agent_name: 未使用（インターフェース互換のため保持）。
            session_id: Codex は session_id を返さない（None 固定）。

        Returns:
            ChatResult（session_id=None, compacted=False 固定）

        Raises:
            LLMProviderTimeoutError: タイムアウト発生時。
            LLMProviderAuthError: 認証失敗時。
            LLMProviderProcessError: CLI プロセスエラー時。
            LLMProviderEmptyResponseError: 空応答時。
        """
        prompt = self._build_prompt(messages, system)
        try:
            return await asyncio.wait_for(
                self._run_codex(prompt),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMProviderTimeoutError(
                message=_MSG_LC_001_TMPL.format(timeout_seconds=self._timeout_seconds),
                provider=self.provider,
            ) from exc

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        system: str,
        tools: list[dict[str, object]],
        session_id: str | None = None,
    ) -> ChatResult:
        """ツール呼び出し対応の LLM 呼び出し（§確定 D）。

        Codex は tool_use を未サポートのため、``chat()`` に委譲して
        tool_calls が空の ChatResult を返す。
        """
        del tools, session_id  # Codex は tool schema を使用しない
        return await self.chat(messages=messages, system=system)

    def _build_prompt(self, messages: list[dict[str, str]], system: str) -> str:
        """messages リストとシステムプロンプトからプロンプト文字列を構築する。"""
        parts: list[str] = []
        if system:
            parts.append(system)
        for msg in messages:
            content = msg.get("content", "")
            if content:
                parts.append(content)
        return "\n\n".join(parts)

    async def _run_codex(self, prompt: str) -> ChatResult:
        """codex CLI をサブプロセスで起動し応答を収集する。

        §確定 SEC5: --dangerously-bypass-approvals-and-sandbox + --ephemeral 使用。
        """
        cmd: list[str] = [
            "codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--ephemeral",
            "--dangerously-bypass-approvals-and-sandbox",
            prompt,
        ]

        # §確定 CMD-EXEC: リスト形式、shell=False、env allow-list 管理
        allowed_keys = {"PATH", "HOME", "LANG", "LC_ALL"}
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

        response_text = self._parse_jsonl(stdout_bytes.decode("utf-8", errors="replace"))

        if not response_text:
            raise LLMProviderEmptyResponseError(
                message=_MSG_LC_006,
                provider=self.provider,
            )

        # Codex は session_id を返さない（REQ-LC-016 §出力）
        return ChatResult(
            response=response_text,
            session_id=None,
            compacted=False,
        )

    def _parse_jsonl(self, stdout: str) -> str:
        """JSONL 形式から agent_message タイプの応答テキストを抽出する。"""
        response_parts: list[str] = []

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            if item.get("type") == "agent_message":
                content = item.get("content", "")
                if content:
                    response_parts.append(str(content))

        return "\n".join(response_parts)


__all__ = ["CodexLLMClient"]
