"""Directive Aggregate Root package.

Implements ``REQ-DR-001``〜``REQ-DR-003`` per ``docs/features/directive``.
M1 5 兄弟目 (after empire / workflow / agent / room) — slim by design:
five attributes, two structural invariants, one behavior. Split into
two sibling modules for the sake of consistency with the older M1
packages even though everything fits comfortably in one file:

* :mod:`bakufu.domain.directive.aggregate_validators` — two
  module-level invariant helpers (``_validate_text_range`` /
  ``_validate_task_link_immutable``).
* :mod:`bakufu.domain.directive.directive` — :class:`Directive`
  Aggregate Root.

This ``__init__`` re-exports the public surface plus the
underscore-prefixed helpers tests need to invoke directly (the same
pattern Norman approved for the agent / room packages).
"""

from __future__ import annotations

from bakufu.domain.directive.aggregate_validators import (
    MAX_TEXT_LENGTH,
    MIN_TEXT_LENGTH,
    _validate_task_link_immutable,
    _validate_text_range,
)
from bakufu.domain.directive.directive import Directive

__all__ = [
    "MAX_TEXT_LENGTH",
    "MIN_TEXT_LENGTH",
    "Directive",
    "_validate_task_link_immutable",
    "_validate_text_range",
]
