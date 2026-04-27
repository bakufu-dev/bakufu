"""Application-layer responsibility lock (TC-UT-AG-029 / REQ-AG R1-B).

Confirmation R1-B in the requirements analysis says **name uniqueness inside
an Empire is the application service's job**, not the aggregate's. Two
Agents with identical names but different ids must construct cleanly at the
domain layer; the duplicate check belongs in ``AgentService.hire``.

These tests lock that contract so a future refactor cannot silently move the
check into the aggregate (which would give a false sense of "name uniqueness
is now defended at multiple layers" while breaking the layered design).
"""

from __future__ import annotations

from tests.factories.agent import make_agent


class TestNameUniquenessLeftToApplicationLayer:
    """TC-UT-AG-029 — Agent aggregate does NOT enforce intra-Empire name uniqueness."""

    def test_two_agents_with_same_name_but_different_ids_construct(self) -> None:
        """REQ-AG R1-B: Aggregate accepts duplicate names — uniqueness lives in AgentService."""
        a1 = make_agent(name="ダリオ")
        a2 = make_agent(name="ダリオ")
        # Both Agents construct successfully and carry distinct ids.
        assert a1.name == a2.name and a1.id != a2.id
