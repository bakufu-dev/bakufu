"""Mutators (REQ-AG-002 / 003 / 004) + pre-validate rollback.

Covers TC-UT-AG-005 / 006 / 007 / 008 / 009 / 017 / 019 / 022〜024.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)


class TestSetDefaultProvider:
    """REQ-AG-002 / TC-UT-AG-005 / 006 / 017."""

    def test_switches_default_to_target_kind(self) -> None:
        """TC-UT-AG-005: set_default_provider promotes the target to default."""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
        ]
        agent = make_agent(providers=providers)
        updated = agent.set_default_provider(ProviderKind.CODEX)
        codex = next(p for p in updated.providers if p.provider_kind is ProviderKind.CODEX)
        assert codex.is_default is True

    def test_demotes_previously_default_provider(self) -> None:
        """TC-UT-AG-017: switching default flips the previously-default flag to False."""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
            make_provider_config(provider_kind=ProviderKind.GEMINI, is_default=False),
        ]
        agent = make_agent(providers=providers)
        updated = agent.set_default_provider(ProviderKind.CODEX)
        non_codex_defaults = [
            p
            for p in updated.providers
            if p.provider_kind is not ProviderKind.CODEX and p.is_default
        ]
        assert non_codex_defaults == []

    def test_unknown_kind_raises_provider_not_found(self) -> None:
        """TC-UT-AG-006: switching to a non-registered kind raises provider_not_found."""
        agent = make_agent()
        with pytest.raises(AgentInvariantViolation) as excinfo:
            agent.set_default_provider(ProviderKind.GEMINI)
        assert excinfo.value.kind == "provider_not_found"


class TestAddSkill:
    """REQ-AG-003 / TC-UT-AG-007 / 008."""

    def test_appends_to_skills_list(self) -> None:
        """TC-UT-AG-007: add_skill returns a new Agent with the skill appended."""
        agent = make_agent()
        skill = make_skill_ref(name="reviewer", path="bakufu-data/skills/reviewer.md")
        updated = agent.add_skill(skill)
        assert len(updated.skills) == 1 and updated.skills[0].skill_id == skill.skill_id

    def test_does_not_mutate_original(self) -> None:
        """TC-UT-AG-007: caller's Agent stays empty after add_skill path."""
        agent = make_agent()
        agent.add_skill(make_skill_ref())
        assert agent.skills == []

    def test_duplicate_skill_id_raises_skill_duplicate(self) -> None:
        """TC-UT-AG-008: add_skill with existing skill_id raises skill_duplicate."""
        skill = make_skill_ref()
        agent = make_agent(skills=[skill])
        with pytest.raises(AgentInvariantViolation) as excinfo:
            agent.add_skill(make_skill_ref(skill_id=skill.skill_id, name="dup"))
        assert excinfo.value.kind == "skill_duplicate"


class TestRemoveSkill:
    """REQ-AG-004 / TC-UT-AG-009 / 019."""

    def test_drops_target_skill(self) -> None:
        """TC-UT-AG-009: remove_skill returns a new Agent without the target skill."""
        s1 = make_skill_ref(name="a", path="bakufu-data/skills/a.md")
        s2 = make_skill_ref(name="b", path="bakufu-data/skills/b.md")
        agent = make_agent(skills=[s1, s2])
        updated = agent.remove_skill(s1.skill_id)
        assert len(updated.skills) == 1 and updated.skills[0].skill_id == s2.skill_id

    def test_unknown_skill_id_raises_skill_not_found(self) -> None:
        """TC-UT-AG-019: remove_skill with unregistered skill_id raises skill_not_found."""
        agent = make_agent()
        with pytest.raises(AgentInvariantViolation) as excinfo:
            agent.remove_skill(uuid4())
        assert excinfo.value.kind == "skill_not_found"


class TestPreValidateRollback:
    """Confirmation A / TC-UT-AG-022〜024 — failed mutators leave caller unchanged."""

    def test_failed_set_default_provider_keeps_original(self) -> None:
        """TC-UT-AG-022: failed set_default_provider does not mutate caller's Agent."""
        agent = make_agent()
        original_defaults = [p.provider_kind for p in agent.providers if p.is_default]
        with pytest.raises(AgentInvariantViolation):
            agent.set_default_provider(ProviderKind.GEMINI)
        unchanged = [p.provider_kind for p in agent.providers if p.is_default]
        assert unchanged == original_defaults

    def test_failed_add_skill_keeps_original(self) -> None:
        """TC-UT-AG-023: failed add_skill does not grow caller's skills."""
        skill = make_skill_ref()
        agent = make_agent(skills=[skill])
        with pytest.raises(AgentInvariantViolation):
            agent.add_skill(make_skill_ref(skill_id=skill.skill_id, name="dup"))
        assert len(agent.skills) == 1

    def test_failed_remove_skill_keeps_original(self) -> None:
        """TC-UT-AG-024: failed remove_skill does not shrink caller's skills."""
        skill = make_skill_ref()
        agent = make_agent(skills=[skill])
        with pytest.raises(AgentInvariantViolation):
            agent.remove_skill(uuid4())
        assert len(agent.skills) == 1
