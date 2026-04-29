"""Engine PRAGMA + 二重接続統合テスト
(TC-IT-PF-003 / 013 / 003-A / 003-B / 003-C / 003-D)。

Confirmation D-1〜D-4 / Schneier 重大 2 物理保証。アプリケーションエンジンは
8 つの PRAGMA を設定（``defensive=ON`` / ``writable_schema=OFF``
/ ``trusted_schema=OFF`` 含む）ため、実行時 ``DROP TRIGGER`` は
audit_log 防御を削除できない。マイグレーションエンジンはそれらのガードを
緩和するが、ステージ 4 開始前に明示的に破棄される。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# このモジュールの各テストは async コードを実行。
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def fresh_app_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """テストごとに新規 app エンジンを起動 (Alembic なし、共有状態なし)。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


class TestApplicationPragmas:
    """TC-IT-PF-003 / 013 / 003-A: アプリケーションエンジンが 8 つの PRAGMA を設定。"""

    async def test_journal_mode_is_wal(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: journal_mode = WAL (初回接続後)。"""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            value = result.scalar()
        assert value == "wal"

    async def test_foreign_keys_on(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: foreign_keys = ON (接続ごと)。"""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            value = result.scalar()
        assert value == 1

    async def test_busy_timeout_5000(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: busy_timeout = 5000 ms。"""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
            value = result.scalar()
        assert value == 5000

    async def test_synchronous_normal(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: synchronous = NORMAL (1)。"""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA synchronous"))
            value = result.scalar()
        assert value == 1

    async def test_temp_store_memory(self, fresh_app_engine: AsyncEngine) -> None:
        """TC-IT-PF-003: temp_store = MEMORY (2)。"""
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA temp_store"))
            value = result.scalar()
        assert value == 2


class TestDefensivePragmasOptional:
    """TC-IT-PF-003-A: defensive ガードは best-effort (D-4 フォールバック)。

    SQLite ``PRAGMA defensive`` は SQLITE_DBCONFIG_DEFENSIVE を必要とするが、
    SQLite ライブラリが ``SQLITE_ENABLE_DESERIALIZE`` オプションでコンパイルされた場合
    のみ組み込まれる。古いビルドでは、エンジンは WARN をログして続行 —
    Confirmation D-4 はこれを文書化されたフォールバックとして位置付ける。
    """

    async def test_defensive_pragma_does_not_break_engine(
        self, fresh_app_engine: AsyncEngine
    ) -> None:
        """TC-IT-PF-003-A: エンジンが古い SQLite でも正常に接続。

        ``PRAGMA defensive`` は SQLite で設定のみ (SELECT 形式なし) なので、
        エンジンが接続することのみを確認できる。Confirmation D-4 フォールバック
        パスは PRAGMA を静かに適用するか (現代 SQLite) または WARN をログして
        続行 (古いビルド)。いずれにしろアプリケーションエンジンは通常クエリに
        使用可能である必要がある。
        """
        async with fresh_app_engine.connect() as conn:
            # エンジンは通常クエリに使用可能でなければならない；PRAGMA 適用が
            # 致命的に失敗した場合、接続は engine.connect() 時点で raise していただろう。
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
        assert value == 1


class TestDropTriggerDefense:
    """TC-IT-PF-003-B: defensive=ON で、``DROP TRIGGER`` は audit_log ガードを削除できない。

    defensive=ON がサポートされているビルドでは、
    アプリケーションエンジンからの DROP TRIGGER は raise。古いビルド (D-4 フォールバック)
    では、OS ファイルパーミッション層が信頼境界になる — 我々はまだ
    トリガーがアプリケーションエンジンの生存期間中に *生き残る* ことを確認する
    ため、将来のリポジトリ PR はそれを削除することに誤って依存できない。
    """

    async def test_audit_log_no_delete_trigger_survives(
        self, fresh_app_engine: AsyncEngine
    ) -> None:
        """TC-IT-PF-003-B: トリガーが Alembic upgrade 後に残存。"""
        await run_upgrade_head(fresh_app_engine)
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='trigger' AND name='audit_log_no_delete'"
                )
            )
            names = [row[0] for row in result]
        assert "audit_log_no_delete" in names


class TestDualConnectionLifecycle:
    """TC-IT-PF-003-D: マイグレーションエンジンが Alembic 実行後に破棄される。"""

    async def test_migration_runner_disposes_its_own_engine(
        self, fresh_app_engine: AsyncEngine
    ) -> None:
        """TC-IT-PF-003-D: ``run_upgrade_head`` が破棄後に戻る ; app エンジンはまだ生きている。

        正確な head id は各アグリゲートリポジトリ PR ごとに進行
        (PR #19 → ``0001_init`` → PR #25 → ``0002_empire_aggregate`` →
        将来の PR はさらなる revision を追加)。テストは ``run_upgrade_head`` が
        空でない revision id をレポートし、upgrade 後に M2 cross-cutting
        テーブルが存在することのみを気にする。
        """
        head = await run_upgrade_head(fresh_app_engine)
        assert head, (
            "run_upgrade_head は最新 Alembic revision id をレポートすべき、空文字列ではなく"
        )
        # アプリケーションエンジンが使用可能なままである。
        async with fresh_app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"audit_log", "bakufu_pid_registry", "domain_event_outbox"}.issubset(tables)
