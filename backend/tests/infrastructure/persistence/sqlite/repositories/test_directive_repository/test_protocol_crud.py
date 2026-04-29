"""Directive Repository: Protocol サーフェス + 基本 CRUD + ライフサイクルカバレッジ。

TC-UT-DRR-001〜009 + TC-IT-DRR-LIFECYCLE.

REQ-DRR-001 / REQ-DRR-002 ── 4 メソッドの Protocol サーフェス (§確定 R1-A) +
基本 CRUD (find_by_id / count / save / Tx 境界) + ライフサイクル。

``docs/features/directive-repository/test-design.md`` 準拠。
Issue #34 — M2 0006。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.directive_repository import DirectiveRepository
from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
    SqliteDirectiveRepository,
)
from sqlalchemy import event

from tests.factories.directive import make_directive

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-DRR-001: Protocol 定義 + 4 メソッドサーフェス (§確定 R1-A)
# ---------------------------------------------------------------------------
class TestDirectiveRepositoryProtocol:
    """TC-UT-DRR-001: Protocol が 4 つの async メソッドを宣言する (§確定 R1-A)。"""

    async def test_protocol_declares_four_async_methods(self) -> None:
        """TC-UT-DRR-001: DirectiveRepository が find_by_id/count/save/find_by_room を持つ。"""
        assert hasattr(DirectiveRepository, "find_by_id")
        assert hasattr(DirectiveRepository, "count")
        assert hasattr(DirectiveRepository, "save")
        assert hasattr(DirectiveRepository, "find_by_room")

    async def test_protocol_does_not_have_find_by_task_id(self) -> None:
        """TC-UT-DRR-001: find_by_task_id は Protocol に含まれない（YAGNI）。

        §確定 R1-D 後続申し送り: find_by_task_id は task-repository PR
        （メソッド + INDEX + FK のクロージャを同時に行う）に先送り。
        ここに再出現したら、detailed-design.md の YAGNI 判断を
        設計ドキュメントを更新せずに反転させたことになる。
        """
        assert not hasattr(DirectiveRepository, "find_by_task_id"), (
            "[FAIL] DirectiveRepository.find_by_task_id must not exist (YAGNI).\n"
            "Next: remove find_by_task_id from the Protocol, or update "
            "detailed-design.md §確定 R1-D 後続申し送り first."
        )

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-DRR-001: SqliteDirectiveRepository が DirectiveRepository を満たす。

        変数アノテーションが静的型アサーションとして機能する。pyright strict は、
        Protocol の 4 メソッドのいずれかが欠落または誤シグネチャの場合、代入を拒否する。
        """
        async with session_factory() as session:
            repo: DirectiveRepository = SqliteDirectiveRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")
            assert hasattr(repo, "find_by_room")

    async def test_sqlite_repository_duck_typing_4_methods(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-DRR-001: ダックタイピングで実装に 4 メソッドすべてが存在することを確認する。"""
        async with session_factory() as session:
            repo = SqliteDirectiveRepository(session)
            for method_name in ("find_by_id", "count", "save", "find_by_room"):
                assert hasattr(repo, method_name), (
                    f"[FAIL] SqliteDirectiveRepository.{method_name} missing.\n"
                    f"Protocol requires exactly 4 methods (§確定 R1-A)."
                )


# ---------------------------------------------------------------------------
# TC-UT-DRR-002: find_by_id (REQ-DRR-002, 受入基準 3)
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-UT-DRR-002: find_by_id は保存済み Directive を取得する。未知の id は None。"""

    async def test_find_by_id_returns_saved_directive(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """find_by_id(directive.id) が保存済み Directive を返す。"""
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert fetched is not None
        assert fetched.id == directive.id
        assert fetched.text == directive.text

    async def test_find_by_id_returns_none_for_unknown_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """find_by_id(uuid4()) は例外を投げず None を返す。"""
        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(uuid4())
        assert fetched is None


# ---------------------------------------------------------------------------
# TC-UT-DRR-003: save ラウンドトリップ等価性 (REQ-DRR-002, 受入基準 4, §確定 R1-G)
# ---------------------------------------------------------------------------
class TestSaveRoundTrip:
    """TC-UT-DRR-003: save → find_by_id ラウンドトリップで全属性が保たれる。"""

    async def test_save_find_by_id_round_trip_all_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """全属性 (id/text/target_room_id/created_at/task_id) がラウンドトリップで保たれる。

        §確定 R1-G: created_at は SQLite ストア後も UTC tz-aware を維持しなければならない。
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert restored.id == directive.id
        assert restored.text == directive.text
        assert restored.target_room_id == directive.target_room_id
        assert restored.task_id == directive.task_id

    async def test_created_at_is_utc_timezone_aware_after_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """§確定 R1-G: created_at がラウンドトリップで UTC tz-aware datetime のまま残る。"""
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert restored.created_at.tzinfo is not None, (
            "[FAIL] created_at lost timezone info after round-trip.\n"
            "Next: verify UTCDateTime TypeDecorator returns tz-aware datetime."
        )

    async def test_task_id_none_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """§確定 R1-G: task_id=None が正しくラウンドトリップする。"""
        directive = make_directive(target_room_id=seeded_room_id, task_id=None)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert restored.task_id is None


# ---------------------------------------------------------------------------
# TC-UT-DRR-006: count() の SQL COUNT(*) 契約 (受入基準 8, §確定 R1-A D 補強)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-UT-DRR-006: count() は SELECT COUNT(*) を発行し、行を全件スキャンしない。"""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_room_id: UUID,
    ) -> None:
        """SQL ログが count() に対し SELECT count(*) FROM directives を示す。

        empire-repository §確定 D 補強の契約: count() は Directive 行を Python へ
        全件ストリームしてはならない。
        """
        for _ in range(2):
            directive = make_directive(target_room_id=seeded_room_id)
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(directive)

        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement.strip())

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            async with session_factory() as session:
                count = await SqliteDirectiveRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        directive_selects = [s for s in captured if "FROM directives" in s]
        assert directive_selects, "count() must issue at least one SELECT against directives"
        for stmt in directive_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(DirectiveRow)."
            )


