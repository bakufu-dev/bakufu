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
        reload 時は ``asyncio.create_subprocess_exec`` で uvicorn を子プロセスとして起動する。

        ``uvicorn.run()`` は ``ChangeReload.run()`` 内で ``signal.signal()`` を呼ぶが、
        Python の ``signal.signal()`` はメインスレッドのメインインタープリタでしか動作しない。
        ``run_in_executor`` のスレッドプール上で呼ぶと
        ``ValueError: signal only works in main thread of the main interpreter`` でクラッシュする
        （BUG-006）。

        子プロセスとして起動することで、子プロセス自身のメインスレッドで
        ``signal.signal()`` が正常動作し、``ChangeReload`` によるファイル監視・
        ホットリロードが実現する。

        通常時（reload=False）は ``uvicorn.Server.serve()`` を維持する
        （同一イベントループ上で動作し、型安全性・テスト容易性を保つ）。
    """
    dev_reload = os.environ.get("BAKUFU_DEV_RELOAD", "").lower() in {"true", "1", "yes"}
    reload_dir = os.environ.get("BAKUFU_RELOAD_DIR", "/app/backend/src")
    host = os.environ.get("BAKUFU_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("BAKUFU_BIND_PORT", "8000"))

    if dev_reload:
        # reload 時: 子プロセスとして uvicorn を起動する（BUG-006 対応）。
        # signal.signal() はメインスレッド必須のため run_in_executor は使えない。
        # 子プロセスは自身のメインスレッドを持つため ChangeReload が正常動作する。
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            _APP_IMPORT_STRING,
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "info",
            "--reload",
            "--reload-dir",
            reload_dir,
        )
        await proc.wait()
    else:
        # 通常時: uvicorn.Server.serve() で同一イベントループ上で動作（型安全・テスト容易）
        import uvicorn

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
