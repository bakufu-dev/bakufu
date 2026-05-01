"""ClaudeCodeLLMClient._parse_stream_json ユニットテスト（TC-UT-LC-COMPACT-001〜004）。

Issue: #123
設計書: docs/features/llm-client/infrastructure/basic-design.md REQ-LC-015
対応要件: REQ-LC-015（compacted フラグ — subtype="compact" イベント検出）

IMPL-4 修正検証: compacted フラグ判定を is_error/num_turns ベースから
event_type="system" かつ subtype="compact" 検出に変更したことを物理確認する。
"""

from __future__ import annotations

import json

from bakufu.infrastructure.llm.claude_code_llm_client import ClaudeCodeLLMClient


def _make_client() -> ClaudeCodeLLMClient:
    """テスト用 ClaudeCodeLLMClient（タイムアウトは任意値）。"""
    return ClaudeCodeLLMClient(model_name="claude-opus-4-5", timeout_seconds=30.0)


def _jsonl(*events: dict) -> str:
    """dict のシーケンスを JSONL 文字列に変換する。"""
    return "\n".join(json.dumps(e) for e in events)


class TestParseStreamJsonCompacted:
    """TC-UT-LC-COMPACT-001〜004: _parse_stream_json compacted フラグ検出テスト。"""

    def test_compact_subtype_sets_compacted_true(self) -> None:
        """TC-UT-LC-COMPACT-001: system/compact イベント → compacted=True。

        要件: REQ-LC-015
        IMPL-4: event_type="system" かつ subtype="compact" 検出時に compacted=True になること。
        """
        stdout = _jsonl(
            {"type": "system", "subtype": "compact", "session_id": "sess-001"},
            {"type": "result", "result": "評価結果テキスト", "session_id": "sess-001"},
        )
        client = _make_client()

        response_text, session_id, compacted = client._parse_stream_json(stdout)

        assert compacted is True, "system/compact イベントで compacted が True になっていない"
        assert response_text == "評価結果テキスト"
        assert session_id == "sess-001"

    def test_no_compact_event_compacted_false(self) -> None:
        """TC-UT-LC-COMPACT-002: system/compact なし → compacted=False（デフォルト）。

        要件: REQ-LC-015
        """
        stdout = _jsonl(
            {"type": "result", "result": "通常の応答", "session_id": "sess-002"},
        )
        client = _make_client()

        _, _, compacted = client._parse_stream_json(stdout)

        assert compacted is False, "compact イベントがないのに compacted が True になっている"

    def test_system_event_without_compact_subtype_does_not_set_compacted(self) -> None:
        """TC-UT-LC-COMPACT-003: system イベントでも subtype != compact → compacted=False。

        要件: REQ-LC-015
        旧実装（is_error / num_turns ベース）との差異を物理確認する（IMPL-4 修正検証）。
        subtype が "other" など別の値なら compacted にならないこと。
        """
        stdout = _jsonl(
            {"type": "system", "subtype": "other", "session_id": "sess-003"},
            {"type": "result", "result": "応答", "session_id": "sess-003"},
        )
        client = _make_client()

        _, _, compacted = client._parse_stream_json(stdout)

        assert compacted is False, "subtype が compact 以外なのに compacted が True になっている"

    def test_compact_event_before_result_still_detected(self) -> None:
        """TC-UT-LC-COMPACT-004: compact イベントが result より前にあっても検出される。

        要件: REQ-LC-015
        JSONL ストリームで compact → result の順に届いた場合でも compacted=True であること。
        """
        stdout = _jsonl(
            {"type": "system", "subtype": "compact", "session_id": "sess-004"},
            {"type": "assistant", "content": "中間メッセージ"},
            {"type": "result", "result": "最終応答", "session_id": "sess-004"},
        )
        client = _make_client()

        response_text, _, compacted = client._parse_stream_json(stdout)

        assert compacted is True
        assert response_text == "最終応答"
