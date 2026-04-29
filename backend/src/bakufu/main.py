"""bakufu Backend entry point.

The CLI launches :func:`main` which wires the production
:class:`Bootstrap` (with the Alembic migration runner attached) and
runs the eight-stage cold start. Stage 8 (FastAPI bind) is supplied
via the ``listener_starter`` coroutine that runs uvicorn in-process
(REQ-HAF-007, 確定 G).

Execution: ``uv run python -m bakufu.main``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from bakufu.infrastructure.bootstrap import Bootstrap
from bakufu.infrastructure.exceptions import BakufuConfigError
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head


async def _uvicorn_starter() -> None:
    """Stage-8 listener_starter: run uvicorn serving the FastAPI app (確定 G)。"""
    import uvicorn

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
        # Stage failure already logged a FATAL line; emit the canonical
        # MSG-PF-NNN message to stderr for parity with operator runbooks.
        sys.stderr.write(f"{exc.message}\n")
        return 1
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
