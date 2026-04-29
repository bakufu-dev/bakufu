"""Task Repository: 2 カラムへの MaskedText 配線 (TC-IT-TR-020-masking-*).

REQ-TR-004 / §確定 G 実適用 ── tasks.last_error / deliverables.body_markdown
は ``MaskedText`` カラム。

``conversation_messages.body_markdown`` は除外 (§BUG-TR-002 凍結済み):
Task ドメインに現状 ``conversations`` 属性は存在しない。
``conversation_messages.body_markdown`` のテストはその属性導入時に追加する。

**Task §確定 G 実適用の物理保証**:
2 カラムは secret トークンを SQLite まで通してはならない。各カラムは
**raw SQL SELECT** で検証する ── ``MaskedText.process_result_value`` を
迂回し、ディスク上の実バイトを観察するため。
``docs/features/task-repository/test-design.md`` TC-IT-TR-020-masking-* 準拠。
Issue #35 ── M2 0007。
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
# secret トークン定数 (push-protection 回避のため実形を分割構築)
# ---------------------------------------------------------------------------

# Discord Bot Token ── [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27

# GitHub PAT ── (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}
_GITHUB_TOKEN = "ghp_" + "X" * 40

# redaction センチネル
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"


# ---------------------------------------------------------------------------
# Raw-SQL ヘルパ
# ---------------------------------------------------------------------------
async def _read_last_error(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
) -> str | None:
    """tasks.last_error の実バイトを raw SQL で取得する (TypeDecorator 読み取りを迂回)。"""
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
    """deliverables.body_markdown の実バイトを取得する (最初の deliverable)。"""
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
    """TC-IT-TR-020-masking-discord: last_error 中の Discord Bot Token が redact される。"""

    async def test_discord_token_in_last_error_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:DISCORD_TOKEN> を返し、生トークンはディスク上に残らない。"""
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
    """TC-IT-TR-020-masking-passthrough: 平文のエラーテキストはバイト等価で保存される。"""

    async def test_plain_error_text_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """secret を含まない last_error は変更なしで保存される (masking は適用範囲限定)。"""
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
    """TC-IT-TR-020-masking-roundtrip: find_by_id はマスク済み last_error を返す。

    save() 時に一度 Discord トークンが masking されると、生トークンは
    DB から物理的に復元不能となる。find_by_id は last_error に元トークンではなく
    redaction sentinel を含む Task を返さねばならない。
    """

    async def test_find_by_id_returns_masked_last_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """生 Discord トークンを last_error に保存 → find_by_id → last_error がマスクされている。"""
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
    """TC-IT-TR-020-masking-null-safe: last_error=None は SQL NULL として保存される。"""

    async def test_null_last_error_stored_as_null(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """PENDING task で last_error=None → raw SQL SELECT は NULL を返す。"""
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
    """TC-IT-TR-020-masking-deliverable: deliverables.body_markdown
    中の GitHub PAT が redact される。"""

    async def test_github_pat_in_deliverable_body_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:GITHUB_PAT> を返し、生 PAT はディスク上に残らない。"""
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
        """secret を含まない deliverables.body_markdown は変更なしで保存される。"""
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
# TC-IT-TR-020-masking-2columns: 同時 masking (2 カラム同時)
#
# §BUG-TR-002 凍結済みのため conversation_messages は除外。
# tasks.last_error (Discord) + deliverables.body_markdown (GitHub PAT) のみ。
# ---------------------------------------------------------------------------
class TestTwoColumnSimultaneousMasking:
    """TC-IT-TR-020-masking-2columns: 2 つの MaskedText カラムが同時に redact される。

    1 つの Task で以下を持つ:
      * tasks.last_error            → Discord トークン
      * deliverables.body_markdown  → GitHub PAT
    両方とも 1 回の save サイクルで redact されねばならない。
    """

    async def test_two_masked_text_columns_redacted_simultaneously(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """別個の 2 つの MaskedText カラム全てで Discord + GitHub がいずれも redact される。"""
        room_id, directive_id = seeded_task_context
        stage_id = uuid4()

        # last_error に Discord トークン
        last_error = f"Discord webhook error: {_DISCORD_TOKEN}"
        # deliverable body に GitHub PAT
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

        # 両カラムを raw SQL で確認
        persisted_last_error = await _read_last_error(session_factory, blocked.id)
        persisted_deliv = await _read_deliverable_body(session_factory, blocked.id)

        # tasks.last_error フィールドの Discord トークン検査
        assert persisted_last_error is not None
        assert _DISCORD_SENTINEL in persisted_last_error, (
            "[FAIL] tasks.last_error missing Discord sentinel in 2-column test."
        )
        assert _DISCORD_TOKEN not in persisted_last_error

        # deliverables.body_markdown フィールドの GitHub PAT 検査
        assert persisted_deliv is not None
        assert _GITHUB_SENTINEL in persisted_deliv, (
            "[FAIL] deliverables.body_markdown missing GitHub sentinel in 2-column test."
        )
        assert _GITHUB_TOKEN not in persisted_deliv
