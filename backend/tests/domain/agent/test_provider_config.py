"""ProviderConfig VO contract (TC-UT-VO-AG-003 / 004 / 028).

Confirmation I leaves "Adapter implemented in MVP" enforcement to the
application service ``AgentService.hire`` — the VO only checks structural
shape (enum value, model length). The MVP-implementation gate is verified at
the application layer in a future ``feature/agent-service`` test.
"""

from __future__ import annotations

import pytest
from bakufu.domain.agent import ProviderConfig
from bakufu.domain.value_objects import ProviderKind
from pydantic import ValidationError


class TestProviderConfigKindEnum:
    """TC-UT-VO-AG-003 / TC-UT-AG-028 — provider_kind must be a known ProviderKind."""

    @pytest.mark.parametrize("kind", list(ProviderKind))
    def test_accepts_each_canonical_kind(self, kind: ProviderKind) -> None:
        """TC-UT-VO-AG-003: every ProviderKind enum value constructs."""
        config = ProviderConfig(provider_kind=kind, model="x", is_default=True)
        assert config.provider_kind is kind

    def test_rejects_unknown_kind_string(self) -> None:
        """TC-UT-AG-028: provider_kind='UNKNOWN' raises ValidationError."""
        with pytest.raises(ValidationError):
            ProviderConfig.model_validate(
                {"provider_kind": "UNKNOWN_PROVIDER", "model": "x", "is_default": True}
            )


class TestProviderConfigModelBoundary:
    """TC-UT-VO-AG-004 — model length 1〜80."""

    @pytest.mark.parametrize("valid_length", [1, 80])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-VO-AG-004: 1-char and 80-char model construct."""
        config = ProviderConfig(
            provider_kind=ProviderKind.CLAUDE_CODE,
            model="a" * valid_length,
        )
        assert len(config.model) == valid_length

    @pytest.mark.parametrize("invalid_length", [0, 81])
    def test_rejects_outside_boundary(self, invalid_length: int) -> None:
        """TC-UT-VO-AG-004: 0 / 81 model raises ValidationError."""
        with pytest.raises(ValidationError):
            ProviderConfig(
                provider_kind=ProviderKind.CLAUDE_CODE,
                model="a" * invalid_length,
            )

    def test_model_strips_surrounding_whitespace(self) -> None:
        """Confirmation E: model is strip-only (NFC has no behavioral effect on ASCII)."""
        config = ProviderConfig(
            provider_kind=ProviderKind.CLAUDE_CODE,
            model="  sonnet  ",
        )
        assert config.model == "sonnet"
