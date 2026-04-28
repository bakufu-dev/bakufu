"""Room Repository: §確定 R1-J — MaskedText wiring on rooms.prompt_kit_prefix_markdown.

**Schneier 申し送り #3 实適用の物理保証 (Room 適用)**. This module is the core
masking test file for PR #33 — the MaskedText TypeDecorator on
``rooms.prompt_kit_prefix_markdown`` is exercised end-to-end against a real
SQLite DB, against 7 secret-bearing prompt-prefix shapes:

1. **discord** — Discord Bot Token in webhook URL context →
   ``<REDACTED:DISCORD_TOKEN>`` (primary case from test instruction,
   §確定 R1-J 不可逆性).
2. **anthropic** — ``ANTHROPIC_API_KEY=sk-ant-api03-XXX...`` →
   ``<REDACTED:ANTHROPIC_KEY>``.
3. **github** — ``ghp_XXX...`` → ``<REDACTED:GITHUB_PAT>``.
4. **bearer** — ``Authorization: Bearer XXX`` → ``<REDACTED:BEARER>``.
5. **no-secret** — plain prefix → unchanged (passthrough).
6. **roundtrip** — §確定 R1-J §不可逆性: ``find_by_id`` returns the masked
   form (raw token unrecoverable from DB).
7. **multiple** — 3+ secret types in one prefix → all redacted.

Each verification reads ``rooms.prompt_kit_prefix_markdown`` via **raw SQL
SELECT** so we observe the literal bytes that hit the disk (bypassing
``MaskedText.process_result_value`` on the read side).

Per ``docs/features/room-repository/test-design.md`` TC-IT-RR-008-masking-*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from sqlalchemy import text

from bakufu.domain.room.room import Room
from tests.factories.room import make_prompt_kit, make_room

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# Real-shape (synthetic) secret tokens. Pattern lengths must match
# the masking gateway's regex (masking.py _REGEX_PATTERNS) so the
# token is actually redacted.

# Discord Bot Token — matches [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}
# Used in a webhook URL context per test instruction.
# Constructed via concatenation (same pattern as _ANTHROPIC_TOKEN) to prevent
# GitHub push-protection false positives on a clearly synthetic test fixture.
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27

# Anthropic API key — matches sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60

# GitHub PAT — matches (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}
_GITHUB_TOKEN = "ghp_" + "X" * 40

# Bearer token — matches Authorization: Bearer <token>
_BEARER_TOKEN = "eyJhbGciOi.tokenpart.signature"

# Redaction sentinels (masking.py _REGEX_PATTERNS).
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"
_BEARER_SENTINEL = "<REDACTED:BEARER>"


async def _read_persisted_prefix(
    session_factory: async_sessionmaker[AsyncSession],
    room_id: UUID,
) -> str:
    """Raw-SQL SELECT to fetch ``rooms.prompt_kit_prefix_markdown`` literal bytes.

    Bypasses ``MaskedText.process_result_value`` so we observe the value
    that is physically stored on disk. Uses ``.hex`` for the UUID parameter
    to match ``UUIDStr`` TypeDecorator storage format.
    """
    async with session_factory() as session:
        stmt = text(
            "SELECT prompt_kit_prefix_markdown FROM rooms WHERE id = :id"
        )
        row = (await session.execute(stmt, {"id": room_id.hex})).first()
    assert row is not None, f"rooms row not found for id={room_id}"
    persisted = row[0]
    assert isinstance(persisted, str)
    return persisted


def _make_room_with_prefix(
    prefix_markdown: str,
    *,
    workflow_id: UUID,
) -> Room:
    """Build a Room whose PromptKit carries ``prefix_markdown``."""
    return make_room(
        workflow_id=workflow_id,
        prompt_kit=make_prompt_kit(prefix_markdown=prefix_markdown),
    )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-discord (primary case, §確定 R1-J)
# ---------------------------------------------------------------------------
class TestDiscordTokenMasked:
    """TC-IT-RR-008-masking-discord: Discord Bot Token in webhook URL redacted.

    This is the **primary case** from the test instruction:
    ``prompt_kit_prefix_markdownにDiscord webhook URLを渡した時DB上で
    <REDACTED:DISCORD_TOKEN>になること（不可逆性確認）``.

    A prompt-kit prefix that contains a Discord Bot Token embedded in a
    webhook URL must be masked before it hits SQLite disk.
    """

    async def test_discord_token_in_webhook_url_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:DISCORD_TOKEN>``; raw token absent."""
        prefix = (
            f"通知先: https://discord.com/api/webhooks/123456789012345678/{_DISCORD_TOKEN}\n"
            f"このURLを使ってワークフロー完了を通知する。"
        )
        room = _make_room_with_prefix(prefix, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        persisted = await _read_persisted_prefix(session_factory, room.id)

        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] rooms.prompt_kit_prefix_markdown missing Discord redaction sentinel.\n"
            f"Next: verify MaskedText TypeDecorator on rooms.prompt_kit_prefix_markdown. "
            f"Persisted: {persisted!r}"
        )
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Raw Discord Bot Token leaked into rooms.prompt_kit_prefix_markdown.\n"
            f"This violates §確定 R1-J (不可逆性凍結). Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-anthropic
