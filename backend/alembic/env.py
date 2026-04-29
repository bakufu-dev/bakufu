"""bakufu Backend の Alembic 環境。

2 つの実行モードを持つ:

* **プログラム経由** — Bootstrap stage 3 がアクティブな asyncio ループ内から
  ``command.upgrade`` を呼び出す。マイグレーションランナーが事前に同期版の
  :class:`Connection` を確立し ``config.attributes`` に格納する。本モジュールは
  新しい asyncio ループを開く代わりにそれを再利用する。
* **CLI 単独** — シェルから ``alembic upgrade head`` を実行する場合。まだ
  asyncio ループが存在しないため、エンジンを自前で開き ``asyncio.run`` で
  アップグレードを実行する。

両経路とも同じ ``target_metadata`` を共有し、autogenerate がすべての横断テーブルを
認識できるようにしている。
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from alembic import context
from bakufu.infrastructure.persistence.sqlite.base import Base

# テーブルモジュールを import することで ORM マッピング・リスナーが metadata に
# 登録され、autogenerate から参照できるようにする。
from bakufu.infrastructure.persistence.sqlite.tables import (  # noqa: F401
    audit_log,
    outbox,
    pid_registry,
)
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

# BUG-PF-002 修正: ここで ``logging.config.fileConfig`` を**呼ばない**こと。
# Alembic 既定の ``env.py`` テンプレートは ``alembic.ini`` からロガー設定を読み込むが、
# (a) ``disable_existing_loggers=True`` により設定済みの bakufu ロガーを全て無効化し、
# (b) ルートロガーを ``WARN`` に引き上げてしまう。いずれの副作用も、stage 3 完了後に
# Bootstrap stages 4〜8 の INFO/WARN テレメトリが本番ログから失われる原因となる。
# bakufu はロギングを先に ``logging.basicConfig``（本番）または pytest の caplog
# （テスト）で構成する。Alembic 自身の ``alembic.runtime.migration`` ロガーは root を
# 継承するため、マイグレーションの進捗行は引き続き出力される。
config = context.config

target_metadata = Base.metadata


def _resolve_url() -> str:
    """SQLAlchemy URL を選択する。

    優先順位:
    1. ``BAKUFU_ALEMBIC_URL`` 環境変数（テスト環境 / CI でのオーバーライド）。
    2. ``BAKUFU_DATA_DIR`` 環境変数 → ``<dir>/bakufu.db``。
    3. ``alembic.ini`` の ``sqlalchemy.url`` 値（CLI フォールバック）。
    """
    override = os.environ.get("BAKUFU_ALEMBIC_URL")
    if override:
        return override
    data_dir = os.environ.get("BAKUFU_DATA_DIR")
    if data_dir:
        return f"sqlite+aiosqlite:///{Path(data_dir) / 'bakufu.db'}"
    raw = config.get_main_option("sqlalchemy.url")
    if raw is None:
        raise RuntimeError(
            "alembic env: sqlalchemy.url not configured and no "
            "BAKUFU_DATA_DIR / BAKUFU_ALEMBIC_URL set"
        )
    return raw


def run_migrations_offline() -> None:
    """接続を開かずに SQL をレンダリングする。"""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """CLI 単独経路: エンジンを構築してアップグレードを実行する。"""
    connectable: AsyncEngine = async_engine_from_config(
        {"sqlalchemy.url": _resolve_url()},
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    # プログラム経由（Bootstrap stage 3）: 呼び出し側が既に ``connection.run_sync``
    # 内で同期 Connection を開き、``config.attributes['connection']`` に格納している。
    injected = config.attributes.get("connection", None)
    if isinstance(injected, Connection):
        _do_run_migrations(injected)
        return
    # CLI 単独: エンジンと asyncio ループを自前で立ち上げる。
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
