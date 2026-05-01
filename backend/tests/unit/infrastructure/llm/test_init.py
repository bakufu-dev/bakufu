"""§確定G 公開 API 制限テスト（TC-UT-INIT-001）.

Issue: #144
"""
from __future__ import annotations

import pytest


class TestPublicApiRestriction:
    """TC-UT-INIT-001: AnthropicLLMClient / OpenAILLMClient.

    bakufu.infrastructure.llm から直接 import できない。
    """

    def test_anthropic_client_not_exported_from_init(self) -> None:
        """TC-UT-INIT-001a: AnthropicLLMClient は bakufu.infrastructure.llm から import 不可。"""
        from bakufu.infrastructure.llm import __all__ as llm_all
        assert "AnthropicLLMClient" not in llm_all

    def test_openai_client_not_exported_from_init(self) -> None:
        """TC-UT-INIT-001b: OpenAILLMClient は bakufu.infrastructure.llm から import 不可。"""
        from bakufu.infrastructure.llm import __all__ as llm_all
        assert "OpenAILLMClient" not in llm_all

    def test_only_factory_config_provider_exported(self) -> None:
        """TC-UT-INIT-001c: __all__ は設計書で確定した 3 シンボルのみ。"""
        from bakufu.infrastructure.llm import __all__ as llm_all
        expected = {"LLMClientConfig", "LLMProviderEnum", "llm_client_factory"}
        assert set(llm_all) == expected

    def test_anthropic_client_import_raises_error(self) -> None:
        """TC-UT-INIT-001d: AnthropicLLMClient の直接 import が失敗する。

        `from bakufu.infrastructure.llm import AnthropicLLMClient` raises error.
        """
        import bakufu.infrastructure.llm as _llm_pkg

        with pytest.raises(AttributeError):
            _ = _llm_pkg.AnthropicLLMClient  # type: ignore[attr-defined]
