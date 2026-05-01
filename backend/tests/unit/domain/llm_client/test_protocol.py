"""AbstractLLMClient Protocol テスト（TC-UT-PROTO-001〜003）.

Issue: #144
Covers:
  TC-UT-PROTO-001  Protocol stub が完全に機能する
  TC-UT-PROTO-002  complete() シグネチャ検証
  TC-UT-PROTO-003  application/ports/llm_client.py が anthropic/openai を import しない (R1-2)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from bakufu.domain.value_objects.llm import LLMResponse, MessageRole


@pytest.mark.asyncio
class TestProtocolStub:
    """TC-UT-PROTO-001〜002: Protocol stub の機能確認。"""

    async def test_stub_satisfies_protocol(self) -> None:
        """TC-UT-PROTO-001: Protocol を満たす stub が complete() を呼べる。"""
        from tests.factories.llm_client import (
            make_llm_message,
            make_llm_response,
            make_stub_llm_client,
        )

        response = make_llm_response(content="テスト応答")
        stub = make_stub_llm_client(response=response)
        msg = make_llm_message(role=MessageRole.USER, content="テスト入力")

        result = await stub.complete((msg,), 512)
        assert result.content == "テスト応答"

    async def test_complete_signature(self) -> None:
        """TC-UT-PROTO-002: tuple[LLMMessage, ...] + int → LLMResponse 型。"""
        from tests.factories.llm_client import (
            make_llm_message,
            make_llm_response,
            make_stub_llm_client,
        )

        response = make_llm_response()
        stub = make_stub_llm_client(response=response)
        msgs = (
            make_llm_message(role=MessageRole.SYSTEM, content="システムプロンプト"),
            make_llm_message(role=MessageRole.USER, content="ユーザー入力"),
        )
        result = await stub.complete(msgs, max_tokens=512)
        assert isinstance(result, LLMResponse)


class TestSDKNonDependency:
    """TC-UT-PROTO-003: R1-2 domain 層 SDK 非依存物理確認（同期テスト）。"""

    def test_llm_client_port_does_not_import_anthropic_or_openai(self) -> None:
        """TC-UT-PROTO-003: llm_client.py が anthropic / openai を import していない。"""
        src_path = (
            Path(__file__).parents[4] / "src" / "bakufu" / "application" / "ports" / "llm_client.py"
        )
        assert src_path.exists(), f"llm_client.py が見つからない: {src_path}"

        source = src_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        sdk_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("anthropic", "openai"):
                        sdk_imports.append(alias.name)
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (
                    node.module == "anthropic"
                    or node.module.startswith("anthropic.")
                    or node.module == "openai"
                    or node.module.startswith("openai.")
                )
            ):
                sdk_imports.append(node.module)

        assert not sdk_imports, (
            f"llm_client.py が SDK を import している（R1-2 違反）: {sdk_imports}"
        )
