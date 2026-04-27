"""bakufu Backend entry point.

The CLI launches :func:`main` which wires the production
:class:`Bootstrap` (with the Alembic migration runner attached) and
runs the eight-stage cold start. Stage 8 (FastAPI bind) is supplied
by a future ``feature/http-api`` PR; until then the entry point exits
cleanly after the dispatcher / scheduler are running.

Execution: ``uv run python -m bakufu.main``.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from bakufu.infrastructure.bootstrap import Bootstrap
from bakufu.infrastructure.exceptions import BakufuConfigError
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head


async def _run() -> int:
    bootstrap = Bootstrap(
        listener_starter=None,  # ``feature/http-api`` will inject the FastAPI bind.
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
