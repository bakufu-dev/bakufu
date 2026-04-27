"""Aggregate-level invariant helpers for :class:`Agent`.

Each helper is a **module-level pure function** so tests can ``import`` and
invoke directly — same testability pattern Norman / Steve approved for the
workflow package's ``dag_validators.py``. The Aggregate Root in
:mod:`bakufu.domain.agent.agent` stays a thin dispatch over them; rule
changes touch only the helper, never the orchestration code.

Helpers (run in this order in :class:`Agent.model_validator`):

1. :func:`_validate_provider_capacity` — ``1 ≤ len(providers) ≤ 10``
2. :func:`_validate_provider_kind_unique` — no duplicate ``provider_kind``
3. :func:`_validate_default_provider_count` — exactly one ``is_default=True``
4. :func:`_validate_skill_capacity` — ``len(skills) ≤ 20``
5. :func:`_validate_skill_id_unique` — no duplicate ``skill_id``

Naming follows the workflow precedent ``_validate_*_unique`` for collection
uniqueness checks (Steve's twin-defense symmetry rule from PR #16).
"""

from __future__ import annotations

from bakufu.domain.agent.value_objects import ProviderConfig, SkillRef
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind, SkillId

# Confirmation C: capacity bounds.
MIN_PROVIDERS: int = 1
MAX_PROVIDERS: int = 10
MAX_SKILLS: int = 20


def _validate_provider_capacity(providers: list[ProviderConfig]) -> None:
    """T2-DoS guard + REQ-AG-001 contract (1 件以上、上限 10 件)."""
    count = len(providers)
    if count < MIN_PROVIDERS:
        raise AgentInvariantViolation(
            kind="no_provider",
            message="[FAIL] Agent must have at least one provider",
            detail={"providers_count": count, "min_providers": MIN_PROVIDERS},
        )
    if count > MAX_PROVIDERS:
        raise AgentInvariantViolation(
            kind="provider_capacity_exceeded",
            message=(
                f"[FAIL] Agent invariant violation: providers capacity "
                f"{MAX_PROVIDERS} exceeded (got {count})"
            ),
            detail={"providers_count": count, "max_providers": MAX_PROVIDERS},
        )


def _validate_provider_kind_unique(providers: list[ProviderConfig]) -> None:
    """No two ProviderConfig may share ``provider_kind`` (MSG-AG-004)."""
    seen: set[ProviderKind] = set()
    for provider in providers:
        if provider.provider_kind in seen:
            raise AgentInvariantViolation(
                kind="provider_duplicate",
                message=f"[FAIL] Duplicate provider_kind: {provider.provider_kind}",
                detail={"provider_kind": str(provider.provider_kind)},
            )
        seen.add(provider.provider_kind)


def _validate_default_provider_count(providers: list[ProviderConfig]) -> None:
    """Exactly one provider must be marked ``is_default=True`` (MSG-AG-003)."""
    count = sum(1 for provider in providers if provider.is_default)
    if count != 1:
        raise AgentInvariantViolation(
            kind="default_not_unique",
            message=(f"[FAIL] Exactly one provider must have is_default=True (got {count})"),
            detail={"default_count": count},
        )


def _validate_skill_capacity(skills: list[SkillRef]) -> None:
    """Cap skills at 20 (REQ-AG-001 / Confirmation C)."""
    count = len(skills)
    if count > MAX_SKILLS:
        raise AgentInvariantViolation(
            kind="skill_capacity_exceeded",
            message=(
                f"[FAIL] Agent invariant violation: skills capacity "
                f"{MAX_SKILLS} exceeded (got {count})"
            ),
            detail={"skills_count": count, "max_skills": MAX_SKILLS},
        )


def _validate_skill_id_unique(skills: list[SkillRef]) -> None:
    """No two SkillRef may share ``skill_id`` (MSG-AG-007).

    Naming mirrors workflow's ``_validate_stage_id_unique`` /
    ``_validate_transition_id_unique`` symmetry that Steve required in
    PR #16: every collection contract that says "no duplicate id" gets a
    dedicated helper so the Boy Scout rule ("first leak breaks all") never
    catches us off-guard on the next aggregate.
    """
    seen: set[SkillId] = set()
    for skill in skills:
        if skill.skill_id in seen:
            raise AgentInvariantViolation(
                kind="skill_duplicate",
                message=f"[FAIL] Skill already added: skill_id={skill.skill_id}",
                detail={"skill_id": str(skill.skill_id)},
            )
        seen.add(skill.skill_id)


__all__ = [
    "MAX_PROVIDERS",
    "MAX_SKILLS",
    "MIN_PROVIDERS",
    "_validate_default_provider_count",
    "_validate_provider_capacity",
    "_validate_provider_kind_unique",
    "_validate_skill_capacity",
    "_validate_skill_id_unique",
]
