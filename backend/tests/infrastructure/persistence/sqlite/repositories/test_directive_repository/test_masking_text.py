"""Directive Repository: §確定 G 実適用 — MaskedText wiring on directives.text.

TC-IT-DRR-010-masking-* (7 paths).

**directive §確定 G 実適用の物理保証**: This module is the core masking
test file for PR #34 — the MaskedText TypeDecorator on ``directives.text``
is exercised end-to-end against a real SQLite DB, against 7 secret-bearing
directive text shapes:

1. **discord** — Discord Bot Token in webhook URL context →
   ``<REDACTED:DISCORD_TOKEN>`` (primary irreversibility case).
2. **anthropic** — ``ANTHROPIC_API_KEY=sk-ant-api03-XXX...`` →
   ``<REDACTED:ANTHROPIC_KEY>``.
3. **github** — ``ghp_XXX...`` → ``<REDACTED:GITHUB_PAT>``.
4. **bearer** — ``Authorization: Bearer XXX`` → ``<REDACTED:BEARER>``.
5. **no-secret** — plain text → unchanged (passthrough).
6. **roundtrip** — §確定 G §不可逆性: find_by_id returns masked form
   (raw token unrecoverable from DB).
7. **multiple** — 3 secret types in one directive text → all redacted.

Each verification reads ``directives.text`` via **raw SQL SELECT** so we
observe the literal bytes that hit the disk (bypassing
``MaskedText.process_result_value`` on the read side).

Room-repo ``test_masking_prompt_kit.py`` pattern inherited 100%.

Per ``docs/features/directive-repository/test-design.md`` TC-IT-DRR-010-*.
Issue #34 — M2 0006.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
    SqliteDirectiveRepository,
)
from sqlalchemy import text

from tests.factories.directive import make_directive

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# Real-shape (synthetic) secret tokens. Pattern lengths must match
# the masking gateway's regex (masking.py _REGEX_PATTERNS).

# Discord Bot Token — matches [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}
# Constructed via concatenation to prevent GitHub push-protection false positives.
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27

# Anthropic API key — matches sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60

# GitHub PAT — matches (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}
_GITHUB_TOKEN = "ghp_" + "X" * 40

# Bearer token — matches Authorization: Bearer <token>
_BEARER_TOKEN = "eyJhbGciOi.tokenpart.signature"

# Redaction sentinels
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"
_BEARER_SENTINEL = "<REDACTED:BEARER>"


async def _read_persisted_text(
    session_factory: async_sessionmaker[AsyncSession],
    directive_id: UUID,
) -> str:
    """Raw-SQL SELECT to fetch ``directives.text`` literal bytes from disk.

    Bypasses ``MaskedText.process_result_value`` so we observe the value
    physically stored in SQLite. Uses ``.hex`` for the UUID parameter
    to match ``UUIDStr`` TypeDecorator storage format.
    """
    async with session_factory() as session:
        stmt = text("SELECT text FROM directives WHERE id = :id")
        row = (await session.execute(stmt, {"id": directive_id.hex})).first()
    assert row is not None, f"directives row not found for id={directive_id}"
    persisted = row[0]
    assert isinstance(persisted, str)
    return persisted


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-discord (primary case, directive §確定 G 不可逆性)
# ---------------------------------------------------------------------------
class TestDiscordTokenMasked:
    """TC-IT-DRR-010-masking-discord: Discord Bot Token in directive text redacted."""

    async def test_discord_token_in_webhook_url_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:DISCORD_TOKEN>; raw token absent from disk."""
        directive_text = (
            f"配信先: https://discord.com/api/webhooks/123456789012345678/{_DISCORD_TOKEN}\n"
            f"通知プレフィックス: CEO 指令"
        )
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] directives.text missing Discord redaction sentinel.\n"
            f"Next: verify MaskedText TypeDecorator on directives.text. "
            f"Persisted: {persisted!r}"
        )
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Raw Discord Bot Token leaked into directives.text.\n"
            f"This violates directive §確定 G (不可逆性凍結). Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-anthropic
