"""Task Repository: MaskedText wiring on 2 columns (TC-IT-TR-020-masking-*).

REQ-TR-004 / §確定 G 実適用 — tasks.last_error / deliverables.body_markdown
are ``MaskedText`` columns.

``conversation_messages.body_markdown`` is excluded (§BUG-TR-002 凍結済み):
Task domain currently has no ``conversations`` attribute. Tests for
``conversation_messages.body_markdown`` will be added when that attribute is
introduced.

**Task §確定 G 実適用の物理保証**:
2 columns must never let secret tokens reach SQLite. Each is verified via
**raw SQL SELECT** so the observation bypasses ``MaskedText.process_result_value``
and confirms the literal bytes on disk.

Per ``docs/features/task-repository/test-design.md`` TC-IT-TR-020-masking-*.
Issue #35 — M2 0007.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from sqlalchemy import text

from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_done_task,
    make_task,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Secret token constants (real-shape, constructed to avoid push-protection)
# ---------------------------------------------------------------------------

# Discord Bot Token — [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27

# Anthropic API key — sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60

# GitHub PAT — (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}
_GITHUB_TOKEN = "ghp_" + "X" * 40

# Redaction sentinels
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"


# ---------------------------------------------------------------------------
# Raw-SQL helpers
# ---------------------------------------------------------------------------
async def _read_last_error(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
) -> str | None:
    """Fetch tasks.last_error literal bytes via raw SQL (bypasses TypeDecorator read)."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT last_error FROM tasks WHERE id = :id"),
                {"id": task_id.hex},
            )
        ).first()
    if row is None:
        raise AssertionError(f"tasks row not found for id={task_id}")
    return row[0]


async def _read_deliverable_body(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
) -> str | None:
    """Fetch deliverables.body_markdown literal bytes for the first deliverable."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT body_markdown FROM deliverables WHERE task_id = :task_id LIMIT 1"),
                {"task_id": task_id.hex},
            )
        ).first()
    if row is None:
        raise AssertionError(f"deliverables row not found for task_id={task_id}")
    return row[0]


# ---------------------------------------------------------------------------
# TC-IT-TR-020-masking-discord: tasks.last_error Discord token redacted
# ---------------------------------------------------------------------------
class TestLastErrorDiscordTokenMasked:
    """TC-IT-TR-020-masking-discord: Discord Bot Token in last_error is redacted."""

    async def test_discord_token_in_last_error_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:DISCORD_TOKEN>; raw token absent from disk."""
        room_id, directive_id = seeded_task_context
        last_error = (
            f"Discord webhook failed: https://discord.com/api/webhooks/123/{_DISCORD_TOKEN}\n"
            f"status=401 Unauthorized"
        )
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error=last_error,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        persisted = await _read_last_error(session_factory, blocked.id)

        assert persisted is not None
        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] tasks.last_error missing Discord redaction sentinel.\nPersisted: {persisted!r}"
        )
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Raw Discord Bot Token leaked into tasks.last_error.\n"
            f"Violates Task §確定 G (不可逆性凍結). Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-020-masking-passthrough: tasks.last_error plain text unchanged
