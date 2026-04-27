"""ExternalReviewGate Aggregate Root package.

Implements ``REQ-GT-001``〜``REQ-GT-007`` per
``docs/features/external-review-gate``. M1 7 兄弟目 — the **last**
M1 aggregate, completing the domain skeleton (after empire /
workflow / agent / room / directive / task). The package is split
along the responsibility lines that the design calls out:

* :mod:`bakufu.domain.external_review_gate.state_machine` —
  decision-table state machine (``Final[Mapping]`` +
  :class:`types.MappingProxyType`, §確定 B). 7 entries matching
  §確定 A's 4 x 4 dispatch table 1:1.
* :mod:`bakufu.domain.external_review_gate.aggregate_validators` —
  four module-level ``_validate_*`` helpers for the structural
  invariants (§確定 J kinds 2〜5; ``decision_already_decided`` is
  enforced by the state-machine lookup itself).
* :mod:`bakufu.domain.external_review_gate.gate` —
  :class:`ExternalReviewGate` Aggregate Root exposing four behavior
  methods whose names map 1:1 to the state-machine action names
  (§確定 A — task #42 §確定 A-2 パターン継承).

This ``__init__`` re-exports the public surface plus the
underscore-prefixed validators tests need to invoke directly (the
same pattern Norman approved for the agent / room / directive /
task packages).
"""

from __future__ import annotations

from bakufu.domain.external_review_gate.aggregate_validators import (
    MAX_FEEDBACK_LENGTH,
    MIN_FEEDBACK_LENGTH,
    _validate_audit_trail_append_only,
    _validate_decided_at_consistency,
    _validate_feedback_text_range,
    _validate_snapshot_immutable,
)
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.external_review_gate.state_machine import (
    TRANSITIONS,
    GateAction,
    allowed_actions_from,
    lookup,
)

__all__ = [
    "MAX_FEEDBACK_LENGTH",
    "MIN_FEEDBACK_LENGTH",
    "TRANSITIONS",
    "ExternalReviewGate",
    "GateAction",
    "_validate_audit_trail_append_only",
    "_validate_decided_at_consistency",
    "_validate_feedback_text_range",
    "_validate_snapshot_immutable",
    "allowed_actions_from",
    "lookup",
]