# ---------------------------------------------------------------------------
class TestAnthropicKeyMasked:
    """TC-IT-DRR-010-masking-anthropic: Anthropic API key redacted on save."""

    async def test_anthropic_key_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:ANTHROPIC_KEY>; raw key absent."""
        directive_text = f"ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN} を使ってClaude APIを呼ぶこと"
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] directives.text missing Anthropic redaction sentinel. "
            f"Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Raw Anthropic API key leaked into directives.text. "
            f"Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-github
# ---------------------------------------------------------------------------
class TestGitHubPatMasked:
    """TC-IT-DRR-010-masking-github: GitHub PAT redacted on save."""

    async def test_github_pat_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:GITHUB_PAT>; raw PAT absent."""
        directive_text = f"git push には {_GITHUB_TOKEN} を使うこと"
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] directives.text missing GitHub PAT redaction sentinel. "
            f"Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] Raw GitHub PAT leaked into directives.text. "
            f"Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-bearer
# ---------------------------------------------------------------------------
class TestBearerTokenMasked:
    """TC-IT-DRR-010-masking-bearer: Authorization: Bearer XXX redacted."""

    async def test_bearer_token_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:BEARER>; raw Bearer token absent."""
        directive_text = (
            f"APIコール時は Authorization: Bearer {_BEARER_TOKEN} を使うこと"
        )
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        assert _BEARER_SENTINEL in persisted, (
            f"[FAIL] directives.text missing Bearer redaction sentinel. "
            f"Persisted: {persisted!r}"
        )
        assert _BEARER_TOKEN not in persisted, (
            f"[FAIL] Raw Bearer token leaked into directives.text. "
            f"Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-no-secret (passthrough)
# ---------------------------------------------------------------------------
class TestNoSecretPassthrough:
    """TC-IT-DRR-010-masking-no-secret: plain directive text is stored unchanged."""

    async def test_plain_text_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """A directive text with no secrets is persisted byte-identical.

        Confirms masking is scoped — only known secret patterns get
        redacted; the gateway is not over-aggressive on plain text.
        """
        plain_text = "チームAにタスクXを割り当て、Vモデル設計工程に入ること。"
        directive = make_directive(target_room_id=seeded_room_id, text=plain_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)
        assert persisted == plain_text, (
            f"[FAIL] plain directive text was modified during persistence.\n"
            f"Expected: {plain_text!r}\n"
            f"Got:      {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-roundtrip (directive §確定 G §不可逆性)
# ---------------------------------------------------------------------------
class TestRoundTripIsIrreversible:
    """TC-IT-DRR-010-masking-roundtrip: §確定 G §不可逆性 — find_by_id returns masked.

    Once a Discord Bot Token is masked at save time, the raw token is
    physically unrecoverable from DB. find_by_id must return a Directive
    whose text carries the redaction sentinel rather than the original token.
    """

    async def test_find_by_id_returns_masked_text(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Save raw Discord webhook URL → find_by_id → text == masked form."""
        raw_text = (
            f"配信先: https://discord.com/api/webhooks/12345/{_DISCORD_TOKEN}"
        )
        directive = make_directive(target_room_id=seeded_room_id, text=raw_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert _DISCORD_SENTINEL in restored.text, (
            f"[FAIL] find_by_id did not return masked text.\n"
            f"Restored text: {restored.text!r}"
        )
        assert _DISCORD_TOKEN not in restored.text, (
            f"[FAIL] directive §確定 G §不可逆性 violated: raw Discord token recovered after "
            f"round-trip.\nRestored text: {restored.text!r}"
        )
        # Round-tripped Directive must NOT equal the original (masking changed it)
        assert restored != directive, (
            "[FAIL] round-trip equality should not hold for masked directive text; "
            "masking might be a no-op."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-multiple
# ---------------------------------------------------------------------------
class TestMultipleSecretsAllRedacted:
    """TC-IT-DRR-010-masking-multiple: 3+ secret types in one directive all redacted."""

    async def test_multiple_secrets_all_redacted_in_one_pass(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Discord + Anthropic + GitHub all redacted in a single directive text."""
        directive_text = (
            f"複数シークレットを含む指令:\n"
            f"  Discord: https://discord.com/api/webhooks/123/{_DISCORD_TOKEN}\n"
            f"  ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN}\n"
            f"  GITHUB_TOKEN={_GITHUB_TOKEN}\n"
        )
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        # All 3 sentinels present
        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] Discord sentinel missing in multi-secret directive. "
            f"Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] Anthropic sentinel missing in multi-secret directive. "
            f"Persisted: {persisted!r}"
        )
        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] GitHub sentinel missing in multi-secret directive. "
            f"Persisted: {persisted!r}"
        )
        # All 3 raw tokens absent
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Discord token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Anthropic token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] GitHub PAT survived multi-secret masking. Persisted: {persisted!r}"
        )
