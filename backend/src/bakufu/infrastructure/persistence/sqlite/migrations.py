"""Bootstrap stage 3 用の Alembic マイグレーション ランナー（Confirmation D-3）。

Bootstrap stage 3 は :func:`run_upgrade_head` を *アプリケーション* エンジンで
呼び出す。本モジュールはエンジンを新しい **マイグレーション** エンジン
（``defensive=OFF`` / ``writable_schema=ON``）に置き換え、Alembic を ``head``
まで実行した後で破棄する。アプリケーション エンジンは Alembic から触れられない —
Schneier 重大 2 の防御的保証は維持される。
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine

from bakufu.infrastructure.persistence.sqlite.engine import create_migration_engine

logger = logging.getLogger(__name__)

# Backend パッケージ レイアウト:
# backend/src/bakufu/infrastructure/persistence/sqlite/migrations.py
# alembic.ini は backend/alembic.ini に存在。
_ALEMBIC_INI: Path = Path(__file__).resolve().parents[5] / "alembic.ini"


async def run_upgrade_head(app_engine: AsyncEngine) -> str:
    """一時的なマイグレーション エンジン経由で ``alembic upgrade head`` を適用する。

    Args:
        app_engine: アプリケーション レベル エンジン。マイグレーション エンジンが
            同じ DB ファイルを対象とできるよう、URL のみを読む。

    Returns:
        現在スキーマが到達している ``head`` リビジョン識別子。Bootstrap stage 3
        完了ログに含めるために使う。

    Raises:
        Exception: Alembic 自体は多様なエラーを表面化する。Bootstrap がこれらを
            :class:`BakufuMigrationError` に変換する。
    """
    url = str(app_engine.url)
    migration_engine = create_migration_engine(url)
    try:
        async with migration_engine.connect() as connection:

            def _do_upgrade(sync_connection: object) -> None:
                from alembic import command

                cfg = Config(str(_ALEMBIC_INI))
                cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
                cfg.attributes["connection"] = sync_connection
                command.upgrade(cfg, "head")

            await connection.run_sync(_do_upgrade)

        cfg = Config(str(_ALEMBIC_INI))
        cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        return head or ""
    finally:
        await migration_engine.dispose()


__all__ = ["run_upgrade_head"]
