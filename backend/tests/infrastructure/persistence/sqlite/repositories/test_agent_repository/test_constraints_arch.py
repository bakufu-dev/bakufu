"""Agent Repository: DB constraints + arch-test reference.

TC-IT-AGR-007 / TC-UT-AGR-009 — the **partial unique index 二重防衛**
(§確定 G) and the CI Layer 2 arch-test cross-reference.

§確定 G: ``is_default = 1`` rows under the same ``agent_id`` are
forbidden by **two layers**:

1. **Aggregate-level** (``_validate_default_provider_count`` in the
   Agent VO chain) catches the violation at construction time.
2. **DB-level** partial unique index ``uq_agent_providers_default``
   (``WHERE is_default = 1``) physically rejects the INSERT — the
   final defense line for code paths that bypass the Aggregate
   (raw SQL, future Repository implementations that forget the
   check, dump/restore migrations, etc.).

This test exercises **layer 2 in isolation** by writing raw SQL that
sidesteps the Aggregate. A regression that drops the partial index
DDL would let the second INSERT succeed silently — that fails this
test loudly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-AGR-007: partial unique index 二重防衛 (§確定 G)
# ---------------------------------------------------------------------------
class TestPartialUniqueIndexDoubleDefense:
    """TC-IT-AGR-007: ``is_default=1`` x 2 under same agent_id raises IntegrityError.

    The Aggregate's ``_validate_default_provider_count`` is the first
    layer; this test bypasses it by writing raw SQL directly so the
    partial unique index is the only thing standing between us and a
    silent corruption. The first INSERT must succeed; the second must
    raise ``IntegrityError`` (or any ``DBAPIError``-shaped wrapper —
    SQLAlchemy maps SQLite's UNIQUE constraint violation to
    ``IntegrityError``).
    """

    async def test_duplicate_default_provider_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """TC-IT-AGR-007: 2 rows with ``is_default=1`` for same agent_id is rejected by DB."""
        from sqlalchemy.exc import IntegrityError

        # Seed an Agent row so the FK in agent_providers can resolve.
        # We bypass the Repository entirely — raw SQL throughout —
        # to keep the test focused on the DB layer.
        agent_id = uuid4()
        empire_id = seeded_empire_id
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO agents "
                    "(id, empire_id, name, role, display_name, archetype, "
                    "prompt_body, archived) VALUES "
                    "(:id, :empire_id, :name, :role, :display_name, :archetype, "
                    ":prompt_body, :archived)"
                ),
                {
                    "id": agent_id.hex,
                    "empire_id": empire_id.hex,
                    "name": "raw-sql-agent",
                    "role": "DEVELOPER",
                    "display_name": "raw",
                    "archetype": "review-focused",
                    "prompt_body": "no secret",
                    "archived": False,
                },
            )

        # First default provider — should succeed.
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO agent_providers "
                    "(agent_id, provider_kind, model, is_default) VALUES "
                    "(:agent_id, :provider_kind, :model, :is_default)"
                ),
                {
                    "agent_id": agent_id.hex,
                    "provider_kind": "claude_code",
                    "model": "sonnet-4.5",
                    "is_default": True,
                },
            )

        # Second default provider on the same agent_id — distinct
        # provider_kind so the (agent_id, provider_kind) UNIQUE does
        # NOT trip; only the partial unique index on is_default=1
        # should fire.
        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO agent_providers "
                        "(agent_id, provider_kind, model, is_default) VALUES "
                        "(:agent_id, :provider_kind, :model, :is_default)"
                    ),
                    {
                        "agent_id": agent_id.hex,
                        # Different provider_kind — so this is not the
                        # (agent_id, provider_kind) UNIQUE; the
                        # partial index alone is the relevant defense.
                        "provider_kind": "claude_api",
                        "model": "haiku-3.5",
                        "is_default": True,
                    },
                )

    async def test_non_default_duplicates_are_permitted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """``is_default=0`` rows on the same agent_id are NOT subject to the partial index.

        Confirms the partial nature: ``WHERE is_default = 1`` means
        rows with ``is_default = 0`` can coexist freely on the same
        agent_id (subject only to the (agent_id, provider_kind)
        UNIQUE).
        """
        agent_id = uuid4()
        empire_id = seeded_empire_id
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO agents "
                    "(id, empire_id, name, role, display_name, archetype, "
                    "prompt_body, archived) VALUES "
                    "(:id, :empire_id, :name, :role, :display_name, :archetype, "
                    ":prompt_body, :archived)"
                ),
                {
                    "id": agent_id.hex,
                    "empire_id": empire_id.hex,
                    "name": "non-default-test",
                    "role": "DEVELOPER",
                    "display_name": "raw",
                    "archetype": "review-focused",
                    "prompt_body": "no secret",
                    "archived": False,
                },
            )

        # Two providers, both is_default=False, distinct kinds — both succeed.
        async with session_factory() as session, session.begin():
            for kind in ("claude_code", "claude_api"):
                await session.execute(
                    text(
                        "INSERT INTO agent_providers "
                        "(agent_id, provider_kind, model, is_default) VALUES "
                        "(:agent_id, :provider_kind, :model, :is_default)"
                    ),
                    {
                        "agent_id": agent_id.hex,
                        "provider_kind": kind,
                        "model": "model-x",
                        "is_default": False,
                    },
                )

        # Both rows present; partial index did not fire.
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM agent_providers WHERE agent_id = :agent_id"),
                {"agent_id": agent_id.hex},
            )
            count = result.scalar_one()
        assert count == 2


# ---------------------------------------------------------------------------
# TC-IT-AGR-007 補強: same agent_id duplicate (agent_id, provider_kind) → reject
# ---------------------------------------------------------------------------
class TestUniqueAgentProviderPair:
    """The (agent_id, provider_kind) UNIQUE rejects same kind twice."""

    async def test_duplicate_agent_provider_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Same (agent_id, provider_kind) inserted twice → IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        agent_id = uuid4()
        empire_id = seeded_empire_id
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO agents "
                    "(id, empire_id, name, role, display_name, archetype, "
                    "prompt_body, archived) VALUES "
                    "(:id, :empire_id, :name, :role, :display_name, :archetype, "
                    ":prompt_body, :archived)"
                ),
                {
                    "id": agent_id.hex,
                    "empire_id": empire_id.hex,
                    "name": "kind-dup-test",
                    "role": "DEVELOPER",
                    "display_name": "raw",
                    "archetype": "review-focused",
                    "prompt_body": "no secret",
                    "archived": False,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO agent_providers "
                    "(agent_id, provider_kind, model, is_default) VALUES "
                    "(:agent_id, :provider_kind, :model, :is_default)"
                ),
                {
                    "agent_id": agent_id.hex,
                    "provider_kind": "claude_code",
                    "model": "sonnet-4.5",
                    "is_default": False,
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO agent_providers "
                        "(agent_id, provider_kind, model, is_default) VALUES "
                        "(:agent_id, :provider_kind, :model, :is_default)"
                    ),
                    {
                        "agent_id": agent_id.hex,
                        "provider_kind": "claude_code",  # same kind
                        "model": "haiku-3.5",
                        "is_default": False,
                    },
                )


# ---------------------------------------------------------------------------
# TC-UT-AGR-009: Layer 2 arch-test reference — Agent rows registered
# ---------------------------------------------------------------------------
class TestArchTestRegistrationStructure:
    """TC-UT-AGR-009: ``test_masking_columns.py`` parametrize lists include Agent.

    Cross-checks that the CI Layer 2 arch test was extended to cover
    the 3 Agent tables. A future PR that drops these registrations
    (e.g. by accident during a refactor) would let an over-masking
    or under-masking change land silently — this test catches it.
    """

    async def test_agents_prompt_body_in_masking_contract(self) -> None:
        """``agents.prompt_body`` is registered as MaskedText in the contract list."""
        from bakufu.infrastructure.persistence.sqlite.base import MaskedText

        from tests.architecture.test_masking_columns import (
            _MASKING_CONTRACT,  # pyright: ignore[reportPrivateUsage]
        )

        assert ("agents", "prompt_body", MaskedText) in _MASKING_CONTRACT, (
            "[FAIL] agents.prompt_body missing from _MASKING_CONTRACT.\n"
            "Next: re-add the Schneier 申し送り #3 实適用 row to "
            "tests/architecture/test_masking_columns.py."
        )

    async def test_agent_providers_and_skills_in_no_mask_list(self) -> None:
        """``agent_providers`` / ``agent_skills`` are no-mask tables."""
        from tests.architecture.test_masking_columns import (
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        assert "agent_providers" in _NO_MASK_TABLES
        assert "agent_skills" in _NO_MASK_TABLES

    async def test_agents_partial_mask_template_registered(self) -> None:
        """``agents`` is registered in the partial-mask template list."""
        from tests.architecture.test_masking_columns import (
            _PARTIAL_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        partial = dict(_PARTIAL_MASK_TABLES)
        assert partial.get("agents") == "prompt_body", (
            f"[FAIL] agents partial-mask declared {partial.get('agents')!r}, "
            f"expected 'prompt_body'.\n"
            f"Next: §逆引き表 freezes prompt_body as the sole masked column on agents."
        )
