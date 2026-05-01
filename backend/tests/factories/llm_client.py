"""LLM ドメイン層ファクトリ群（domain/test-design.md §外部I/O依存マップ 準拠）.

本モジュールは本番コードから import してはならない。
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from weakref import WeakValueDictionary

from bakufu.domain.value_objects.llm import LLMMessage, LLMResponse, MessageRole
from pydantic import BaseModel

_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    _SYNTHETIC_REGISTRY[id(instance)] = instance


def make_llm_message(
    *,
    role: MessageRole = MessageRole.USER,
    content: str = "テストメッセージ",
) -> LLMMessage:
    """妥当な LLMMessage を構築する。"""
    msg = LLMMessage(role=role, content=content)
    _register(msg)
    return msg


def make_llm_response(
    *,
    content: str = "テスト応答テキスト",
) -> LLMResponse:
    """妥当な LLMResponse を構築する。"""
    resp = LLMResponse(content=content)
    _register(resp)
    return resp


def make_stub_llm_client(*, response: LLMResponse) -> AsyncMock:
    """AbstractLLMClient Protocol を満たす stub を返す。complete() が response を返す。"""
    stub = AsyncMock()
    stub.complete = AsyncMock(return_value=response)
    stub._meta_synthetic = True
    return stub


def make_stub_llm_client_raises(*, exc: Exception) -> AsyncMock:
    """complete() が exc を raise する stub を返す。"""
    stub = AsyncMock()
    stub.complete = AsyncMock(side_effect=exc)
    stub._meta_synthetic = True
    return stub


__all__ = [
    "is_synthetic",
    "make_llm_message",
    "make_llm_response",
    "make_stub_llm_client",
    "make_stub_llm_client_raises",
]
