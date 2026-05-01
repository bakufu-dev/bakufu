"""LLM クライアント Characterization テスト.

Issue: #144

RUN_CHARACTERIZATION=1 の場合のみ実行する。本流 CI からは除外。
実行には BAKUFU_ANTHROPIC_API_KEY と BAKUFU_OPENAI_API_KEY が必要。

Usage:
    RUN_CHARACTERIZATION=1 \\
    BAKUFU_ANTHROPIC_API_KEY=sk-ant-xxx \\
    BAKUFU_OPENAI_API_KEY=sk-xxx \\
    pytest tests/characterization/test_llm_client_characterization.py -v
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

# RUN_CHARACTERIZATION=1 でなければ全テストをスキップ
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_CHARACTERIZATION") != "1",
    reason="RUN_CHARACTERIZATION=1 を設定した場合のみ実行する",
)

_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "characterization" / "raw" / "llm_client"
_SCHEMA_DIR = Path(__file__).parents[1] / "fixtures" / "characterization" / "schema" / "llm_client"


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


class TestAnthropicCharacterization:
    """Anthropic API の実レスポンスを raw fixture として保存する。"""

    async def test_capture_anthropic_success(self) -> None:
        """Anthropic 正常応答を anthropic_complete_success.json に保存する。"""
        import anthropic as anthropic_sdk

        api_key = os.environ["BAKUFU_ANTHROPIC_API_KEY"]
        client = anthropic_sdk.AsyncAnthropic(api_key=api_key)

        _prompt = "Reply with exactly: LLMクライアント基盤の動作確認テスト応答です。"
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=64,
            messages=[{"role": "user", "content": _prompt}],
        )

        raw_data = response.model_dump()
        # API キーをマスク
        raw_data["_meta"] = {
            "captured_at": _now_utc(),
            "endpoint": "https://api.anthropic.com/v1/messages",
            "api_version": "2023-06-01",
            "sdk_version": f"anthropic=={anthropic_sdk.__version__}",
        }
        _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        (_FIXTURES_DIR / "anthropic_complete_success.json").write_text(
            json.dumps(raw_data, ensure_ascii=False, indent=2)
        )

    async def test_capture_anthropic_no_text(self) -> None:
        """TextBlock なし応答は tool_use のみの応答でシミュレート（合成フィクスチャ確認）。"""
        # tool_use 応答は通常 API では取得困難なため合成フィクスチャを使用
        # 既存の anthropic_complete_no_text.json は構造が正しいことを確認
        fixture_path = _FIXTURES_DIR / "anthropic_complete_no_text.json"
        assert fixture_path.exists()
        data = json.loads(fixture_path.read_text())
        assert "_meta" in data
        assert any(block["type"] == "tool_use" for block in data["content"])


class TestOpenAICharacterization:
    """OpenAI API の実レスポンスを raw fixture として保存する。"""

    async def test_capture_openai_success(self) -> None:
        """OpenAI 正常応答を openai_complete_success.json に保存する。"""
        import openai as openai_sdk

        api_key = os.environ["BAKUFU_OPENAI_API_KEY"]
        client = openai_sdk.AsyncOpenAI(api_key=api_key)

        _prompt = "Reply with exactly: LLMクライアント基盤の動作確認テスト応答です。"
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_completion_tokens=64,
            messages=[{"role": "user", "content": _prompt}],
        )

        raw_data = response.model_dump()
        raw_data["_meta"] = {
            "captured_at": _now_utc(),
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "api_version": "v1",
            "sdk_version": f"openai=={openai_sdk.__version__}",
        }
        _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        (_FIXTURES_DIR / "openai_complete_success.json").write_text(
            json.dumps(raw_data, ensure_ascii=False, indent=2)
        )