# ---------------------------------------------------------------------------
class TestAnthropicKeyMasked:
    """TC-IT-RR-008-masking-anthropic: Anthropic API key redacted on save."""

    async def test_anthropic_key_redacted_in_persisted_prefix(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:ANTHROPIC_KEY>``; raw token absent."""
        prefix = f"ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN} を使ってClaude APIを呼ぶこと。"
        room = _make_room_with_prefix(prefix, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        persisted = await _read_persisted_prefix(session_factory, room.id)

        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] rooms.prompt_kit_prefix_markdown missing Anthropic redaction sentinel.\n"
            f"Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Raw Anthropic API key leaked into rooms.prompt_kit_prefix_markdown.\n"
            f"Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-github
# ---------------------------------------------------------------------------
class TestGitHubPatMasked:
    """TC-IT-RR-008-masking-github: GitHub PAT redacted on save."""

    async def test_github_pat_redacted_in_persisted_prefix(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:GITHUB_PAT>``; raw PAT absent."""
        prefix = f"git push には {_GITHUB_TOKEN} を使うこと。"
        room = _make_room_with_prefix(prefix, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        persisted = await _read_persisted_prefix(session_factory, room.id)

        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] rooms.prompt_kit_prefix_markdown missing GitHub PAT redaction sentinel. "
            f"Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] Raw GitHub PAT leaked into rooms.prompt_kit_prefix_markdown. "
            f"Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-bearer
# ---------------------------------------------------------------------------
class TestBearerTokenMasked:
    """TC-IT-RR-008-masking-bearer: Authorization: Bearer XXX redacted."""

    async def test_bearer_token_redacted_in_persisted_prefix(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT shows ``<REDACTED:BEARER>``; raw token absent."""
        prefix = f"APIコール時は ``Authorization: Bearer {_BEARER_TOKEN}`` を使うこと。"
        room = _make_room_with_prefix(prefix, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        persisted = await _read_persisted_prefix(session_factory, room.id)

        assert _BEARER_SENTINEL in persisted, (
            f"[FAIL] rooms.prompt_kit_prefix_markdown missing Bearer redaction sentinel. "
            f"Persisted: {persisted!r}"
        )
        assert _BEARER_TOKEN not in persisted, (
            f"[FAIL] Raw Bearer token leaked into rooms.prompt_kit_prefix_markdown. "
            f"Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-no-secret (passthrough)
# ---------------------------------------------------------------------------
class TestNoSecretPassthrough:
    """TC-IT-RR-008-masking-no-secret: plain prefix is stored unchanged."""

    async def test_plain_prefix_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """A prefix with no Schneier-#6 secrets is persisted byte-identical.

        Confirms masking is **scoped** — only known secret patterns
        get redacted; the masking gateway is not over-aggressive on
        plain text.
        """
        plain = "あなたはコードレビューを担当する開発者です。丁寧かつ的確にフィードバックを行ってください。"
        room = _make_room_with_prefix(plain, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        persisted = await _read_persisted_prefix(session_factory, room.id)
        assert persisted == plain, (
            f"[FAIL] non-secret prefix was modified during persistence.\n"
            f"Expected: {plain!r}\n"
            f"Got:      {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-roundtrip (§確定 R1-J §不可逆性)
# ---------------------------------------------------------------------------
class TestRoundTripIsIrreversible:
    """TC-IT-RR-008-masking-roundtrip: §確定 R1-J §不可逆性 — find_by_id returns masked.

    Once a Discord Bot Token is masked at save time, the raw token is
    **physically unrecoverable** from the DB. ``find_by_id`` must
    therefore return a Room whose ``prompt_kit.prefix_markdown`` carries
    the redaction sentinel rather than the original token.

    This is the primary irreversibility test specifically requested in
    the task instruction: "Discord webhook URLを渡した時DB上でになること
    （不可逆性確認）".
    """

    async def test_find_by_id_returns_masked_prefix_markdown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Save raw Discord webhook URL → find_by_id → prefix == masked form."""
        raw_prefix = (
            f"Notify via https://discord.com/api/webhooks/12345/{_DISCORD_TOKEN}"
        )
        room = _make_room_with_prefix(raw_prefix, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            restored = await SqliteRoomRepository(session).find_by_id(room.id)

        assert restored is not None
        assert _DISCORD_SENTINEL in restored.prompt_kit.prefix_markdown, (
            f"[FAIL] find_by_id did not return masked prefix_markdown.\n"
            f"Restored: {restored.prompt_kit.prefix_markdown!r}"
        )
        assert _DISCORD_TOKEN not in restored.prompt_kit.prefix_markdown, (
            f"[FAIL] §確定 R1-J §不可逆性 violated: raw Discord token recovered after "
            f"round-trip.\nRestored: {restored.prompt_kit.prefix_markdown!r}"
        )
        # The round-tripped Room must NOT equal the original (masking changed the value).
        assert restored != room, (
            "[FAIL] round-trip equality should not hold for masked prompts; "
            "if this passes, masking might be a no-op."
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-multiple
# ---------------------------------------------------------------------------
class TestMultipleSecretsAllRedacted:
    """TC-IT-RR-008-masking-multiple: 3+ secret types in one prefix all redacted."""

    async def test_multiple_secrets_all_redacted_in_one_pass(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """A prefix with discord + anthropic + github all gets fully redacted.

        Confirms masking is **comprehensive** — applying one redaction
        does not short-circuit the others. The gateway iterates all
        regex patterns; this test pins that behaviour.
        """
        prefix = (
            f"複数シークレットを含むプレフィックス:\n"
            f"  Discord: https://discord.com/api/webhooks/123/{_DISCORD_TOKEN}\n"
            f"  ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN}\n"
            f"  GITHUB_TOKEN={_GITHUB_TOKEN}\n"
        )
        room = _make_room_with_prefix(prefix, workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        persisted = await _read_persisted_prefix(session_factory, room.id)

        # All 3 sentinels present.
        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] Discord sentinel missing in multi-secret prefix. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] Anthropic sentinel missing in multi-secret prefix. Persisted: {persisted!r}"
        )
        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] GitHub sentinel missing in multi-secret prefix. Persisted: {persisted!r}"
        )
        # All 3 raw tokens absent.
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Discord token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Anthropic token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] GitHub PAT survived multi-secret masking. Persisted: {persisted!r}"
        )
