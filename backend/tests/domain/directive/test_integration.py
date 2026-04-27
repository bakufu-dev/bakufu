"""Round-trip scenarios across Directive + DirectiveInvariantViolation
(TC-IT-DR-001 / 002).

The directive feature is domain-only with zero external I/O, so
"integration" here means *aggregate-internal module integration*:
chained behaviors over a Directive lifecycle, with the original
Directive observed unchanged at each step (frozen + pre-validate
rebuild, Confirmation A).

These tests intentionally compose the production constructors /
behaviors directly — no mocks, no test-only back doors — and exercise
the documented acceptance criteria 1, 5, 6 in a single sequence.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestDirectiveLifecycleRoundTrip:
    """TC-IT-DR-001: full Directive lifecycle (construct → link → re-link rejected)."""

    def test_full_lifecycle_preserves_immutability(self) -> None:
        """TC-IT-DR-001: construct → link_task → second link_task rejected."""
        # Step 1: construct an unlinked Directive.
        d0 = make_directive()
        assert d0.task_id is None

        # Step 2: link a Task. New instance has the new task_id.
        task_id_1 = uuid4()
        d1 = d0.link_task(task_id_1)
        assert d1.task_id == task_id_1

        # Step 3: re-linking d1 must Fail Fast.
        task_id_2 = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            d1.link_task(task_id_2)
        assert excinfo.value.kind == "task_already_linked"

        # Step 4: original Directives are unchanged across the
        # sequence (frozen + pre-validate rebuild contract).
        assert d0.task_id is None
        assert d1.task_id == task_id_1

        # Step 5: structural equality — d0 and d1 must NOT compare
        # equal because their task_id values differ.
        assert d0 != d1


class TestRelinkFailureContinuity:
    """TC-IT-DR-002: re-link failure isolates state across repeated attempts."""

    def test_repeated_relink_attempts_do_not_corrupt_state(self) -> None:
        """TC-IT-DR-002: 3 consecutive failed re-links leave task_id unchanged."""
        existing_task_id = uuid4()
        d = make_linked_directive(task_id=existing_task_id)

        # Three different attempted_task_ids — each must fail.
        for _ in range(3):
            new_task_id = uuid4()
            with pytest.raises(DirectiveInvariantViolation) as excinfo:
                d.link_task(new_task_id)
            assert excinfo.value.kind == "task_already_linked"

        # The Directive's existing task_id survives intact — the
        # re-link contract is permanent (Confirmation D).
        assert d.task_id == existing_task_id

    def test_relink_failure_does_not_block_unrelated_directives(self) -> None:
        """TC-IT-DR-002 supplemental: failure isolation across instances."""
        # Link Directive A; re-link must fail.
        a = make_linked_directive(task_id=uuid4())
        with pytest.raises(DirectiveInvariantViolation):
            a.link_task(uuid4())

        # Independent Directive B can still be linked normally.
        b = make_directive()
        new_task_id = uuid4()
        b_linked = b.link_task(new_task_id)
        assert b_linked.task_id == new_task_id
