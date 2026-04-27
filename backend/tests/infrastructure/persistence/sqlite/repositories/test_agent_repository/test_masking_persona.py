"""Agent Repository: §確定 H — MaskedText wiring on agents.prompt_body.

**Schneier 申し送り #3 实適用の物理保証**. This module is the core test
file for PR #45 — the persistence-foundation #23 hook structure is
finally exercised end-to-end against a real SQLite DB, against 7
secret-bearing prompt-body shapes:

1. **anthropic** — ``ANTHROPIC_API_KEY=sk-ant-api03-XXX...`` → ``<REDACTED:ANTHROPIC_KEY>``
2. **github** — ``ghp_XXX...`` → ``<REDACTED:GITHUB_PAT>``
3. **openai** — ``sk-XXX...`` → ``<REDACTED:OPENAI_KEY>``
4. **bearer** — ``Authorization: Bearer XXX`` → ``<REDACTED:BEARER>``
5. **no-secret** — plain prompt → unchanged (passthrough)
6. **roundtrip** — §確定 H §不可逆性: ``find_by_id`` returns the masked
   form (raw token unrecoverable from DB).
7. **multiple** — 3+ secret types in one prompt → all redacted.

Each verification reads the persisted ``agents.prompt_body`` value via
**raw SQL SELECT** so we observe the literal bytes that hit the disk
(bypassing ``MaskedText.process_result_value`` is fine; the column is
TEXT-typed, so the raw bind side IS the on-disk side).

Per ``docs/features/agent-repository/test-design.md`` TC-IT-AGR-006-masking-*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.agent import Agent, Persona
from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
    SqliteAgentRepository,
)
from sqlalchemy import text

from tests.factories.agent import make_agent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# Real-shape (synthetic) secret tokens. Pattern lengths must match
# the masking gateway's regex (masking.py L62-93) so the token is
# actually redacted; otherwise the test would pass for the wrong
# reason (token is plain text → grep finds no token → false negative).
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60
_GITHUB_TOKEN = "ghp_" + "X" * 40
_OPENAI_TOKEN = "sk-" + "B" * 50  # 20+ chars after sk-, not sk-ant- (negative lookahead)
_BEARER_TOKEN = "eyJhbGciOi.tokenpart.signature"

# Redaction sentinels (masking.py L62-93).
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"
_OPENAI_SENTINEL = "<REDACTED:OPENAI_KEY>"
_BEARER_SENTINEL = "<REDACTED:BEARER>"


def _make_agent_with_prompt(prompt_body: str, *, empire_id: UUID) -> Agent:
    """Build an Agent whose Persona carries ``prompt_body``.

    The default factory keeps every other field synthetic-but-valid;
    we override only ``persona.prompt_body`` to inject the secret
    pattern under test. ``empire_id`` is required so the FK to
    ``empires.id`` resolves at INSERT time.
    """
    persona = Persona(
        display_name="masking-probe",
        archetype="review-focused",
        prompt_body=prompt_body,
    )
    return make_agent(empire_id=empire_id, persona=persona)


async def _read_persisted_prompt(
    session_factory: async_sessionmaker[AsyncSession],
    agent_id: UUID,
) -> str:
    """Raw-SQL SELECT to fetch ``agents.prompt_body`` literal bytes.

    Bypasses ``MaskedText.process_result_value`` is unnecessary —
    that hook is identity (just returns the stored string), so what
    we read here IS what is on disk. We use ``text()`` to make the
    intent explicit and to keep the test independent of the ORM-
    declarative metadata.
    """
    async with session_factory() as session:
        stmt = text("SELECT prompt_body FROM agents WHERE id = :id")
        # SQLAlchemy's UUIDStr TypeDecorator stores as ``.hex``; we
        # match that here so the WHERE clause hits the row.
        row = (await session.execute(stmt, {"id": agent_id.hex})).first()
    assert row is not None, f"agents row not found for id={agent_id}"
    persisted = row[0]
    assert isinstance(persisted, str)
    return persisted


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-anthropic
# ---------------------------------------------------------------------------
class TestAnthropicKeyMasked:
    """TC-IT-AGR-006-masking-anthropic: Anthropic API key redacted on save."""

    async def test_anthropic_key_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:ANTHROPIC_KEY>``; raw token absent."""
        prompt = f"Use ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN} when calling Claude."
        agent = _make_agent_with_prompt(prompt, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        persisted = await _read_persisted_prompt(session_factory, agent.id)

        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] agents.prompt_body missing Anthropic redaction sentinel.\n"
            f"Next: verify MaskedText TypeDecorator on agents.prompt_body. "
            f"Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Raw Anthropic API key leaked into agents.prompt_body.\n"
            f"This is the catastrophic case Schneier 申し送り #3 was designed "
            f"to prevent. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-github
