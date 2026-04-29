"""Room Repository: §確定 R1-J ── rooms.prompt_kit_prefix_markdown への MaskedText 配線.

**Schneier 申し送り #3 実適用の物理保証 (Room 適用)**.
本モジュールは PR #33 の masking テスト中核 ──
``rooms.prompt_kit_prefix_markdown`` 上の MaskedText TypeDecorator を
実 SQLite DB に対して端から端まで動かし、secret を含む 7 種類の
prompt prefix 形に対して検証する:

1. **discord** ── webhook URL 文脈中の Discord Bot Token →
   ``<REDACTED:DISCORD_TOKEN>`` (テスト指示の主要ケース、§確定 R1-J 不可逆性)。
2. **anthropic** ── ``ANTHROPIC_API_KEY=sk-ant-api03-XXX...`` →
   ``<REDACTED:ANTHROPIC_KEY>``。
3. **github** ── ``ghp_XXX...`` → ``<REDACTED:GITHUB_PAT>``。
4. **bearer** ── ``Authorization: Bearer XXX`` → ``<REDACTED:BEARER>``。
5. **no-secret** ── 平文 prefix → 変更なし (passthrough)。
6. **roundtrip** ── §確定 R1-J §不可逆性: ``find_by_id`` は masking 済み形を
   返す (生トークンは DB から復元不能)。
7. **multiple** ── 1 つの prefix に 3 種以上の secret → 全て redact される。

各検証は ``rooms.prompt_kit_prefix_markdown`` を **raw SQL SELECT** で
読む ── ディスクに書き込まれた実バイトを観察するため (読み取り側で
``MaskedText.process_result_value`` を迂回)。

``docs/features/room-repository/test-design.md`` TC-IT-RR-008-masking-* 準拠。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.room.room import Room
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from sqlalchemy import text

from tests.factories.room import make_prompt_kit, make_room

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# 実形 (合成) の secret トークン。パターン長は masking ゲートウェイの正規表現
# (masking.py _REGEX_PATTERNS) に一致させなければ redact されない。

# Discord Bot Token ── [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,} に一致。
# テスト指示に従い webhook URL 文脈で使用。
# 明らかに合成テストフィクスチャに対する GitHub push-protection の誤検知を
# 避けるため、_ANTHROPIC_TOKEN と同じく連結で構築する。
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27

# Anthropic API キー ── sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,} に一致。
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60

# GitHub PAT ── (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,} に一致。
_GITHUB_TOKEN = "ghp_" + "X" * 40

# Bearer トークン ── Authorization: Bearer <token> に一致。
_BEARER_TOKEN = "eyJhbGciOi.tokenpart.signature"

# redaction sentinel (masking.py _REGEX_PATTERNS)。
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"
_BEARER_SENTINEL = "<REDACTED:BEARER>"


async def _read_persisted_prefix(
    session_factory: async_sessionmaker[AsyncSession],
    room_id: UUID,
) -> str:
    """``rooms.prompt_kit_prefix_markdown`` の実バイトを raw-SQL SELECT で取得する。

    ``MaskedText.process_result_value`` を迂回して、ディスクに物理的に
    保存された値を観察する。``UUIDStr`` TypeDecorator の保存形式と
    合わせるため、UUID パラメータは ``.hex`` を使う。
    """
    async with session_factory() as session:
        stmt = text("SELECT prompt_kit_prefix_markdown FROM rooms WHERE id = :id")
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
    """``prefix_markdown`` を持つ PromptKit を備えた Room を構築する。"""
    return make_room(
        workflow_id=workflow_id,
        prompt_kit=make_prompt_kit(prefix_markdown=prefix_markdown),
    )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-discord (primary case, §確定 R1-J)
# ---------------------------------------------------------------------------
class TestDiscordTokenMasked:
    """TC-IT-RR-008-masking-discord: webhook URL 中の Discord Bot Token が redact される。

    テスト指示の **主要ケース**:
    ``prompt_kit_prefix_markdownにDiscord webhook URLを渡した時DB上で
    <REDACTED:DISCORD_TOKEN>になること(不可逆性確認)``.

    webhook URL に埋め込まれた Discord Bot Token を含む prompt kit prefix は、
    SQLite ディスクに到達する前に masking されねばならない。
    """

    async def test_discord_token_in_webhook_url_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:DISCORD_TOKEN>`` を返し、生トークンは残らない。"""
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
    """TC-IT-RR-008-masking-anthropic: save 時に Anthropic API キーが redact される。"""

    async def test_anthropic_key_redacted_in_persisted_prefix(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:ANTHROPIC_KEY>`` を返し、生トークンは残らない。"""
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
    """TC-IT-RR-008-masking-github: save 時に GitHub PAT が redact される。"""

    async def test_github_pat_redacted_in_persisted_prefix(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:GITHUB_PAT>`` を返し、生 PAT は残らない。"""
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
    """TC-IT-RR-008-masking-bearer: Authorization: Bearer XXX が redact される。"""

    async def test_bearer_token_redacted_in_persisted_prefix(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:BEARER>`` を返し、生トークンは残らない。"""
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
    """TC-IT-RR-008-masking-no-secret: 平文 prefix は変更なしで保存される。"""

    async def test_plain_prefix_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Schneier #6 secret を含まない prefix はバイト等価で保存される。

        masking が **適用範囲限定** であることを確認 ── 既知の secret
        パターンのみ redact され、平文に対して過敏に反応しない。
        """
        plain = (
            "あなたはコードレビューを担当する開発者です。"
            "丁寧かつ的確にフィードバックを行ってください。"
        )
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
    """TC-IT-RR-008-masking-roundtrip: §確定 R1-J §不可逆性 ── find_by_id は masking 形を返す。

    save 時に一度 Discord Bot Token が masking されると、生トークンは
    DB から **物理的に復元不能** となる。``find_by_id`` は
    ``prompt_kit.prefix_markdown`` に元トークンではなく redaction sentinel
    を含む Room を返さねばならない。

    タスク指示に明示要求された主要 irreversibility テスト:
    「Discord webhook URLを渡した時DB上でになること(不可逆性確認)」。
    """

    async def test_find_by_id_returns_masked_prefix_markdown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """生 Discord webhook URL を保存 → find_by_id → prefix が masking 形。"""
        raw_prefix = f"Notify via https://discord.com/api/webhooks/12345/{_DISCORD_TOKEN}"
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
        # ラウンドトリップ済み Room は元と等価であってはならない (masking が値を変更している)。
        assert restored != room, (
            "[FAIL] round-trip equality should not hold for masked prompts; "
            "if this passes, masking might be a no-op."
        )


# ---------------------------------------------------------------------------
# TC-IT-RR-008-masking-multiple
# ---------------------------------------------------------------------------
class TestMultipleSecretsAllRedacted:
    """TC-IT-RR-008-masking-multiple: 1 つの prefix に 3 種以上の secret → 全て redact。"""

    async def test_multiple_secrets_all_redacted_in_one_pass(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """discord + anthropic + github を含む prefix は全て完全に redact される。

        masking が **網羅的** であることを確認 ── 1 つの redaction が
        他を短絡しない。ゲートウェイは全正規表現パターンを反復する ──
        本テストでその挙動を固定する。
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

        # 3 つの sentinel が全て存在する。
        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] Discord sentinel missing in multi-secret prefix. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] Anthropic sentinel missing in multi-secret prefix. Persisted: {persisted!r}"
        )
        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] GitHub sentinel missing in multi-secret prefix. Persisted: {persisted!r}"
        )
        # 3 つの生トークンは全て消えている。
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Discord token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Anthropic token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] GitHub PAT survived multi-secret masking. Persisted: {persisted!r}"
        )
