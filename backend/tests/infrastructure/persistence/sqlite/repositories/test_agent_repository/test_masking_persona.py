"""Agent Repository: §確定 H — agents.prompt_body への MaskedText 配線。

**Schneier 申し送り #3 の物理保証**。本モジュールは PR #45 の中核テストファイルであり、
persistence-foundation #23 のフック構造が、実際の SQLite DB 上で
secret を含む 7 種類の prompt-body 形状に対しエンドツーエンドで動作することを検証する:

1. **anthropic** — ``ANTHROPIC_API_KEY=sk-ant-api03-XXX...`` → ``<REDACTED:ANTHROPIC_KEY>``
2. **github** — ``ghp_XXX...`` → ``<REDACTED:GITHUB_PAT>``
3. **openai** — ``sk-XXX...`` → ``<REDACTED:OPENAI_KEY>``
4. **bearer** — ``Authorization: Bearer XXX`` → ``<REDACTED:BEARER>``
5. **no-secret** — secret を含まない prompt → 変更されない（passthrough）
6. **roundtrip** — §確定 H §不可逆性: ``find_by_id`` はマスク済み形式を返す
   （生トークンは DB から復元不能）
7. **multiple** — 1 つの prompt 中の 3 種以上の secret がすべて redact される。

各検証は **raw SQL SELECT** で永続化された ``agents.prompt_body`` を読み取り、
ディスクに到達した literal バイトを観測する
（``MaskedText.process_result_value`` を迂回しても問題ない ── このフックは恒等関数
であり、ストアした文字列をそのまま返すため、ここで読む値はディスク上の値そのものとなる）。

``docs/features/agent-repository/test-design.md`` TC-IT-AGR-006-masking-* 準拠。
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


# 実形（合成）secret トークン。パターン長は masking gateway の正規表現
# (masking.py L62-93) と一致させる必要がある ── でなければトークンが redact されず、
# テストが誤った理由で pass してしまう（生 → grep がトークンを見つけない → false negative）。
_ANTHROPIC_TOKEN = "sk-ant-api03-" + "A" * 60
_GITHUB_TOKEN = "ghp_" + "X" * 40
_OPENAI_TOKEN = "sk-" + "B" * 50  # sk- 後に 20 文字以上、かつ sk-ant- 以外（negative lookahead）
_BEARER_TOKEN = "eyJhbGciOi.tokenpart.signature"

# Redaction sentinel (masking.py L62-93)。
_ANTHROPIC_SENTINEL = "<REDACTED:ANTHROPIC_KEY>"
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"
_OPENAI_SENTINEL = "<REDACTED:OPENAI_KEY>"
_BEARER_SENTINEL = "<REDACTED:BEARER>"


def _make_agent_with_prompt(prompt_body: str, *, empire_id: UUID) -> Agent:
    """Persona に ``prompt_body`` を持たせた Agent を構築する。

    デフォルト factory は他のフィールドを合成だが妥当な値で埋め、
    ここでは ``persona.prompt_body`` のみ上書きしてテスト対象の secret パターンを注入する。
    ``empire_id`` は INSERT 時に ``empires.id`` への FK を解決するために必須。
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
    """Raw-SQL SELECT で ``agents.prompt_body`` の literal バイトを取得する。

    ``MaskedText.process_result_value`` を迂回する必要はない ── このフックは恒等関数
    （ストアされた文字列をそのまま返す）であるため、ここで読む値はディスク上の値と一致する。
    意図を明示的にし、ORM-declarative metadata から独立させるために ``text()`` を用いる。
    """
    async with session_factory() as session:
        stmt = text("SELECT prompt_body FROM agents WHERE id = :id")
        # SQLAlchemy の UUIDStr TypeDecorator は ``.hex`` で格納するため、
        # WHERE 句がレコードに当たるよう ``.hex`` で照合する。
        row = (await session.execute(stmt, {"id": agent_id.hex})).first()
    assert row is not None, f"agents row not found for id={agent_id}"
    persisted = row[0]
    assert isinstance(persisted, str)
    return persisted


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-anthropic
# ---------------------------------------------------------------------------
class TestAnthropicKeyMasked:
    """TC-IT-AGR-006-masking-anthropic: save 時に Anthropic API key が redact される。"""

    async def test_anthropic_key_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:ANTHROPIC_KEY>`` を返し、生トークンが含まれない。"""
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
    """TC-IT-AGR-006-masking-github: save 時に GitHub PAT が redact される。"""

    async def test_github_pat_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:GITHUB_PAT>`` を返し、生 PAT が含まれない。"""
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
    """TC-IT-AGR-006-masking-openai: save 時に OpenAI API key が redact される。"""

    async def test_openai_key_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:OPENAI_KEY>`` を返し、生トークンが含まれない。

        masking gateway は **negative lookahead** を用いるため、Anthropic の
        ``sk-ant-`` プレフィックスは OpenAI と誤分類されない。ここでは
        Anthropic ではない ``sk-...`` を渡している。
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
    """TC-IT-AGR-006-masking-bearer: Authorization: Bearer XXX が redact される。"""

    async def test_bearer_token_redacted_in_persisted_prompt(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Raw-SQL SELECT が ``<REDACTED:BEARER>`` を返し、生トークンが含まれない。"""
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
    """TC-IT-AGR-006-masking-no-secret: 平文 prompt は変更されずに保存される。"""

    async def test_plain_prompt_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Schneier-#6 の secret を含まない prompt はバイト等価で永続化される。

        マスキングが **限定的** であることを確認する ── 既知の secret パターンのみ
        redact され、masking gateway は平文に対し過剰反応しない。このチェックがないと、
        masking gateway を ``str.replace_all('a', '<X>')`` に置き換えた回帰により
        prompt が静かに破壊されてしまう。
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
    """TC-IT-AGR-006-masking-roundtrip: §確定 H §不可逆性 ── find_by_id はマスク済みを返す。

    一度 secret が save 時にマスクされたら、生トークンは DB から **物理的に復元不能**
    である。したがって ``find_by_id`` は redaction sentinel を持つ Persona を返す
    べきであり、元のトークンを返してはならない。マスクされた prompt を検出して
    LLM へのディスパッチを拒否することは ``feature/llm-adapter`` の責務（申し送り #1）であり、
    Repository の契約は「戻ってくるのはマスク済みの形式」である。
    """

    async def test_find_by_id_returns_masked_prompt_body(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """生で save → find_by_id → persona.prompt_body == マスク済み形式。"""
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
        # ラウンドトリップした Agent は元の Agent と等価ではない（prompt_body が変わるため）。
        # この非対称性を文書化された設計契約として固定する。
        assert restored != agent, (
            "[FAIL] round-trip equality should not hold for masked prompts; "
            "if this passes, masking might be a no-op."
        )


# ---------------------------------------------------------------------------
# TC-IT-AGR-006-masking-multiple
# ---------------------------------------------------------------------------
class TestMultipleSecretsAllRedacted:
    """TC-IT-AGR-006-masking-multiple: 1 prompt 中の 3 種以上の secret がすべて redact される。"""

    async def test_multiple_secrets_all_redacted_in_one_pass(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """anthropic + github + bearer を含む prompt がすべて完全に redact される。

        マスキングが **包括的** であることを確認する ── 1 つの redaction を適用しても
        他の redaction が短絡されない。gateway はすべての正規表現パターンを反復処理する。
        本テストはこの動作を固定する。
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

        # 3 種の sentinel がすべて含まれる。
        assert _ANTHROPIC_SENTINEL in persisted
        assert _GITHUB_SENTINEL in persisted
        assert _BEARER_SENTINEL in persisted
        # 3 種の生トークンはいずれも含まれない。
        assert _ANTHROPIC_TOKEN not in persisted, (
            f"[FAIL] Anthropic token survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] GitHub PAT survived multi-secret masking. Persisted: {persisted!r}"
        )
        assert _BEARER_TOKEN not in persisted, (
            f"[FAIL] Bearer token survived multi-secret masking. Persisted: {persisted!r}"
        )
