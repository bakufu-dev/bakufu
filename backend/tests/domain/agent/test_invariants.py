"""Aggregate-level invariants (REQ-AG-001 / 005 / 006).

Covers TC-UT-AG-003 / 004 / 013〜015 / 018 / 021. Each invariant lives in its
own ``Test*`` class so failures cluster by which collection contract was
violated. Capacity overflow paths use ``model_construct`` to bypass the Agent
constructor's eager Pydantic validation when the test needs to feed the
helper an already-built collection.
"""

from __future__ import annotations

import pytest
from bakufu.domain.agent.aggregate_validators import MAX_PROVIDERS, MAX_SKILLS
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)


class TestProvidersRequired:
    """TC-UT-AG-013 — providers must contain at least one entry."""

    def test_empty_providers_raises_no_provider(self) -> None:
        """TC-UT-AG-013: providers=[] raises no_provider."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=[])
        assert excinfo.value.kind == "no_provider"


class TestProviderCapacity:
    """TC-UT-AG-014 — providers ≤ MAX_PROVIDERS (Confirmation C)."""

    def test_overflow_raises_provider_capacity_exceeded(self) -> None:
        """TC-UT-AG-014: 11 providers raises provider_capacity_exceeded."""
        # 10 with is_default=False + 1 with is_default=True so the
        # default-count helper would pass (it runs after capacity).
        providers = [
            make_provider_config(provider_kind=kind, is_default=False)
            for kind in list(ProviderKind)[:6]
        ]
        # Append duplicates beyond MAX_PROVIDERS by varying model strings
        # (we just need >MAX_PROVIDERS entries; provider_kind uniqueness
        # check would catch it but capacity runs first).
        providers.extend(
            make_provider_config(
                provider_kind=ProviderKind.CLAUDE_CODE,
                model=f"sonnet-{i}",
                is_default=False,
            )
            for i in range(MAX_PROVIDERS - 5)  # tops out beyond MAX
        )
        # Need at least one default — append one more.
        providers.append(make_provider_config(is_default=True))
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "provider_capacity_exceeded"


class TestProviderKindUnique:
    """TC-UT-AG-015 — provider_kind must be unique across providers."""

    def test_duplicate_provider_kind_raises_provider_duplicate(self) -> None:
        """TC-UT-AG-015: two ProviderConfigs with same provider_kind raises."""
        p1 = make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True)
        p2 = make_provider_config(
            provider_kind=ProviderKind.CLAUDE_CODE, model="opus", is_default=False
        )
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=[p1, p2])
        assert excinfo.value.kind == "provider_duplicate"


class TestDefaultProviderCount:
    """TC-UT-AG-003 / 004 / 021 — exactly one is_default=True."""

    def test_zero_defaults_raises_default_not_unique(self) -> None:
        """TC-UT-AG-003: all is_default=False raises default_not_unique with count=0."""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=False),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "default_not_unique"
        assert excinfo.value.detail.get("default_count") == 0

    def test_two_defaults_raises_default_not_unique(self) -> None:
        """TC-UT-AG-004: two is_default=True raises default_not_unique with count=2."""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=True),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "default_not_unique"
        assert excinfo.value.detail.get("default_count") == 2

    @pytest.mark.parametrize(
        ("default_flags", "expected_count"),
        [
            ([False, False, False], 0),
            ([True, True, False], 2),
            ([True, True, True], 3),
        ],
    )
    def test_count_outside_one_raises(self, default_flags: list[bool], expected_count: int) -> None:
        """TC-UT-AG-021: 0 / 2 / 3 default counts all raise (boundary all sweep)."""
        kinds = [ProviderKind.CLAUDE_CODE, ProviderKind.CODEX, ProviderKind.GEMINI]
        providers = [
            make_provider_config(provider_kind=kind, is_default=flag)
            for kind, flag in zip(kinds, default_flags, strict=True)
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "default_not_unique"
        assert excinfo.value.detail.get("default_count") == expected_count

    def test_exactly_one_default_succeeds(self) -> None:
        """TC-UT-AG-021: exactly one is_default=True (boundary success case)."""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
            make_provider_config(provider_kind=ProviderKind.GEMINI, is_default=False),
        ]
        agent = make_agent(providers=providers)
        defaults = [p for p in agent.providers if p.is_default]
        assert len(defaults) == 1


class TestSkillCapacity:
    """TC-UT-AG-018 — skills ≤ MAX_SKILLS (Confirmation C)."""

    def test_overflow_raises_skill_capacity_exceeded(self) -> None:
        """TC-UT-AG-018: MAX_SKILLS+1 skills raises skill_capacity_exceeded."""
        skills = [
            make_skill_ref(name=f"skill-{i:02d}", path=f"bakufu-data/skills/s{i:02d}.md")
            for i in range(MAX_SKILLS + 1)
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(skills=skills)
        assert excinfo.value.kind == "skill_capacity_exceeded"


class TestSkillIdUnique:
    """TC-UT-AG-008 — skill_id must be unique (mirrors stage / transition rule).

    Steve PR #16 symmetry: every "no duplicate id" collection contract gets a
    dedicated helper. The Agent ``_validate_skill_id_unique`` mirrors that.
    """

    def test_duplicate_skill_id_raises_skill_duplicate(self) -> None:
        """TC-UT-AG-008: two SkillRef sharing skill_id raises skill_duplicate."""
        s1 = make_skill_ref()
        s2 = make_skill_ref(skill_id=s1.skill_id, name="another")
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(skills=[s1, s2])
        assert excinfo.value.kind == "skill_duplicate"