# ---------------------------------------------------------------------------
class TestLastErrorNoSecretPassthrough:
    """TC-IT-TR-020-masking-passthrough: plain error text stored byte-identical."""

    async def test_plain_error_text_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """A last_error without secrets is stored unchanged (masking is scoped)."""
        room_id, directive_id = seeded_task_context
        plain_error = "RateLimitExceeded: max 100 requests/min. Retry after 60s."
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error=plain_error,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        persisted = await _read_last_error(session_factory, blocked.id)
        assert persisted == plain_error, (
            f"[FAIL] plain last_error was modified during persistence.\n"
            f"Expected: {plain_error!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-020-masking-roundtrip: §確定 G §不可逆性
# ---------------------------------------------------------------------------
class TestLastErrorRoundTripIsIrreversible:
    """TC-IT-TR-020-masking-roundtrip: find_by_id returns masked last_error.

    Once a Discord token is masked at save(), the raw token is physically
    unrecoverable from DB. find_by_id must return a Task whose last_error
    carries the redaction sentinel rather than the original token.
    """

    async def test_find_by_id_returns_masked_last_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Save raw Discord token in last_error → find_by_id → last_error == masked."""
        room_id, directive_id = seeded_task_context
        raw_error = f"webhook auth={_DISCORD_TOKEN} rejected by Discord API"
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error=raw_error,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(blocked.id)

        assert restored is not None
        assert restored.last_error is not None
        assert _DISCORD_SENTINEL in restored.last_error, (
            f"[FAIL] find_by_id did not return masked last_error.\n"
            f"Restored last_error: {restored.last_error!r}"
        )
        assert _DISCORD_TOKEN not in restored.last_error, (
            f"[FAIL] Task §確定 G §不可逆性 violated: raw Discord token recovered.\n"
            f"Restored last_error: {restored.last_error!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-020-masking-null-safe: NULL last_error safe
# ---------------------------------------------------------------------------
class TestLastErrorNullSafe:
    """TC-IT-TR-020-masking-null-safe: last_error=None stored as SQL NULL."""

    async def test_null_last_error_stored_as_null(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """PENDING task with last_error=None → raw SQL SELECT returns NULL."""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, last_error=None)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        persisted = await _read_last_error(session_factory, task.id)
        assert persisted is None, (
            f"[FAIL] last_error=None should be stored as SQL NULL, got {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-020-masking-deliverable: deliverables.body_markdown GitHub PAT
# ---------------------------------------------------------------------------
class TestDeliverableBodyMarkdownGitHubPatMasked:
    """TC-IT-TR-020-masking-deliverable: GitHub PAT in deliverables.body_markdown redacted."""

    async def test_github_pat_in_deliverable_body_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:GITHUB_PAT>; raw PAT absent from disk."""
        room_id, directive_id = seeded_task_context
        stage_id = uuid4()
        body = f"## 成果物\nGitHub PAT: {_GITHUB_TOKEN}\nこのトークンでリポジトリを操作しました。"
        deliv = make_deliverable(stage_id=stage_id, body_markdown=body)
        task = make_done_task(
            room_id=room_id,
            directive_id=directive_id,
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        persisted = await _read_deliverable_body(session_factory, task.id)

        assert persisted is not None
        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] deliverables.body_markdown missing GitHub PAT sentinel.\n"
            f"Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] Raw GitHub PAT leaked into deliverables.body_markdown.\n"
            f"Persisted: {persisted!r}"
        )

    async def test_plain_deliverable_body_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """deliverables.body_markdown without secrets stored unchanged."""
        room_id, directive_id = seeded_task_context
        stage_id = uuid4()
        plain_body = "## 成果物\n\nタスク完了。特に問題なし。"
        deliv = make_deliverable(stage_id=stage_id, body_markdown=plain_body)
        task = make_done_task(
            room_id=room_id,
            directive_id=directive_id,
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        persisted = await _read_deliverable_body(session_factory, task.id)
        assert persisted == plain_body, (
            f"[FAIL] plain deliverable body was modified during persistence.\n"
            f"Expected: {plain_body!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-020-masking-2columns: simultaneous masking (2 columns at once)
#
# §BUG-TR-002 凍結済みのため conversation_messages は除外。
# tasks.last_error (Discord) + deliverables.body_markdown (GitHub PAT) のみ。
# ---------------------------------------------------------------------------
class TestTwoColumnSimultaneousMasking:
    """TC-IT-TR-020-masking-2columns: 2 MaskedText columns redacted simultaneously.

    One Task with:
      * tasks.last_error            → Discord token
      * deliverables.body_markdown  → GitHub PAT
    Both must be redacted in a single save cycle.
    """

    async def test_two_masked_text_columns_redacted_simultaneously(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Discord + GitHub both redacted across 2 separate MaskedText columns."""
        room_id, directive_id = seeded_task_context
        stage_id = uuid4()

        # last_error with Discord token
        last_error = f"Discord webhook error: {_DISCORD_TOKEN}"
        # deliverable body with GitHub PAT
        deliv_body = f"## 成果物\nGitHub clone with token {_GITHUB_TOKEN}"
        deliv = make_deliverable(stage_id=stage_id, body_markdown=deliv_body)

        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error=last_error,
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        # Verify both columns via raw SQL
        persisted_last_error = await _read_last_error(session_factory, blocked.id)
        persisted_deliv = await _read_deliverable_body(session_factory, blocked.id)

        # tasks.last_error — Discord
        assert persisted_last_error is not None
        assert _DISCORD_SENTINEL in persisted_last_error, (
            "[FAIL] tasks.last_error missing Discord sentinel in 2-column test."
        )
        assert _DISCORD_TOKEN not in persisted_last_error

        # deliverables.body_markdown — GitHub
        assert persisted_deliv is not None
        assert _GITHUB_SENTINEL in persisted_deliv, (
            "[FAIL] deliverables.body_markdown missing GitHub sentinel in 2-column test."
        )
        assert _GITHUB_TOKEN not in persisted_deliv
