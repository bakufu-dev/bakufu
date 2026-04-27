"""Agent Repository port.

Per ``docs/features/agent-repository/detailed-design.md`` §確定 A
(empire-repo / workflow-repo テンプレート 100% 継承) plus §確定 F
(``find_by_name`` 第 4 method 追加 — the **first** Repository in the
codebase to extend the canonical 3-method surface):

* Protocol class with **no** ``@runtime_checkable`` decorator —
  Python 3.12 ``typing.Protocol`` duck typing is enough.
* Every method declared ``async def`` (async-first contract).
* Argument and return types come exclusively from
  :mod:`bakufu.domain` — no SQLAlchemy types leak across the port.
* ``find_by_name`` takes ``empire_id`` first because the "name unique
  within an Empire" invariant is Empire-scoped (§確定 F (a)
  rejected the global-scope alternative). Argument order **scope →
  identifier** is the natural reading.
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.agent import Agent
from bakufu.domain.value_objects import AgentId, EmpireId


class AgentRepository(Protocol):
    """Persistence contract for the :class:`Agent` Aggregate Root.

    The application layer (``AgentService.hire`` etc., future PR)
    consumes this Protocol via dependency injection; the SQLite
    implementation lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.agent_repository`.
    """

    async def find_by_id(self, agent_id: AgentId) -> Agent | None:
        """Hydrate the Agent whose primary key equals ``agent_id``.

        Returns ``None`` when the row is absent. SQLAlchemy / driver /
        ``pydantic.ValidationError`` exceptions propagate untouched so
        the application service's Unit-of-Work boundary can choose
        between rollback and surfaced error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM agents``.

        Application services use this for bulk-introspection
        (e.g. monitoring dashboards). Deciding what the count means is
        the application layer's call (§確定 D).
        """
        ...

    async def save(self, agent: Agent) -> None:
        """Persist ``agent`` via the §確定 B delete-then-insert flow.

        The implementation must run the five-step sequence (UPSERT
        agents → DELETE agent_providers → bulk INSERT providers →
        DELETE agent_skills → bulk INSERT skills) within the
        **caller-managed** transaction. Repositories never call
        ``session.commit()`` / ``session.rollback()``; the application
        service owns the Unit-of-Work boundary.
        """
        ...

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Agent | None:
        """Hydrate the Agent named ``name`` inside Empire ``empire_id`` (§確定 F).

        The "name unique within an Empire" invariant is Empire-scoped
        per ``docs/features/agent/detailed-design.md`` so the
        Repository takes ``empire_id`` first. Implementations must
        emit ``WHERE empire_id = :empire_id AND name = :name LIMIT 1``
        rather than fetching all Agents and filtering in Python (the
        latter is explicitly rejected as a memory / N+1 pitfall in
        §確定 F (c)).

        Returns ``None`` when no Agent matches. Implementations are
        expected to delegate the side-table SELECTs to
        :meth:`find_by_id` once the AgentId is known so the
        ``_to_row`` / ``_from_row`` conversion logic is not duplicated
        (§設計判断補足).
        """
        ...


__all__ = ["AgentRepository"]
