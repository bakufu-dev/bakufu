"""Persona VO contract (TC-UT-AG-016 / TC-UT-VO-AG-001 / 002 / 007).

Verifies the display_name / archetype / prompt_body length boundaries plus
the special rule that ``prompt_body`` is NFC-normalized **without** strip
(Confirmation E) so Markdown leading/trailing whitespace survives intact.
"""

from __future__ import annotations

import unicodedata

import pytest
from bakufu.domain.agent import Persona
from bakufu.domain.exceptions import AgentInvariantViolation


class TestPersonaDisplayName:
    """TC-UT-VO-AG-001 / 002 — display_name length 1〜40."""

    @pytest.mark.parametrize("valid_length", [1, 40])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-VO-AG-001: 1-char and 40-char display_name construct."""
        persona = Persona(display_name="a" * valid_length)
        assert len(persona.display_name) == valid_length

    @pytest.mark.parametrize("invalid_length", [0, 41])
    def test_rejects_outside_boundary(self, invalid_length: int) -> None:
        """TC-UT-VO-AG-002: 0 / 41 display_name raises display_name_range."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            Persona(display_name="a" * invalid_length)
        assert excinfo.value.kind == "display_name_range"


class TestPersonaArchetype:
    """TC-UT-VO-AG-007 — archetype 0〜80 (Boy Scout补完)."""

    @pytest.mark.parametrize("valid_length", [0, 80])
    def test_accepts_zero_or_eighty(self, valid_length: int) -> None:
        """TC-UT-VO-AG-007: 0-char and 80-char archetype construct."""
        persona = Persona(display_name="p", archetype="a" * valid_length)
        assert len(persona.archetype) == valid_length

    def test_rejects_eightyone_chars(self) -> None:
        """TC-UT-VO-AG-007: 81-char archetype raises archetype_too_long."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            Persona(display_name="p", archetype="a" * 81)
        assert excinfo.value.kind == "archetype_too_long"


class TestPersonaPromptBody:
    """TC-UT-AG-016 — prompt_body 0〜10000 + NFC only (no strip)."""

    @pytest.mark.parametrize("valid_length", [0, 10_000])
    def test_accepts_zero_or_ten_thousand_chars(self, valid_length: int) -> None:
        """TC-UT-AG-016: 0-char and 10000-char prompt_body construct."""
        persona = Persona(display_name="p", prompt_body="a" * valid_length)
        assert len(persona.prompt_body) == valid_length

    def test_rejects_ten_thousand_one_chars(self) -> None:
        """TC-UT-AG-016: 10001-char prompt_body raises persona_too_long."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            Persona(display_name="p", prompt_body="a" * 10_001)
        assert excinfo.value.kind == "persona_too_long"

    def test_prompt_body_preserves_leading_and_trailing_whitespace(self) -> None:
        """Confirmation E: prompt_body is NFC-only, NOT strip — Markdown whitespace survives."""
        markdown = "\n\n  # heading  \nbody\n  \n"
        persona = Persona(display_name="p", prompt_body=markdown)
        assert persona.prompt_body == unicodedata.normalize("NFC", markdown)

    def test_prompt_body_normalizes_decomposed_kana(self) -> None:
        """Confirmation E: prompt_body still goes through NFC for canonical equality."""
        composed = "がが"
        decomposed = unicodedata.normalize("NFD", composed)
        persona = Persona(display_name="p", prompt_body=decomposed)
        assert persona.prompt_body == composed
