"""Factories for psutil.Process behavior under pid_gc tests.

Per ``docs/features/persistence-foundation/test-design.md`` §外部 I/O
依存マップ. The pid_gc unit tests cannot spawn / SIGKILL real processes
(OS-dependent and unsafe in CI), so we build minimal mock objects whose
``create_time`` / ``children`` / ``is_running`` / ``send_signal`` shapes
match psutil's documented contract.

Each factory tags its output with ``_meta = {"synthetic": True}`` so a
reviewer or future linter can spot test-built objects against real
``psutil.Process`` instances.

The mock surface intentionally mirrors only the methods :mod:`pid_gc`
actually calls — adding more would let tests drift further from the
production code path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import psutil

if TYPE_CHECKING:
    from collections.abc import Sequence


def _tag_synthetic(mock_obj: MagicMock) -> MagicMock:
    """Stamp ``_meta.synthetic=True`` so reviewers can spot factory output."""
    mock_obj._meta = {"synthetic": True}  # intentional mock attribute
    return mock_obj


def make_orphan_process(
    *,
    pid: int = 1234,
    create_time_seconds: float | None = None,
    children: Sequence[MagicMock] | None = None,
) -> MagicMock:
    """Build a psutil.Process mock representing an orphan to kill.

    The ``create_time()`` value matches the recorded ``started_at`` —
    pid_gc's classifier returns ``'orphan_kill'`` for this shape.
    """
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    if create_time_seconds is None:
        create_time_seconds = datetime.now(UTC).timestamp() - 60.0
    proc.create_time.return_value = create_time_seconds
    proc.children.return_value = list(children) if children else []
    proc.send_signal = MagicMock()
    proc.is_running = MagicMock(return_value=False)
    return _tag_synthetic(proc)


def make_protected_process(
    *,
    pid: int = 5678,
    recorded_started_at: datetime | None = None,
) -> MagicMock:
    """Build a psutil.Process mock whose ``create_time`` mismatches.

    pid_gc must classify this as ``'protected'`` (PID was reused by an
    unrelated process) and refuse to send any signal.
    """
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    if recorded_started_at is None:
        recorded_started_at = datetime.now(UTC)
    # Live create_time is 1 hour later than what we recorded — clearly
    # a different process.
    proc.create_time.return_value = recorded_started_at.timestamp() + 3600.0
    proc.children.return_value = []
    proc.send_signal = MagicMock()
    proc.is_running = MagicMock(return_value=True)
    return _tag_synthetic(proc)


def make_no_such_process_factory(pid: int = 9999) -> type[psutil.NoSuchProcess]:
    """Return a ``psutil.NoSuchProcess`` constructor pre-bound to ``pid``."""
    return type("_BoundNoSuchProcess", (psutil.NoSuchProcess,), {"_meta_pid": pid})


def make_access_denied_process(*, pid: int = 7777) -> MagicMock:
    """Build a mock whose ``create_time`` raises ``psutil.AccessDenied``.

    pid_gc must WARN-log and leave the registry row for the next sweep —
    DELETE-ing under AccessDenied lets orphans accumulate forever.
    """
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    proc.create_time.side_effect = psutil.AccessDenied(pid)
    proc.children.return_value = []
    proc.send_signal = MagicMock()
    proc.is_running = MagicMock(return_value=True)
    return _tag_synthetic(proc)


def make_child_process(*, pid: int) -> MagicMock:
    """Build a child psutil.Process mock for descendants() output."""
    child = MagicMock(spec=psutil.Process)
    child.pid = pid
    child.send_signal = MagicMock()
    child.is_running = MagicMock(return_value=False)
    return _tag_synthetic(child)


__all__ = [
    "make_access_denied_process",
    "make_child_process",
    "make_no_such_process_factory",
    "make_orphan_process",
    "make_protected_process",
]
