"""PRAGMA を強制する SQLite ``AsyncEngine`` ファクトリ（§確定 D）。

確定 D-2（Schneier 重大 2）に従い、2 種類のエンジンを用意する:

* :func:`create_engine` — **アプリケーション** エンジン。Alembic 以外の
  全箇所で使用する。``defensive=ON`` と ``writable_schema=OFF`` を含む
  8 つの PRAGMA を設定するので、``audit_log`` トリガが実行時に
  ``DROP`` されることはない。
* :func:`create_migration_engine` — **マイグレーション** エンジン。
  Bootstrap stage 3 の内側でのみ使用し、その後 ``dispose()`` する。
  Alembic が DDL を発行できるよう ``defensive`` / ``writable_schema``
  を緩める。

PRAGMA 一覧は基盤の同期エンジンに対する ``connect`` イベントリスナで
接続ごとに設定する — ここが SQLAlchemy / aiosqlite が DBAPI 接続を
ORM 活動の前に渡してくる箇所である。
"""

from __future__ import annotations

import logging
from typing import Final

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

# 確定 D-1: アプリケーション接続向けの 8 つの PRAGMA。
# 順序が重要 — `journal_mode=WAL` を最初に、defensive ガードを最後に置き、
# それらが以後すべてに対して有効になるようにする。
_APP_PRAGMAS: Final[tuple[tuple[str, str], ...]] = (
    ("journal_mode", "WAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
    ("synchronous", "NORMAL"),
    ("temp_store", "MEMORY"),
    ("defensive", "ON"),
    ("writable_schema", "OFF"),
    ("trusted_schema", "OFF"),
)

# 確定 D-2: マイグレーション用エンジンは defensive ガードを緩めて Alembic が
# CREATE TABLE / CREATE TRIGGER を発行できるようにする。それ以外の PRAGMA は
# 同一に保つ — 並行性 / FK / busy_timeout はマイグレーション中も依然重要。
_MIGRATION_PRAGMAS: Final[tuple[tuple[str, str], ...]] = (
    ("journal_mode", "WAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
    ("synchronous", "NORMAL"),
    ("temp_store", "MEMORY"),
    ("defensive", "OFF"),
    ("writable_schema", "ON"),
)


def create_engine(url: str, *, debug: bool = False) -> AsyncEngine:
    """アプリケーションレベルの :class:`AsyncEngine` を構築する。

    Args:
        url: SQLAlchemy URL（例: ``sqlite+aiosqlite:///<path>``）。
        debug: 開発時に詳細な SQL ログを出すため
            ``create_async_engine(echo=...)`` に転送する。

    connect 時に確定 D-1 の 8 つの PRAGMA リスナを配線する。
    秘密情報のマスキングは
    :mod:`bakufu.infrastructure.persistence.sqlite.base` の
    ``Masked*`` カラム :class:`TypeDecorator` アダプタで強制される。
    そのレイヤは ORM フラッシュと Core
    ``insert(table).values(...)`` の双方の ``process_bind_param`` で
    発火する（BUG-PF-001 の修正）ため、マスキングのために engine レベルの
    リスナを追加する必要はない。
    """
    engine = create_async_engine(url, echo=debug, future=True)
    event.listen(engine.sync_engine, "connect", _set_app_pragmas)
    return engine


def create_migration_engine(url: str) -> AsyncEngine:
    """マイグレーション専用の :class:`AsyncEngine` を構築する（確定 D-2）。

    Bootstrap stage 3（Alembic ``upgrade head``）からのみ使用し、直後に
    ``dispose()`` すること。アプリケーションコードと共有してはならない。
    """
    engine = create_async_engine(url, echo=False, future=True)
    event.listen(engine.sync_engine, "connect", _set_migration_pragmas)
    return engine


def _apply_pragmas(
    dbapi_conn: object,
    pragmas: tuple[tuple[str, str], ...],
) -> None:
    """各ペアに対して ``PRAGMA name=value;`` を適用する。

    一部の PRAGMA（``defensive`` / ``writable_schema`` / ``trusted_schema``）
    は SQLite 3.31+ にしか存在しない。古いビルドでは ``execute`` が例外を
    送出するためスキップをログに出す。それ以外の PRAGMA は必須なので
    失敗は伝播し、Bootstrap が MSG-PF-002 へ変換する。
    """
    cursor_factory = getattr(dbapi_conn, "cursor", None)
    if cursor_factory is None:
        return
    cursor = cursor_factory()
    try:
        for name, value in pragmas:
            try:
                cursor.execute(f"PRAGMA {name}={value}")
            except Exception as exc:
                if name in {"defensive", "writable_schema", "trusted_schema"}:
                    # 確定 D-4 のフォールバック: ログ + 継続。
                    # 脅威モデルのエントリがこのケースをカバーしている。
                    logger.warning(
                        "[WARN] PRAGMA %s=%s not supported on this "
                        "SQLite build (%r); falling back to OS-level "
                        "isolation per threat-model §T2",
                        name,
                        value,
                        exc,
                    )
                    continue
                raise
    finally:
        cursor.close()


def _set_app_pragmas(dbapi_conn: object, _connection_record: object) -> None:
    """アプリケーションエンジン用の ``connect`` リスナ。"""
    _apply_pragmas(dbapi_conn, _APP_PRAGMAS)


def _set_migration_pragmas(
    dbapi_conn: object,
    _connection_record: object,
) -> None:
    """マイグレーションエンジン用の ``connect`` リスナ。"""
    _apply_pragmas(dbapi_conn, _MIGRATION_PRAGMAS)


__all__ = [
    "create_engine",
    "create_migration_engine",
]
