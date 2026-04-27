"""pid_registry GC unit tests (TC-UT-PF-010 / 026 / 027 / 028).

Schneier 申し送り #5 の物理保証. ``psutil.Process`` is mocked because we
cannot spawn / SIGKILL real processes in CI. Every mock is built via
``tests.factories.psutil_process`` so the surface stays consistent and
the ``_meta.synthetic`` tag is in place.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import psutil
import pytest
from bakufu.infrastructure.persistence.sqlite.pid_gc import (
    _classify_row,  # pyright: ignore[reportPrivateUsage]
    _kill_descendants,  # pyright: ignore[reportPrivateUsage]
)

from tests.factories.psutil_process import (
    make_access_denied_process,
    make_child_process,
    make_orphan_process,
    make_protected_process,
)


class TestClassifyRow:
    """TC-UT-PF-010: classifier returns the correct verdict per psutil shape."""

    def test_no_such_process_returns_absent(self) -> None:
        """TC-UT-PF-010 (absent): NoSuchProcess at psutil.Process() → 'absent'."""
        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(123)):
            verdict = _classify_row(pid=123, recorded_started_at=datetime.now(UTC))
        assert verdict == "absent"

    def test_create_time_match_returns_orphan_kill(self) -> None:
        """TC-UT-PF-010 (orphan_kill): create_time matches → kill verdict."""
        recorded = datetime.now(UTC)
        proc = make_orphan_process(pid=456, create_time_seconds=recorded.timestamp())
        with patch("psutil.Process", return_value=proc):
            verdict = _classify_row(pid=456, recorded_started_at=recorded)
        assert verdict == "orphan_kill"

    def test_create_time_mismatch_returns_protected(self) -> None:
        """TC-UT-PF-010 (protected): mismatching create_time → 'protected'."""
        recorded = datetime.now(UTC)
        proc = make_protected_process(pid=789, recorded_started_at=recorded)
        with patch("psutil.Process", return_value=proc):
            verdict = _classify_row(pid=789, recorded_started_at=recorded)
        assert verdict == "protected"


class TestProtectedNeverKilled:
    """TC-UT-PF-026: protected verdict skips _kill_descendants."""

    def test_protected_pid_send_signal_not_called(self) -> None:
        """TC-UT-PF-026: PID-reused processes are never signaled."""
        recorded = datetime.now(UTC)
        proc = make_protected_process(pid=555, recorded_started_at=recorded)
        with patch("psutil.Process", return_value=proc):
            verdict = _classify_row(pid=555, recorded_started_at=recorded)
        assert verdict == "protected"
        # _classify_row never calls send_signal — it only inspects.
        assert proc.send_signal.call_count == 0


class TestAccessDeniedRetry:
    """TC-UT-PF-027: AccessDenied bubbles up so the row is left for next sweep."""

    def test_access_denied_propagates(self) -> None:
        """TC-UT-PF-027: psutil.AccessDenied → caller WARN-logs + skip."""
        proc = make_access_denied_process(pid=777)
        with patch("psutil.Process", return_value=proc), pytest.raises(psutil.AccessDenied):
            _classify_row(pid=777, recorded_started_at=datetime.now(UTC))


class TestKillDescendantsOrder:
    """TC-UT-PF-028: SIGTERM → grace → SIGKILL with recursive=True."""

    def test_recursive_children_signal_dispatch(self) -> None:
        """TC-UT-PF-028: send_signal called on parent + every child returned."""
        child1 = make_child_process(pid=2001)
        child2 = make_child_process(pid=2002)
        parent = make_orphan_process(pid=999, children=[child1, child2])
        with patch("psutil.Process", return_value=parent):
            _kill_descendants(pid=999)
        # Each target receives at least one SIGTERM (is_running=False so
        # the grace loop terminates without escalating to SIGKILL).
        assert parent.send_signal.call_count >= 1
        assert child1.send_signal.call_count >= 1
        assert child2.send_signal.call_count >= 1

    def test_recursive_keyword_passed_to_children(self) -> None:
        """TC-UT-PF-028 補強: ``children(recursive=True)`` is honored."""
        parent = make_orphan_process(pid=1000)
        with patch("psutil.Process", return_value=parent):
            _kill_descendants(pid=1000)
        parent.children.assert_called_with(recursive=True)
