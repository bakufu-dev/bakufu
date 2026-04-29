"""Directive Repository: §確定 G 実適用 ── directives.text への MaskedText 配線。

TC-IT-DRR-010-masking-* (7 経路)。

**directive §確定 G 実適用の物理保証**: 本モジュールは PR #34 のマスキング核となるテストファイル。
``directives.text`` の MaskedText TypeDecorator が、実際の SQLite DB に対して
secret を含む 7 種類の directive text 形状でエンドツーエンドに動作することを検証する:

1. **discord** — webhook URL 文脈の Discord Bot Token →
   ``<REDACTED:DISCORD_TOKEN>``（主要な不可逆性ケース）。
2. **anthropic** — ``ANTHROPIC_API_KEY=sk-ant-api03-XXX...`` →
   ``<REDACTED:ANTHROPIC_KEY>``。
3. **github** — ``ghp_XXX...`` → ``<REDACTED:GITHUB_PAT>``。
4. **bearer** — ``Authorization: Bearer XXX`` → ``<REDACTED:BEARER>``。
5. **no-secret** — 平文 → 変更されない（passthrough）。
6. **roundtrip** — §確定 G §不可逆性: find_by_id はマスク済み形式を返す
   （生トークンは DB から復元不能）。
7. **multiple** — 1 つの directive text 内の 3 種の secret すべてが redact される。

各検証は **raw SQL SELECT** で ``directives.text`` を読み取り、ディスクに到達した
literal バイトを観測する（読み出し側で ``MaskedText.process_result_value`` を迂回）。

Room-repo ``test_masking_prompt_kit.py`` のパターンを 100% 踏襲。

``docs/features/directive-repository/test-design.md`` TC-IT-DRR-010-* 準拠。
Issue #34 — M2 0006。
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


# 実形（合成）secret トークン。パターン長は masking gateway の正規表現
# (masking.py _REGEX_PATTERNS) に一致させる必要がある。

# Discord Bot Token ── [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,} に一致。
# GitHub push-protection の false positive を避けるため連結で構築。
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27

# Anthropic API key ── sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,} に一致。
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60

# GitHub PAT ── (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,} に一致。
_GITHUB_TOKEN = "ghp_" + "X" * 40

# Bearer token ── Authorization: Bearer <token> に一致。
_BEARER_TOKEN = "eyJhbGciOi.tokenpart.signature"

# Redaction センチネル
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"
_BEARER_SENTINEL = "<REDACTED:BEARER>"


async def _read_persisted_text(
    session_factory: async_sessionmaker[AsyncSession],
    directive_id: UUID,
) -> str:
    """Raw-SQL SELECT で ``directives.text`` の literal バイトをディスクから取得する。

    ``MaskedText.process_result_value`` を迂回して SQLite に物理的に保存されている値を観測する。
    UUID パラメータは ``UUIDStr`` TypeDecorator のストレージ形式に合わせて ``.hex`` を用いる。
    """
    async with session_factory() as session:
        stmt = text("SELECT text FROM directives WHERE id = :id")
        row = (await session.execute(stmt, {"id": directive_id.hex})).first()
    assert row is not None, f"directives row not found for id={directive_id}"
    persisted = row[0]
    assert isinstance(persisted, str)
    return persisted


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-discord (主要ケース、directive §確定 G 不可逆性)
# ---------------------------------------------------------------------------
class TestDiscordTokenMasked:
    """TC-IT-DRR-010-masking-discord: directive text 中の Discord Bot Token が redact される。"""

    async def test_discord_token_in_webhook_url_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:DISCORD_TOKEN> を返し、生トークンがディスク上に残らない。"""
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
    """TC-IT-DRR-010-masking-anthropic: save 時に Anthropic API key が redact される。"""

    async def test_anthropic_key_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:ANTHROPIC_KEY> を返し、生 key が含まれない。"""
        directive_text = f"ANTHROPIC_API_KEY={_ANTHROPIC_TOKEN} を使ってClaude APIを呼ぶこと"
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] directives.text missing Anthropic redaction sentinel. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Raw Anthropic API key leaked into directives.text. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-github
# ---------------------------------------------------------------------------
class TestGitHubPatMasked:
    """TC-IT-DRR-010-masking-github: save 時に GitHub PAT が redact される。"""

    async def test_github_pat_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:GITHUB_PAT> を返し、生 PAT が含まれない。"""
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
            f"[FAIL] Raw GitHub PAT leaked into directives.text. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-bearer