# ---------------------------------------------------------------------------
# TC-UT-DRR-007: save の UPSERT 更新セマンティクス (受入基準 4)
# ---------------------------------------------------------------------------
class TestSaveUpsertSemantics:
    """TC-UT-DRR-007: 同一 id での再 save は行を更新する（UPSERT）。"""

    async def test_resave_updates_text(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """同じ directive.id で text を変更 → 最新の text が返る。"""
        original = make_directive(target_room_id=seeded_room_id, text="初期テキスト")
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(original)

        updated = original.model_copy(update={"text": "更新後テキスト"})
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.text == "更新後テキスト", (
            "[FAIL] UPSERT did not update text on re-save.\n"
            "Next: verify on_conflict_do_update sets text in the update set."
        )

    async def test_resave_does_not_duplicate_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """UPSERT により、同じ id を複数回 save しても件数は 1 のまま。"""
        directive = make_directive(target_room_id=seeded_room_id)
        for _ in range(3):
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            count = await SqliteDirectiveRepository(session).count()
        assert count == 1


# ---------------------------------------------------------------------------
# TC-UT-DRR-008: link_task 後の save ── task_id 更新 (§確定 R1-G)
# ---------------------------------------------------------------------------
class TestSaveAfterLinkTask:
    """TC-UT-DRR-008: link_task → 再 save で task_id カラムが更新される。"""

    async def test_link_task_and_resave_updates_task_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """directive.link_task(task_id) → save → find_by_id が更新後 task_id を返す。

        BUG-DRR-001 クロージャ (0007): directives.task_id → tasks.id RESTRICT FK が
        有効。directive.task_id を設定する前に実 tasks 行が存在しなければならない。
        """
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        from tests.factories.task import make_task

        original = make_directive(target_room_id=seeded_room_id, task_id=None)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(original)

        # BUG-DRR-001 クロージャ: 先にこの Directive を参照する実 Task を save する。
        real_task = make_task(room_id=seeded_room_id, directive_id=original.id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(real_task)

        new_task_id = real_task.id
        updated = original.link_task(new_task_id)  # type: ignore[arg-type]
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.task_id is not None
        assert restored.task_id == new_task_id, (
            f"[FAIL] task_id not updated after link_task → re-save.\n"
            f"Expected: {new_task_id}, Got: {restored.task_id}"
        )


# ---------------------------------------------------------------------------
# TC-UT-DRR-009: Tx 境界 (§確定 R1-B, empire §確定 B 踏襲)
# ---------------------------------------------------------------------------
class TestTxBoundary:
    """TC-UT-DRR-009: Repository は自動 commit せず、UoW 境界は呼び出し側が所有する。"""

    async def test_save_within_begin_persists(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """async with session.begin() 内の save は行を永続化する。"""
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)
        assert fetched is not None

    async def test_save_without_begin_does_not_persist(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """session.begin() なしの save は session クローズ後に行が残らない。

        begin() なしの場合、SQLAlchemy async session はデフォルトで autobegin するが、
        session 終了時に自動 commit はしない。暗黙トランザクションは、commit せず
        session コンテキストマネージャを抜けた時点でロールバックされる。
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session:
            # session.begin() なし → __aexit__ で自動ロールバック
            await SqliteDirectiveRepository(session).save(directive)
            # commit しない

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)
        assert fetched is None, (
            "[FAIL] Repository auto-committed without session.begin().\n"
            "Next: verify save() does not call session.commit() (empire §確定 B 踏襲)."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-LIFECYCLE: 4 メソッドのフルライフサイクル (§確定 R1-F + R1-G)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-IT-DRR-LIFECYCLE: save → find_by_room → save(更新) → count → find_by_id。"""

    async def test_full_lifecycle_4_method(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """4 メソッドのフルライフサイクル: save x3 → find_by_room →
        link_task+resave → count → find_by_id。

        §確定 R1-F (save 1 引数) と §確定 R1-G (task_id 更新) を、
        モックなしのリアルな end-to-end シーケンスで検証する。
        """
        # Step 1: 3 件の directive を save
        now = datetime.now(UTC)
        d1 = make_directive(
            target_room_id=seeded_room_id,
            text="ディレクティブ1",
            created_at=now,
        )
        import asyncio

        await asyncio.sleep(0)  # 順序保証のため yield
        d2 = make_directive(
            target_room_id=seeded_room_id,
            text="ディレクティブ2",
            created_at=now,
        )
        d3 = make_directive(
            target_room_id=seeded_room_id,
            text="ディレクティブ3",
            created_at=now,
        )

        async with session_factory() as session, session.begin():
            repo = SqliteDirectiveRepository(session)
            await repo.save(d1)
            await repo.save(d2)
            await repo.save(d3)

        # Step 2: find_by_room が 3 件の directive を返す
        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        assert len(results) == 3

        # Step 3: link_task → 再 save
        # BUG-DRR-001 クロージャ (0007): directives.task_id → tasks.id RESTRICT FK。
        # directive.task_id を設定する前に d1 を参照する実 Task を save しなければならない。
        from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
            SqliteTaskRepository,
        )

        from tests.factories.task import make_task

        task_for_d1 = make_task(room_id=seeded_room_id, directive_id=d1.id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_for_d1)

        new_task_id = task_for_d1.id
        d1_updated = d1.link_task(new_task_id)  # type: ignore[arg-type]
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(d1_updated)

        # Step 4: count → 3（再 save は UPSERT であり INSERT ではない）
        async with session_factory() as session:
            count = await SqliteDirectiveRepository(session).count()
        assert count == 3

        # Step 5: find_by_id(d2.id) → d2 の属性
        async with session_factory() as session:
            via_id = await SqliteDirectiveRepository(session).find_by_id(d2.id)
        assert via_id is not None
        assert via_id.text == d2.text

        # Step 6: d1_updated に task_id が設定されている
        async with session_factory() as session:
            d1_restored = await SqliteDirectiveRepository(session).find_by_id(d1.id)
        assert d1_restored is not None
        assert d1_restored.task_id == new_task_id

    async def test_save_directive_resolves_fk_from_directive_target_room_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """§確定 R1-F: save(directive) は directive.target_room_id から FK を読み取る。

        1 引数 save パターン: Directive は target_room_id を自身の属性として持つため、
        Repository はそれを直接読み取る。追加の empire_id 引数なしで save が成功するべき。
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            # 第二引数不要 ── §確定 R1-F の標準パターン
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)
        assert fetched is not None
        assert fetched.target_room_id == seeded_room_id
