"""SQLite adapter for :class:`bakufu.application.ports.AgentRepository`.

Implements the §確定 B "delete-then-insert" save flow over three
tables (``agents`` / ``agent_providers`` / ``agent_skills``):

1. ``agents`` UPSERT (id-conflict → name + role + persona +
   archived update; ``prompt_body`` binds through
   :class:`MaskedText` so any embedded API key / OAuth token /
   GitHub PAT is redacted *before* it hits SQLite — Schneier 申し送り
   #3 实適用, applied to the Agent path here).
2. ``agent_providers`` DELETE WHERE agent_id = ?
3. ``agent_providers`` bulk INSERT (one row per ProviderConfig).
4. ``agent_skills`` DELETE WHERE agent_id = ?
5. ``agent_skills`` bulk INSERT (one row per SkillRef).

The repository **never** calls ``session.commit()`` /
``session.rollback()``: the caller-side service runs
``async with session.begin():`` so the five steps above stay in one
transaction (§確定 B Tx 境界の責務分離).

``_to_row`` / ``_from_row`` are kept as private methods on the class
so both directions live next to each other and tests don't accidentally
acquire a public conversion API to depend on (§確定 C).

Two Agent-specific contracts widen the empire / workflow repository
template:

* **§確定 F — :meth:`find_by_name`**: an extra Protocol method that
  scopes the lookup with ``WHERE empire_id = :empire_id AND name =
  :name LIMIT 1``. The implementation deliberately delegates to
  :meth:`find_by_id` once the AgentId is known so the
  ``_from_row`` conversion logic stays single-sourced.
* **§確定 H — masked ``prompt_body`` is irreversible**: hydration
  via :meth:`find_by_id` returns a Persona whose ``prompt_body`` is
  the masked form (e.g. ``<REDACTED:ANTHROPIC_KEY>``). Detecting and
  refusing to dispatch a masked prompt is the application-layer's
  job, frozen as a follow-up under ``feature/llm-adapter``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.agent import Agent, Persona, ProviderConfig, SkillRef
from bakufu.domain.value_objects import (
    AgentId,
    EmpireId,
    ProviderKind,
    Role,
)
from bakufu.infrastructure.persistence.sqlite.tables.agent_providers import (
    AgentProviderRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.agent_skills import (
    AgentSkillRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.agents import AgentRow


class SqliteAgentRepository:
    """SQLite implementation of :class:`AgentRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, agent_id: AgentId) -> Agent | None:
        """SELECT agent + side tables, hydrate via :meth:`_from_row`.

        Returns ``None`` when the agents row is absent. Side-table
        SELECTs use ``ORDER BY provider_kind`` /
        ``ORDER BY skill_id`` so the hydrated lists are deterministic
        — empire-repository BUG-EMR-001 froze this contract; we apply
        it from PR #1 here.
        """
        agent_stmt = select(AgentRow).where(AgentRow.id == agent_id)
        agent_row = (await self._session.execute(agent_stmt)).scalar_one_or_none()
        if agent_row is None:
            return None

        # ORDER BY makes find_by_id deterministic. Without it SQLite
        # returns rows in internal-scan order, which would break
        # ``Agent == Agent`` round-trip equality (the Aggregate
        # compares list-by-list). See basic-design + workflow-repo
        # §BUG-EMR-001 — this PR adopts the resolved contract from
        # day one.
        provider_stmt = (
            select(AgentProviderRow)
            .where(AgentProviderRow.agent_id == agent_id)
            .order_by(AgentProviderRow.provider_kind)
        )
        provider_rows = list((await self._session.execute(provider_stmt)).scalars().all())

        skill_stmt = (
            select(AgentSkillRow)
            .where(AgentSkillRow.agent_id == agent_id)
            .order_by(AgentSkillRow.skill_id)
        )
        skill_rows = list((await self._session.execute(skill_stmt)).scalars().all())

        return self._from_row(agent_row, provider_rows, skill_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM agents``.

        Implementation detail: SQLAlchemy's ``func.count()`` issues a
        proper ``SELECT COUNT(*)`` so SQLite returns one scalar row
        instead of streaming every PK back to Python. This is the
        empire-repository §確定 D 補強 contract continued — Agent
        provider / skill rows can hold hundreds of records once the
        preset library lands, so the pattern matters.
        """
        stmt = select(func.count()).select_from(AgentRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, agent: Agent) -> None:
        """Persist ``agent`` via the §確定 B five-step delete-then-insert.

        The caller is responsible for the surrounding
        ``async with session.begin():`` block; failures inside any
        step propagate untouched so the Unit-of-Work boundary in the
        application service can rollback cleanly.
        """
        agent_row, provider_rows, skill_rows = self._to_row(agent)

        # Step 1: agents UPSERT (id PK, ON CONFLICT update name +
        # role + Persona fields + archived). ``prompt_body`` binds
        # through MaskedText so the masked form lands in the DB even
        # on update.
        upsert_stmt = sqlite_insert(AgentRow).values(agent_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "empire_id": upsert_stmt.excluded.empire_id,
                "name": upsert_stmt.excluded.name,
                "role": upsert_stmt.excluded.role,
                "display_name": upsert_stmt.excluded.display_name,
                "archetype": upsert_stmt.excluded.archetype,
                "prompt_body": upsert_stmt.excluded.prompt_body,
                "archived": upsert_stmt.excluded.archived,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: agent_providers DELETE.
        await self._session.execute(
            delete(AgentProviderRow).where(AgentProviderRow.agent_id == agent.id)
        )

        # Step 3: agent_providers bulk INSERT (skip when no
        # providers — though the Agent invariant requires at least
        # one provider, the defensive empty-skip keeps behavior
        # consistent with the empire / workflow templates).
        if provider_rows:
            await self._session.execute(insert(AgentProviderRow), provider_rows)

        # Step 4: agent_skills DELETE.
        await self._session.execute(delete(AgentSkillRow).where(AgentSkillRow.agent_id == agent.id))

        # Step 5: agent_skills bulk INSERT (skill set may legitimately
        # be empty — Agent allows zero skills).
        if skill_rows:
            await self._session.execute(insert(AgentSkillRow), skill_rows)

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Agent | None:
        """Hydrate the Agent named ``name`` inside ``empire_id`` (§確定 F).

        Two-stage flow: a lightweight ``SELECT id ... LIMIT 1`` to
        locate the AgentId, then delegation to :meth:`find_by_id` so
        the side-table SELECTs + ``_from_row`` conversion stay
        single-sourced (§設計判断補足 "find_by_id 経由で復元する根拠").
        """
        id_stmt = (
            select(AgentRow.id)
            .where(AgentRow.empire_id == empire_id, AgentRow.name == name)
            .limit(1)
        )
        found_id = (await self._session.execute(id_stmt)).scalar_one_or_none()
        if found_id is None:
            return None
        return await self.find_by_id(found_id)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(
        self,
        agent: Agent,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """Split ``agent`` into ``(agent_row, provider_rows, skill_rows)``.

        SQLAlchemy ``Row`` objects are intentionally avoided here so
        the domain layer never gains an accidental dependency on the
        SQLAlchemy type hierarchy. Each returned ``dict`` matches the
        ``mapped_column`` names of the corresponding table verbatim.
        """
        agent_row: dict[str, Any] = {
            "id": agent.id,
            "empire_id": agent.empire_id,
            "name": agent.name,
            "role": agent.role.value,
            "display_name": agent.persona.display_name,
            "archetype": agent.persona.archetype,
            # MaskedText.process_bind_param will redact secrets from
            # this string before json.dumps / VARCHAR storage —
            # Schneier 申し送り #3 实適用.
            "prompt_body": agent.persona.prompt_body,
            "archived": agent.archived,
        }
        provider_rows: list[dict[str, Any]] = [
            {
                "agent_id": agent.id,
                "provider_kind": provider.provider_kind.value,
                "model": provider.model,
                "is_default": provider.is_default,
            }
            for provider in agent.providers
        ]
        skill_rows: list[dict[str, Any]] = [
            {
                "agent_id": agent.id,
                "skill_id": skill.skill_id,
                "name": skill.name,
                "path": skill.path,
            }
            for skill in agent.skills
        ]
        return agent_row, provider_rows, skill_rows

    def _from_row(
        self,
        agent_row: AgentRow,
        provider_rows: list[AgentProviderRow],
        skill_rows: list[AgentSkillRow],
    ) -> Agent:
        """Hydrate an :class:`Agent` Aggregate Root from its three rows.

        ``Agent.model_validate`` re-runs the post-validator so
        Repository-side hydration goes through the same invariant
        checks that ``AgentService.hire()`` does at construction
        time. The contract (§確定 C) is "Repository hydration produces
        a valid Agent or raises".

        §確定 H §不可逆性: ``persona.prompt_body`` carries the
        already-masked text from disk. ``Persona`` accepts any string
        within the length cap so the masked form constructs cleanly,
        but the resulting Agent should not be dispatched to an LLM
        without ``feature/llm-adapter``'s masked-prompt guard.
        """
        persona = Persona(
            display_name=agent_row.display_name,
            archetype=agent_row.archetype,
            prompt_body=agent_row.prompt_body,
        )
        providers = [
            ProviderConfig(
                provider_kind=ProviderKind(row.provider_kind),
                model=row.model,
                is_default=row.is_default,
            )
            for row in provider_rows
        ]
        skills = [
            SkillRef(
                skill_id=row.skill_id,
                name=row.name,
                path=row.path,
            )
            for row in skill_rows
        ]
        return Agent(
            id=agent_row.id,
            empire_id=agent_row.empire_id,
            name=agent_row.name,
            role=Role(agent_row.role),
            persona=persona,
            providers=providers,
            skills=skills,
            archived=agent_row.archived,
        )


__all__ = ["SqliteAgentRepository"]
