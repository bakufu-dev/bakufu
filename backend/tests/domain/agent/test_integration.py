"""Aggregate-internal lifecycle integration (TC-IT-AG-001 / 002).

Same pattern as ``empire`` / ``workflow`` integration suites: domain layer
has no public entry point, so we validate the round-trip behavior across
the Aggregate's mutator chain (set_default_provider → add_skill →
remove_skill → archive) plus the resilience scenario where a mid-chain
failure leaves the original aggregate intact.
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)


class TestAgentLifecycleIntegration:
    """TC-IT-AG-001 / 002 — full lifecycle + resilience."""

    def test_full_lifecycle_round_trip(self) -> None:
        """TC-IT-AG-001: hire → add_skill → switch default → remove_skill → archive.

        Pre-state: 2-provider Agent (CLAUDE_CODE default + CODEX non-default),
        1 skill. Walk the full mutator chain and verify the final shape.
        """
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
        ]
        skill = make_skill_ref()
        agent = make_agent(providers=providers, skills=[skill])

        # 1) Switch the default to CODEX.
        switched = agent.set_default_provider(ProviderKind.CODEX)
        codex = next(p for p in switched.providers if p.provider_kind is ProviderKind.CODEX)
        assert codex.is_default is True

        # 2) Add a second skill.
        new_skill = make_skill_ref(name="planner", path="bakufu-data/skills/planner.md")
        with_two_skills = switched.add_skill(new_skill)
        assert len(with_two_skills.skills) == 2

        # 3) Remove the original skill.
        with_one_skill = with_two_skills.remove_skill(skill.skill_id)
        assert len(with_one_skill.skills) == 1
        assert with_one_skill.skills[0].skill_id == new_skill.skill_id

        # 4) Archive the agent — Confirmation D returns a *new* instance.
        archived = with_one_skill.archive()
        assert archived.archived is True and archived is not with_one_skill

    def test_failed_set_default_does_not_block_subsequent_operations(self) -> None:
        """TC-IT-AG-002: a failed set_default_provider leaves Agent ready for further changes."""
        agent = make_agent()

        # 1) Switching to an unregistered kind fails; original stays unchanged.
        with pytest.raises(AgentInvariantViolation):
            agent.set_default_provider(ProviderKind.GEMINI)
        assert len(agent.providers) == 1

        # 2) add_skill then succeeds against the unchanged aggregate.
        new_skill = make_skill_ref()
        with_skill = agent.add_skill(new_skill)
        assert len(with_skill.skills) == 1

        # 3) archive() then succeeds against that further-mutated aggregate.
        archived = with_skill.archive()
        assert archived.archived is True
