"""Construction & name normalization (TC-UT-AG-001 / 002 / 012 / 030).

Covers REQ-AG-001 minimal contracts and the NFC + strip pipeline shared with
empire / workflow.
"""

from __future__ import annotations

import unicodedata

import pytest
from bakufu.domain.exceptions import AgentInvariantViolation

from tests.factories.agent import make_agent


class TestAgentConstruction:
    """REQ-AG-001 / TC-UT-AG-001 — minimal Agent contract."""

    def test_default_factory_yields_one_provider_no_skills(self) -> None:
        """TC-UT-AG-001: Agent built via factory has 1 provider, 0 skills, archived=False."""
        agent = make_agent()
        assert len(agent.providers) == 1 and len(agent.skills) == 0 and agent.archived is False


class TestAgentNameBoundaries:
    """REQ-AG-001 / TC-UT-AG-002 — name length 1〜40."""

    @pytest.mark.parametrize("valid_length", [1, 40])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-AG-002: 1-char and 40-char names construct successfully."""
        agent = make_agent(name="a" * valid_length)
        assert len(agent.name) == valid_length

    @pytest.mark.parametrize("invalid_name", ["", "a" * 41, "   "])
    def test_rejects_zero_fortyone_or_whitespace_only(self, invalid_name: str) -> None:
        """TC-UT-AG-002: 0-char / 41-char / whitespace-only names raise."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(name=invalid_name)
        assert excinfo.value.kind == "name_range"


class TestAgentNameNormalization:
    """TC-UT-AG-012 — NFC + strip pipeline shared with empire / workflow."""

    def test_decomposed_kana_normalized_to_nfc(self) -> None:
        """TC-UT-AG-012: decomposed kana with dakuten (e.g. 'がが') is normalized."""
        composed = "がが"
        decomposed = unicodedata.normalize("NFD", composed)
        assert decomposed != composed  # sanity
        agent = make_agent(name=decomposed)
        assert agent.name == composed

    def test_surrounding_whitespace_stripped(self) -> None:
        """TC-UT-AG-012: leading/trailing whitespace is stripped."""
        agent = make_agent(name="  ダリオ  ")
        assert agent.name == "ダリオ"
