"""ClaudeCodeLLMClient — Claude Code CLI サブプロセス統合（REQ-LC-015）。

asyncio.create_subprocess_exec でリスト形式引数を使用（shell=True 禁止）。
§確定 CMD-EXEC 準拠。OAuthトークン自動認証（APIキー不要）。
T3 セキュリティ: サブプロセス PID を bakufu_pid_registry に登録・解除する。

設計書: docs/features/llm-client/infrastructure/basic-design.md REQ-LC-015
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from bakufu.domain.exceptions.llm_provider import (
    LLMProviderAuthError,
    LLMProviderEmptyResponseError,
    LLMProviderProcessError,
    LLMProviderTimeoutError,
)
from bakufu.domain.value_objects.chat_result import ChatResult, ToolCall
from bakufu.infrastructure.security.masking import mask

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

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

    **T3 セキュリティ**: ``session_factory`` が注入されている場合、サブプロセス生成直後に
    ``bakufu_pid_registry`` へ PID を INSERT し、完了後（timeout/cancel 含む finally）で
    DELETE する。GC は Bootstrap Stage 4 が引き継ぐ。
    """

    provider: str = "claude-code"

    def __init__(
        self,
        model_name: str,
        timeout_seconds: float,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._session_factory = session_factory

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

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        system: str,
        tools: list[dict[str, object]],
        session_id: str | None = None,
    ) -> ChatResult:
        """Claude Code CLI でツール呼び出し対応の LLM 実行を行う（M5-B §確定 D）。

        ``tools`` パラメータは型情報として受け取るが、現行の Claude Code CLI では
        ツールスキーマを CLI 引数で直接渡す手段がないため、応答のパースで対応する。
        Claude CLI が tool_use 形式で応答した場合に ``tool_calls`` を返す。

        Args:
            messages: メッセージリスト。
            system: システムプロンプト。
            tools: tool schema リスト（将来の CLI 拡張用に受け取るが現行は参照のみ）。
            session_id: セッション継続 ID。None の場合は新規セッション。

        Returns:
            ChatResult — ``tool_calls`` に抽出したツール呼び出し情報を含む。
            ツール呼び出しがない場合は ``tool_calls`` が空タプルとなる。
        """
        del tools  # 現行実装では CLI 引数経由でスキーマを渡せないため参照のみ。
        prompt = self._build_prompt(messages)
        try:
            base_result = await asyncio.wait_for(
                self._run_claude(prompt, system, use_tools=True, session_id=session_id),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMProviderTimeoutError(
                message=_MSG_LC_001_TMPL.format(timeout_seconds=self._timeout_seconds),
                provider=self.provider,
            ) from exc

        tool_calls = self._extract_tool_calls(base_result.response)
        return ChatResult(
            response=base_result.response,
            session_id=base_result.session_id,
            compacted=base_result.compacted,
            tool_calls=tool_calls,
        )

    def _extract_tool_calls(self, response: str) -> tuple[ToolCall, ...]:
        """LLM 応答テキストから ToolCall リストを抽出する。

        Claude Code CLI が tool_use 形式（JSON 文字列）で応答した場合に ToolCall を返す。
        パース失敗時は空タプルを返す。

        Returns:
            ToolCall のタプル。ツール呼び出しがない場合は空タプル。
        """
        try:
            parsed: object = json.loads(response)
            if not isinstance(parsed, dict):
                return ()
            data: dict[str, object] = cast(dict[str, object], parsed)
            if data.get("type") != "tool_use":
                return ()
            name_raw: object = data.get("name", "")
            if not isinstance(name_raw, str) or not name_raw:
                return ()
            input_raw: object = data.get("input", {})
            if not isinstance(input_raw, dict):
                return ()
            tool_input: dict[str, object] = cast(dict[str, object], input_raw)
            return (ToolCall(name=name_raw, input=tool_input),)
        except (json.JSONDecodeError, AttributeError):
            return ()

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
        allowed_keys = {"PATH", "HOME", "LANG", "LC_ALL", "CLAUDE_HOME"}
        env = {k: v for k, v in os.environ.items() if k in allowed_keys or k.startswith("BAKUFU_")}

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # T3: PID を pid_registry に登録する（session_factory 未注入時はスキップ）。
        await self._register_pid(process.pid, cmd)
        try:
            stdout_bytes, stderr_bytes = await process.communicate()
        finally:
            # T3: 完了後（timeout/CancelledError 含む）に pid_registry から削除する。
            # 例外中の await は安全だが失敗しても GC が次回起動時に補完するため suppress。
            with contextlib.suppress(Exception):
                await self._unregister_pid(process.pid)

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

    async def _register_pid(self, pid: int, cmd: list[str]) -> None:
        """PID を bakufu_pid_registry に INSERT する（T3 セキュリティ）。

        ``session_factory`` が None の場合はスキップ（テスト・factory 経由以外の構築時）。
        失敗しても警告ログのみ — LLM 実行は継続する（非致命）。
        """
        if self._session_factory is None:
            return
        try:
            import psutil

            from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
                PidRegistryRow,
            )

            # psutil で実際の create_time を取得（GC の PID 衝突ガードに使用）
            try:
                started_at = datetime.fromtimestamp(psutil.Process(pid).create_time(), UTC)
            except Exception:
                started_at = datetime.now(UTC)

            async with self._session_factory() as session, session.begin():
                session.add(
                    PidRegistryRow(
                        pid=pid,
                        parent_pid=os.getpid(),
                        started_at=started_at,
                        cmd=str(cmd),
                        task_id=None,
                        stage_id=None,
                    )
                )
        except Exception:
            logger.warning(
                "[WARN] pid_registry INSERT failed for pid=%d; continuing without tracking",
                pid,
            )

    async def _unregister_pid(self, pid: int) -> None:
        """PID を bakufu_pid_registry から DELETE する（T3 セキュリティ）。

        失敗しても警告ログのみ — GC が次回起動時に補完する（非致命）。
        """
        if self._session_factory is None:
            return
        try:
            from sqlalchemy import delete

            from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
                PidRegistryRow,
            )

            async with self._session_factory() as session, session.begin():
                await session.execute(delete(PidRegistryRow).where(PidRegistryRow.pid == pid))
        except Exception:
            logger.warning(
                "[WARN] pid_registry DELETE failed for pid=%d; GC will clean up at next startup",
                pid,
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
            elif event_type == "system":
                result_session_id = event.get("session_id") or result_session_id
                # REQ-LC-015: subtype="compact" イベントでコンテキスト圧縮を検出する。
                if event.get("subtype") == "compact":
                    compacted = True

        return response_text, result_session_id, compacted


__all__ = ["ClaudeCodeLLMClient"]