# ---------------------------------------------------------------------------
class TestBearerTokenMasked:
    """TC-IT-DRR-010-masking-bearer: Authorization: Bearer XXX が redact される。"""

    async def test_bearer_token_redacted(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:BEARER> を返し、生 Bearer トークンが含まれない。"""
        directive_text = f"APIコール時は Authorization: Bearer {_BEARER_TOKEN} を使うこと"
        directive = make_directive(target_room_id=seeded_room_id, text=directive_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        persisted = await _read_persisted_text(session_factory, directive.id)

        assert _BEARER_SENTINEL in persisted, (
            f"[FAIL] directives.text missing Bearer redaction sentinel. Persisted: {persisted!r}"
        )
        assert _BEARER_TOKEN not in persisted, (
            f"[FAIL] Raw Bearer token leaked into directives.text. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-no-secret (passthrough)
# ---------------------------------------------------------------------------
class TestNoSecretPassthrough:
    """TC-IT-DRR-010-masking-no-secret: 平文 directive text は変更されずに保存される。"""

    async def test_plain_text_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """secret を含まない directive text はバイト等価で永続化される。

        マスキングが限定的であること（既知の secret パターンのみ redact、
        gateway は平文に過剰反応しない）を確認する。
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
    """TC-IT-DRR-010-masking-roundtrip: §確定 G §不可逆性 ── find_by_id はマスク済みを返す。

    一度 Discord Bot Token が save 時にマスクされたら、生トークンは DB から
    物理的に復元不能。find_by_id は redaction sentinel を持つ Directive を返さねばならず、
    元のトークンを返してはならない。
    """

    async def test_find_by_id_returns_masked_text(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """生の Discord webhook URL を save → find_by_id → text == マスク済み形式。"""
        raw_text = f"配信先: https://discord.com/api/webhooks/12345/{_DISCORD_TOKEN}"
        directive = make_directive(target_room_id=seeded_room_id, text=raw_text)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert _DISCORD_SENTINEL in restored.text, (
            f"[FAIL] find_by_id did not return masked text.\nRestored text: {restored.text!r}"
        )
        assert _DISCORD_TOKEN not in restored.text, (
            f"[FAIL] directive §確定 G §不可逆性 violated: raw Discord token recovered after "
            f"round-trip.\nRestored text: {restored.text!r}"
        )
        # ラウンドトリップした Directive は元と等価ではない（マスキングで変わるため）
        assert restored != directive, (
            "[FAIL] round-trip equality should not hold for masked directive text; "
            "masking might be a no-op."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-010-masking-multiple
# ---------------------------------------------------------------------------
class TestMultipleSecretsAllRedacted:
    """TC-IT-DRR-010-masking-multiple: 1 directive 内の
    3 種以上の secret すべてが redact される。"""

    async def test_multiple_secrets_all_redacted_in_one_pass(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """1 つの directive text 中の Discord + Anthropic + GitHub すべてが redact される。"""
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

        # 3 種の sentinel すべてが含まれる
        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] Discord sentinel missing in multi-secret directive. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_SENTINEL in persisted, (
            f"[FAIL] Anthropic sentinel missing in multi-secret directive. Persisted: {persisted!r}"
        )
        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] GitHub sentinel missing in multi-secret directive. Persisted: {persisted!r}"
        )
        # 3 種の生トークンはいずれも含まれない
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Discord token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Anthropic token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] GitHub PAT survived multi-secret masking. Persisted: {persisted!r}"
        )
