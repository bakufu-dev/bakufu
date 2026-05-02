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
        reload=True 時は ``app`` オブジェクトではなく import string を渡す。
        uvicorn の reload manager は子プロセスが app を再 import する際に
        import string（``"module:attr"``）が必須であり、オブジェクト渡しでは
        ``WARNING: Current configuration will not reload`` と出力して reload を
        黙殺する（uvicorn 0.46.0 以降の挙動）。
        通常時（reload=False）は app オブジェクトを直接渡すことで型安全性を維持する。
    """
    import uvicorn

    dev_reload = os.environ.get("BAKUFU_DEV_RELOAD", "").lower() in {"true", "1", "yes"}
    reload_dir = os.environ.get("BAKUFU_RELOAD_DIR", "/app/backend/src")

    if dev_reload:
        # reload 時: import string 必須（オブジェクト渡しでは reload が黙殺される）
        config = uvicorn.Config(
            _APP_IMPORT_STRING,
            host=os.environ.get("BAKUFU_BIND_HOST", "127.0.0.1"),
            port=int(os.environ.get("BAKUFU_BIND_PORT", "8000")),
            loop="asyncio",
            log_level="info",
            reload=True,
            reload_dirs=[reload_dir],
        )
    else:
        # 通常時: app オブジェクトを直接渡す（型安全、テスト容易性を維持）
        from bakufu.interfaces.http.app import app

        config = uvicorn.Config(
            app,
            host=os.environ.get("BAKUFU_BIND_HOST", "127.0.0.1"),
            port=int(os.environ.get("BAKUFU_BIND_PORT", "8000")),
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
