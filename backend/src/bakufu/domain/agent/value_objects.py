"""Agent-specific Value Objects (Persona / ProviderConfig / SkillRef).

These VOs live in the ``agent/`` package rather than the global
:mod:`bakufu.domain.value_objects` so the file-level boundary mirrors the
responsibility boundary — same pattern Norman approved for the workflow
package. ``SkillId`` and ``ProviderKind`` remain in the global module
because they cross feature boundaries (Skill loader, LLM Adapter).

The Persona / archetype / display_name validations all share the
:func:`bakufu.domain.value_objects.nfc_strip` pipeline (Confirmation B
shared policy carried forward from empire / workflow). ``prompt_body``
applies NFC only — Markdown leading/trailing newlines must be preserved
because downstream renderers depend on them (Confirmation E).

``SkillRef.path`` runs the full H1〜H10 traversal-defense pipeline from
:mod:`bakufu.domain.agent.path_validators`.
"""

from __future__ import annotations

import unicodedata
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bakufu.domain.agent.path_validators import validate_skill_path
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind, SkillId, nfc_strip

# ---------------------------------------------------------------------------
# Persona (Agent feature §確定 E length policy)
# ---------------------------------------------------------------------------
DISPLAY_NAME_MIN: int = 1
DISPLAY_NAME_MAX: int = 40
ARCHETYPE_MAX: int = 80
PROMPT_BODY_MAX: int = 10_000


class Persona(BaseModel):
    """Character / authoring profile attached to an :class:`Agent`.

    ``display_name`` and ``archetype`` go through NFC + strip (Confirmation E).
    ``prompt_body`` only goes through NFC — strip would eat the Markdown
    leading/trailing whitespace that downstream prompt rendering relies on.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    display_name: str
    archetype: str = ""
    prompt_body: str = ""

    @field_validator("display_name", "archetype", mode="before")
    @classmethod
    def _normalize_short_name(cls, value: object) -> object:
        return nfc_strip(value)

    @field_validator("prompt_body", mode="before")
    @classmethod
    def _normalize_prompt_body(cls, value: object) -> object:
        # NFC only — preserves Markdown leading/trailing whitespace.
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_self_invariants(self) -> Self:
        display_name_len = len(self.display_name)
        if not (DISPLAY_NAME_MIN <= display_name_len <= DISPLAY_NAME_MAX):
            raise AgentInvariantViolation(
                kind="display_name_range",
                message=(
                    f"[FAIL] Persona.display_name must be "
                    f"{DISPLAY_NAME_MIN}-{DISPLAY_NAME_MAX} characters "
                    f"(got {display_name_len})"
                ),
                detail={"length": display_name_len},
            )
        archetype_len = len(self.archetype)
        if archetype_len > ARCHETYPE_MAX:
            raise AgentInvariantViolation(
                kind="archetype_too_long",
                message=(
                    f"[FAIL] Persona.archetype must be 0-{ARCHETYPE_MAX} characters "
                    f"(got {archetype_len})"
                ),
                detail={"length": archetype_len},
            )
        prompt_body_len = len(self.prompt_body)
        if prompt_body_len > PROMPT_BODY_MAX:
            raise AgentInvariantViolation(
                kind="persona_too_long",
                message=(
                    f"[FAIL] Persona.prompt_body must be 0-{PROMPT_BODY_MAX} "
                    f"characters (got {prompt_body_len})"
                ),
                detail={"length": prompt_body_len},
            )
        return self


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------
PROVIDER_MODEL_MIN: int = 1
PROVIDER_MODEL_MAX: int = 80


class ProviderConfig(BaseModel):
    """LLM provider configuration entry inside an :class:`Agent`.

    ``provider_kind`` enum ensures only known providers slip through; the
    "is this provider's Adapter implemented in MVP" check belongs to the
    application layer (``AgentService.hire``), not the VO — see Agent
    detailed-design §確定 I for responsibility split.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    provider_kind: ProviderKind
    model: str = Field(min_length=PROVIDER_MODEL_MIN, max_length=PROVIDER_MODEL_MAX)
    is_default: bool = False

    @field_validator("model", mode="before")
    @classmethod
    def _strip_model(cls, value: object) -> object:
        # Strip-only (no NFC) per Confirmation E — model names are ASCII
        # identifiers in practice and applying NFC has no behavioral effect.
        if isinstance(value, str):
            return value.strip()
        return value


# ---------------------------------------------------------------------------
# SkillRef (H1〜H10 path traversal defense delegated to path_validators)
# ---------------------------------------------------------------------------
SKILL_NAME_MIN: int = 1
SKILL_NAME_MAX: int = 80


class SkillRef(BaseModel):
    """Reference to a Skill markdown file inside ``BAKUFU_DATA_DIR/skills/``.

    The path validation contract is comprehensive (10 separate checks); see
    :func:`bakufu.domain.agent.path_validators.validate_skill_path` for the
    full ordered policy.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    skill_id: SkillId
    name: str = Field(min_length=SKILL_NAME_MIN, max_length=SKILL_NAME_MAX)
    path: str

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @field_validator("path", mode="after")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        # H1〜H10 in one shot. Returns the NFC-normalized form so the stored
        # value is canonical (no later code paths see an un-normalized string).
        return validate_skill_path(value)


__all__ = [
    "ARCHETYPE_MAX",
    "DISPLAY_NAME_MAX",
    "DISPLAY_NAME_MIN",
    "PROMPT_BODY_MAX",
    "PROVIDER_MODEL_MAX",
    "PROVIDER_MODEL_MIN",
    "SKILL_NAME_MAX",
    "SKILL_NAME_MIN",
    "Persona",
    "ProviderConfig",
    "SkillRef",
]
