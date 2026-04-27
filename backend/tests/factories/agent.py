"""Factories for the Agent aggregate, its entities, and its VOs.

Per ``docs/features/agent/test-design.md``. Mirrors the empire / workflow
pattern: every factory returns a *valid* default instance built through the
production constructor, allows keyword overrides, and registers the result
in a :class:`WeakValueDictionary` so :func:`is_synthetic` can later flag
test-built objects without mutating the frozen Pydantic models.

``DEFAULT_SKILL_PATH`` and the ``BAKUFU_DATA_DIR`` env var (set by
``conftest.py``) together make every default ``SkillRef`` pass H1〜H10 so
tests focused on Agent behavior do not have to thread path payloads through
their setup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.agent import (
    Agent,
    Persona,
    ProviderConfig,
    SkillRef,
)
from bakufu.domain.value_objects import ProviderKind, Role
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# Module-scope registry. Values are kept weakly so GC pressure stays neutral.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()

# Default SkillRef.path that satisfies H1〜H10 when ``BAKUFU_DATA_DIR`` is set.
DEFAULT_SKILL_PATH: str = "bakufu-data/skills/sample-skill.md"


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module."""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """Record ``instance`` in the synthetic registry."""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------
def make_persona(
    *,
    display_name: str = "テストペルソナ",
    archetype: str = "review-focused",
    prompt_body: str = "You are a thorough reviewer.",
) -> Persona:
    """Build a valid :class:`Persona`."""
    persona = Persona(
        display_name=display_name,
        archetype=archetype,
        prompt_body=prompt_body,
    )
    _register(persona)
    return persona


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------
def make_provider_config(
    *,
    provider_kind: ProviderKind = ProviderKind.CLAUDE_CODE,
    model: str = "sonnet-4.5",
    is_default: bool = True,
) -> ProviderConfig:
    """Build a valid :class:`ProviderConfig` with ``is_default=True`` by default."""
    config = ProviderConfig(
        provider_kind=provider_kind,
        model=model,
        is_default=is_default,
    )
    _register(config)
    return config


# ---------------------------------------------------------------------------
# SkillRef
# ---------------------------------------------------------------------------
def make_skill_ref(
    *,
    skill_id: UUID | None = None,
    name: str = "sample-skill",
    path: str = DEFAULT_SKILL_PATH,
) -> SkillRef:
    """Build a valid :class:`SkillRef`. Requires ``BAKUFU_DATA_DIR`` env var (H10)."""
    ref = SkillRef(
        skill_id=skill_id if skill_id is not None else uuid4(),
        name=name,
        path=path,
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
def make_agent(
    *,
    agent_id: UUID | None = None,
    name: str = "テストエージェント",
    persona: Persona | None = None,
    role: Role = Role.DEVELOPER,
    providers: Sequence[ProviderConfig] | None = None,
    skills: Sequence[SkillRef] | None = None,
    archived: bool = False,
) -> Agent:
    """Build a valid :class:`Agent`.

    With no overrides yields the simplest valid Agent: 1 ProviderConfig with
    ``is_default=True``, no skills, ``archived=False``.
    """
    if persona is None:
        persona = make_persona()
    if providers is None:
        providers = [make_provider_config()]
    if skills is None:
        skills = []
    agent = Agent(
        id=agent_id if agent_id is not None else uuid4(),
        name=name,
        persona=persona,
        role=role,
        providers=list(providers),
        skills=list(skills),
        archived=archived,
    )
    _register(agent)
    return agent


def make_archived_agent(**overrides: object) -> Agent:
    """Build an Agent with ``archived=True`` for idempotency test setups."""
    return make_agent(archived=True, **overrides)  # pyright: ignore[reportArgumentType]


__all__ = [
    "DEFAULT_SKILL_PATH",
    "is_synthetic",
    "make_agent",
    "make_archived_agent",
    "make_persona",
    "make_provider_config",
    "make_skill_ref",
]
