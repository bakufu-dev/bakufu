"""Workflow Aggregate Root package.

Implements ``REQ-WF-001``〜``REQ-WF-007`` per ``docs/features/workflow``.
Split into three sibling modules along the design's responsibility lines so
each file stays under the 500-line readability budget and the file-level
boundary mirrors Confirmation F's twin-defense:

* :mod:`bakufu.domain.workflow.entities` — :class:`Stage` / :class:`Transition`
  Pydantic models with **self**-invariants only.
* :mod:`bakufu.domain.workflow.dag_validators` — 10 module-level pure helper
  functions enforcing **collection** invariants (DAG, uniqueness, capacity).
* :mod:`bakufu.domain.workflow.workflow` — :class:`Workflow` Aggregate Root
  that dispatches over the helpers in deterministic order.

This ``__init__`` re-exports the public surface plus the ``_validate_*``
helpers that tests need to invoke directly (TC-UT-WF-060). The leading
underscore is preserved to keep the "private to the aggregate" intent clear
even though they are technically importable.
"""

from __future__ import annotations

from bakufu.domain.workflow.dag_validators import (
    MAX_NAME_LENGTH,
    MAX_STAGES,
    MAX_TRANSITIONS,
    MIN_NAME_LENGTH,
    _validate_capacity,
    _validate_dag_reachability,
    _validate_dag_sink_exists,
    _validate_entry_in_stages,
    _validate_external_review_notify,
    _validate_required_role_non_empty,
    _validate_stage_id_unique,
    _validate_transition_determinism,
    _validate_transition_id_unique,
    _validate_transition_refs,
)
from bakufu.domain.workflow.entities import Stage, Transition
from bakufu.domain.workflow.workflow import Workflow

__all__ = [
    "MAX_NAME_LENGTH",
    "MAX_STAGES",
    "MAX_TRANSITIONS",
    "MIN_NAME_LENGTH",
    "Stage",
    "Transition",
    "Workflow",
    "_validate_capacity",
    "_validate_dag_reachability",
    "_validate_dag_sink_exists",
    "_validate_entry_in_stages",
    "_validate_external_review_notify",
    "_validate_required_role_non_empty",
    "_validate_stage_id_unique",
    "_validate_transition_determinism",
    "_validate_transition_id_unique",
    "_validate_transition_refs",
]
