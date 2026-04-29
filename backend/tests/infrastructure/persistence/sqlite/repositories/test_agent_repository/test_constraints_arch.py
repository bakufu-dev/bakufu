"""Agent Repository: DB 制約 + arch-test 相互参照。

TC-IT-AGR-007 / TC-UT-AGR-009 ── **partial unique index による二重防衛**
(§確定 G) と CI Layer 2 arch-test の相互参照を扱う。

§確定 G: 同一 ``agent_id`` 配下の ``is_default = 1`` 行は **2 層** で禁止される:

1. **Aggregate レベル** (Agent VO チェーン内の ``_validate_default_provider_count``)
   が構築時に違反を捕捉する。
2. **DB レベル** の partial unique index ``uq_agent_providers_default``
   (``WHERE is_default = 1``) が INSERT を物理的に拒否 ── Aggregate を迂回する
   コード経路（raw SQL、チェックを忘れた将来の Repository 実装、
   dump/restore マイグレーション等）に対する最終防衛線。

本テストは raw SQL で Aggregate を迂回することで **層 2 を単独で** 検証する。
partial index DDL を落とす回帰は 2 回目の INSERT を静かに成功させてしまう ──
本テストはそれを派手に失敗させる。
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
    """TC-IT-AGR-007: 同一 agent_id 配下での ``is_default=1`` x 2 は IntegrityError を起こす。

    Aggregate の ``_validate_default_provider_count`` が第 1 層。本テストは
    raw SQL を直書きして Aggregate を迂回するため、partial unique index のみが
    静かな破壊との間に立つ唯一の防衛線となる。1 回目の INSERT は成功し、
    2 回目は ``IntegrityError``（SQLAlchemy が SQLite の UNIQUE 制約違反を
    ``IntegrityError`` にマップするため、``DBAPIError`` 形のラッパでも可）を起こさねばならない。
    """

    async def test_duplicate_default_provider_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """TC-IT-AGR-007: 同一 agent_id に対する ``is_default=1`` の 2 行は DB が拒否する。"""
        from sqlalchemy.exc import IntegrityError

        # agent_providers の FK が解決できるよう Agent 行を seed する。
        # テストを DB 層に集中させるため、Repository をすべて迂回し、
        # 全工程を raw SQL で行う。
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

        # 最初のデフォルト provider ── 成功するはず。
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

        # 同じ agent_id に対する 2 つ目のデフォルト provider ── (agent_id,
        # provider_kind) UNIQUE を踏まないよう provider_kind は別にし、
        # is_default=1 の partial unique index のみが発火するようにする。
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
                        # 別の provider_kind ── したがって (agent_id, provider_kind)
                        # UNIQUE には引っかからず、partial index のみが該当する防衛線となる。
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
        """同一 agent_id 配下の ``is_default=0`` 行は partial index の対象外。

        partial の性質を確認する: ``WHERE is_default = 1`` のため、``is_default = 0``
        の行は同一 agent_id 配下で自由に共存できる（(agent_id, provider_kind)
        UNIQUE の制約のみが残る）。
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

        # 2 つの provider ── 両方 is_default=False、別 kind ── 両方とも成功する。
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

        # 両方の行が存在し、partial index は発火していない。
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
    """(agent_id, provider_kind) UNIQUE が同 kind 2 回挿入を拒否する。"""

    async def test_duplicate_agent_provider_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """同じ (agent_id, provider_kind) を 2 回挿入 → IntegrityError。"""
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
                        "provider_kind": "claude_code",  # 同じ kind
                        "model": "haiku-3.5",
                        "is_default": False,
                    },
                )


# ---------------------------------------------------------------------------
# TC-UT-AGR-009: Layer 2 arch-test reference — Agent rows registered
# ---------------------------------------------------------------------------
class TestArchTestRegistrationStructure:
    """TC-UT-AGR-009: ``test_masking_columns.py`` の parametrize リストが Agent を含む。

    CI Layer 2 arch test が 3 つの Agent テーブルをカバーするよう拡張されたかを
    相互チェックする。これらの登録を落とす将来の PR（例: リファクタ中の事故）は
    過剰マスキング / 不足マスキングの変更を静かに着地させてしまう ──
    本テストがそれを捕捉する。
    """

    async def test_agents_prompt_body_in_masking_contract(self) -> None:
        """``agents.prompt_body`` が contract リストに MaskedText として登録されている。"""
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
        """``agent_providers`` / ``agent_skills`` は no-mask テーブル。"""
        from tests.architecture.test_masking_columns import (
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        assert "agent_providers" in _NO_MASK_TABLES
        assert "agent_skills" in _NO_MASK_TABLES

    async def test_agents_partial_mask_template_registered(self) -> None:
        """``agents`` が partial-mask テンプレートリストに登録されている。"""
        from tests.architecture.test_masking_columns import (
            _PARTIAL_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        partial = dict(_PARTIAL_MASK_TABLES)
        assert partial.get("agents") == "prompt_body", (
            f"[FAIL] agents partial-mask declared {partial.get('agents')!r}, "
            f"expected 'prompt_body'.\n"
            f"Next: §逆引き表 freezes prompt_body as the sole masked column on agents."
        )
