"""LiteBootstrap — admin-cli 用 DB 接続のみの軽量初期化（§確定 A）。

フル Bootstrap（8 Stage）のうち、admin-cli に必要な Stage 1（DATA_DIR 解決）+
Stage 4（SQLAlchemy engine 初期化）のみを実行する。

Alembic Migration / Outbox Dispatcher / StageWorker / FastAPI は起動しない。
短命プロセス（admin-cli）に不要なコンポーネントを起動しない（関心の分離）。

設計書: docs/features/admin-cli/cli/detailed-design.md §確定 A
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import NoReturn

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

_ENV_DATA_DIR = "BAKUFU_DATA_DIR"
_DB_FILENAME = "bakufu.db"

# MSG-AC-CLI-001: DB 接続失敗
_MSG_AC_CLI_001_TMPL = (
    "[FAIL] bakufu DB に接続できませんでした（path: {db_path}）。\n"
    "Next: BAKUFU_DATA_DIR 環境変数と DB ファイルの存在を確認してください。"
)


class LiteBootstrap:
    """admin-cli 用の軽量 DB 初期化（§確定 A）。

    `setup_db()` を呼ぶと ``async_sessionmaker`` を返す。
    ``data_dir=None`` 時は ``BAKUFU_DATA_DIR`` 環境変数を参照する。
    """

    @staticmethod
    async def setup_db(data_dir: Path | None = None) -> async_sessionmaker[AsyncSession]:
        """DATA_DIR を解決して SQLAlchemy asyncio engine を初期化する。

        Args:
            data_dir: DB ディレクトリのパス。None の場合は環境変数から取得。

        Returns:
            ``async_sessionmaker[AsyncSession]``（AdminService の DI に渡す）。

        Raises:
            SystemExit: DATA_DIR が未設定 / DB ファイル不在 / engine 初期化失敗時。
        """
        resolved_dir = LiteBootstrap._resolve_data_dir(data_dir)
        db_path = resolved_dir / _DB_FILENAME
        engine = LiteBootstrap._create_engine(db_path)
        return async_sessionmaker(engine, expire_on_commit=False)

    @staticmethod
    def _resolve_data_dir(data_dir: Path | None) -> Path:
        """DATA_DIR を解決する。未設定 / 不在の場合は MSG-AC-CLI-001 で Fail Fast。"""
        if data_dir is not None:
            return data_dir

        raw = os.environ.get(_ENV_DATA_DIR, "")
        if not raw:
            db_path = "unknown"
            _fail_msg(db_path, reason=f"{_ENV_DATA_DIR} 環境変数が設定されていません。")
        return Path(raw)

    @staticmethod
    def _create_engine(db_path: Path) -> AsyncEngine:
        """SQLite asyncio engine を WAL モードで生成する。

        DB ファイルが存在しない場合は MSG-AC-CLI-001 で Fail Fast（CLI は DB を新規作成しない）。
        """
        if not db_path.exists():
            _fail_msg(str(db_path))

        db_url = f"sqlite+aiosqlite:///{db_path}"
        try:
            engine = create_async_engine(
                db_url,
                connect_args={"check_same_thread": False},
            )
        except Exception as exc:
            _fail_msg(str(db_path), reason=str(exc))
        return engine


def _fail_msg(db_path: str, reason: str | None = None) -> NoReturn:
    """MSG-AC-CLI-001 を stderr に出力して exit 1 する。"""
    msg = _MSG_AC_CLI_001_TMPL.format(db_path=db_path)
    if reason:
        msg = f"{msg}\n詳細: {reason}"
    print(msg, file=sys.stderr)
    raise SystemExit(1)


__all__ = ["LiteBootstrap"]
