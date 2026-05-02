"""bakufu Backend のエントリポイント。

CLI は :func:`main` を起動し、本番用の :class:`Bootstrap`
（Alembic マイグレーションランナーを接続済み）を構築して 8 段階のコールドスタート
を実行する。Stage 8（FastAPI バインド）は ``listener_starter`` コルーチンで供給され、
プロセス内で uvicorn を実行する（REQ-HAF-007、確定 G）。

実行方法: ``uv run python -m bakufu.main``。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from bakufu.infrastructure.bootstrap import Bootstrap
from bakufu.infrastructure.exceptions import BakufuConfigError
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head

_APP_IMPORT_STRING = "bakufu.interfaces.http.app:app"


async def _uvicorn_starter() -> None:
    """Stage-8 listener_starter: run uvicorn serving the FastAPI app (確定 G)。

    ``BAKUFU_DEV_RELOAD=true`` を設定すると uvicorn が
    ``BAKUFU_RELOAD_DIR``（デフォルト: ``/app/backend/src``）を監視してホットリロードする。
    docker-compose.override.yml で ``BAKUFU_DEV_RELOAD=true`` + ソース bind mount と
    組み合わせることで開発時のホットリロードを実現する（tech-stack.md §開発専用オーバーライド）。

    .. note::
        reload 時は ``uvicorn.run()`` を使う。
        ``uvicorn.Server(config).serve()`` は ``config.should_reload`` を評価せず
        ``ChangeReload`` サブプロセスを起動しないため、``reload=True`` を渡しても
        ファイル監視が一切行われない（BUG-005）。
        ``uvicorn.run()`` のみが ``ChangeReload.run()`` を呼び出してホットリロードを実現する。

        ``uvicorn.run()`` は同期ブロッキング呼び出しのため、
        ``asyncio.get_running_loop().run_in_executor`` でスレッド上で実行する。

        通常時（reload=False）は ``uvicorn.Server.serve()`` を維持する
        （同一イベントループ上で動作し、型安全性・テスト容易性を保つ）。
    """
    import uvicorn

    dev_reload = os.environ.get("BAKUFU_DEV_RELOAD", "").lower() in {"true", "1", "yes"}
    reload_dir = os.environ.get("BAKUFU_RELOAD_DIR", "/app/backend/src")
    host = os.environ.get("BAKUFU_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("BAKUFU_BIND_PORT", "8000"))

    if dev_reload:
        # reload 時: uvicorn.run() 経由でのみ ChangeReload が起動する（BUG-005 対応）。
        # uvicorn.run() は同期ブロッキングのため run_in_executor でスレッド上で実行する。
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: uvicorn.run(
                _APP_IMPORT_STRING,
                host=host,
                port=port,
                log_level="info",
                reload=True,
                reload_dirs=[reload_dir],
            ),
        )
    else:
        # 通常時: uvicorn.Server.serve() で同一イベントループ上で動作（型安全・テスト容易）
        from bakufu.interfaces.http.app import app

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            loop="asyncio",
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()


async def _run() -> int:
    bootstrap = Bootstrap(
        listener_starter=_uvicorn_starter,
        migration_runner=run_upgrade_head,
    )
    try:
        await bootstrap.run()
    except BakufuConfigError as exc:
        # Stage 失敗時には既に FATAL ログが出力済みのため、運用ランブックとの整合のため
        # 確定文言の MSG-PF-NNN メッセージを stderr に出力する。
        sys.stderr.write(f"{exc.message}\n")
        return 1
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