# ---------------------------------------------------------------------------
class TestGitHubPatMasked:
    """TC-IT-AGR-006-masking-github: GitHub PAT redacted on save."""

    async def test_github_pat_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:GITHUB_PAT>``; raw PAT absent."""
        prompt = f"Use {_GITHUB_TOKEN} for git push."
        agent = _make_agent_with_prompt(prompt, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        persisted = await _read_persisted_prompt(session_factory, agent.id)

        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] agents.prompt_body missing GitHub PAT redaction sentinel. "
            f"Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] Raw GitHub PAT leaked into agents.prompt_body. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-openai
# ---------------------------------------------------------------------------
class TestOpenAiKeyMasked:
    """TC-IT-AGR-006-masking-openai: OpenAI API key redacted on save."""

    async def test_openai_key_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:OPENAI_KEY>``; raw token absent.

        Note the masking gateway uses a **negative lookahead** so
        Anthropic's ``sk-ant-`` prefix is NOT mis-classified as
        OpenAI. We feed a non-Anthropic ``sk-...`` here.
        """
        prompt = f"Use OPENAI_API_KEY={_OPENAI_TOKEN} for fallback."
        agent = _make_agent_with_prompt(prompt, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        persisted = await _read_persisted_prompt(session_factory, agent.id)

        assert _OPENAI_SENTINEL in persisted, (
            f"[FAIL] agents.prompt_body missing OpenAI redaction sentinel. Persisted: {persisted!r}"
        )
        assert _OPENAI_TOKEN not in persisted, (
            f"[FAIL] Raw OpenAI API key leaked into agents.prompt_body. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-bearer
# ---------------------------------------------------------------------------
class TestBearerTokenMasked:
    """TC-IT-AGR-006-masking-bearer: Authorization: Bearer XXX redacted."""

    async def test_bearer_token_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:BEARER>``; raw token absent."""
        prompt = f"Set header `Authorization: Bearer {_BEARER_TOKEN}`."
        agent = _make_agent_with_prompt(prompt, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        persisted = await _read_persisted_prompt(session_factory, agent.id)

        assert _BEARER_SENTINEL in persisted, (
            f"[FAIL] agents.prompt_body missing Bearer redaction sentinel. Persisted: {persisted!r}"
        )
        assert _BEARER_TOKEN not in persisted, (
            f"[FAIL] Raw Bearer token leaked into agents.prompt_body. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-no-secret (passthrough)
# ---------------------------------------------------------------------------
class TestNoSecretPassthrough:
    """TC-IT-AGR-006-masking-no-secret: plain prompt is stored unchanged."""

    async def test_plain_prompt_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """A prompt with no Schneier-#6 secrets is persisted byte-identical.

        Confirms masking is **scoped** — only known secret patterns
        get redacted; the masking gateway is not over-aggressive on
        plain text. Without this check, a regression that replaces
        the masking gateway with ``str.replace_all('a', '<X>')``
        would silently corrupt prompts.
        """
        plain = "You are a thorough reviewer who checks PRs carefully."
        agent = _make_agent_with_prompt(plain, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        persisted = await _read_persisted_prompt(session_factory, agent.id)
        assert persisted == plain, (
            f"[FAIL] non-secret prompt was modified during persistence.\n"
            f"Expected: {plain!r}\n"
            f"Got:      {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-roundtrip (§確定 H §不可逆性)
# ---------------------------------------------------------------------------
class TestRoundTripIsIrreversible:
    """TC-IT-AGR-006-masking-roundtrip: §確定 H §不可逆性 — find_by_id returns masked.

    Once a secret is masked at save time, the raw token is
    **physically unrecoverable** from the DB. ``find_by_id`` must
    therefore return a Persona whose ``prompt_body`` carries the
    redaction sentinel rather than the original token. Detecting
    masked prompts and refusing to dispatch them to the LLM is
    ``feature/llm-adapter``'s job (申し送り #1) — the Repository
    contract is "the masked form is what you get back".
    """

    async def test_find_by_id_returns_masked_prompt_body(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Save raw → find_by_id → persona.prompt_body == masked form."""
        raw = f"ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN}"
        agent = _make_agent_with_prompt(raw, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        async with session_factory() as session:
            restored = await SqliteAgentRepository(session).find_by_id(agent.id)

        assert restored is not None
        assert _ANTHROPIC_SENTINEL in restored.persona.prompt_body, (
            f"[FAIL] find_by_id did not return masked prompt_body.\n"
            f"Restored: {restored.persona.prompt_body!r}"
        )
        assert _ANTHROPIC_TOKEN not in restored.persona.prompt_body, (
            f"[FAIL] §確定 H §不可逆性 violated: raw token recovered after round-trip.\n"
            f"Restored: {restored.persona.prompt_body!r}"
        )
        # And of course the round-tripped Agent does NOT compare equal
        # to the original Agent (since prompt_body changed) — pin
        # this asymmetry as the documented design contract.
        assert restored != agent, (
            "[FAIL] round-trip equality should not hold for masked prompts; "
            "if this passes, masking might be a no-op."
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-multiple
# ---------------------------------------------------------------------------
class TestMultipleSecretsAllRedacted:
    """TC-IT-AGR-006-masking-multiple: 3+ secret types in one prompt all redacted."""

    async def test_multiple_secrets_all_redacted_in_one_pass(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """A prompt with anthropic + github + bearer all gets fully redacted.

        Confirms masking is **comprehensive** — applying one redaction
        does not short-circuit the others. The gateway iterates all
        regex patterns; this test pins that behaviour.
        """
        prompt = (
            f"Multiple secrets in one prompt:\n"
            f"  ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN}\n"
            f"  GITHUB_TOKEN={_GITHUB_TOKEN}\n"
            f"  Authorization: Bearer {_BEARER_TOKEN}\n"
        )
        agent = _make_agent_with_prompt(prompt, empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        persisted = await _read_persisted_prompt(session_factory, agent.id)

        # All 3 sentinels present.
        assert _ANTHROPIC_SENTINEL in persisted
        assert _GITHUB_SENTINEL in persisted
        assert _BEARER_SENTINEL in persisted
        # All 3 raw tokens absent.
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Anthropic token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] GitHub PAT survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _BEARER_TOKEN not in persisted, (
            f"[FAIL] Bearer token survived multi-secret masking. Persisted: {persisted!r}"
        )
