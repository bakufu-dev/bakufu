"""GateRole validated type alias for InternalReviewGate.

A GateRole is a free-form slug label identifying which logical reviewer
category an agent belongs to (e.g. ``"security"``, ``"lead-dev"``,
``"qa-1"``). It is **not** the same as :class:`Role` (which is a fixed enum
of agent capabilities) — GateRoles are defined per-Gate as part of the
Workflow Stage configuration.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

# ---------------------------------------------------------------------------
# GateRole validated type alias
# ---------------------------------------------------------------------------
_GATE_ROLE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_GATE_ROLE_MAX_LEN: int = 40


def _validate_gate_role(value: str) -> str:
    """Enforce the slug pattern for :data:`GateRole`.

    Rules (all checked after NFC normalization):

    * 1〜40 characters (code-point count).
    * Lowercase ASCII letters, digits, and hyphens only.
    * Must start with a lowercase letter (digit-initial slugs are
      rejected to avoid confusion with numeric IDs).
    * No consecutive hyphens (``--`` fragments look like long-options
      and confuse downstream tools).
    * No leading or trailing hyphens (covered by the regex anchor).
    """
    length = len(value)
    if not (1 <= length <= _GATE_ROLE_MAX_LEN):
        raise ValueError(
            f"GateRole must be 1-{_GATE_ROLE_MAX_LEN} characters (got length={length})"
        )
    if not _GATE_ROLE_RE.fullmatch(value):
        raise ValueError(
            f"GateRole must match the slug pattern "
            f"(lowercase letters/digits/hyphens, letter-initial, no consecutive hyphens); "
            f"got {value!r}"
        )
    return value


type GateRole = Annotated[str, AfterValidator(_validate_gate_role)]
"""Validated slug identifier for a role in an :class:`InternalReviewGate`.

A GateRole is a free-form string label that identifies which logical
reviewer category an agent belongs to (e.g. ``"security"``,
``"lead-dev"``, ``"qa-1"``). It is **not** the same as :class:`Role`
(which is a fixed enum of agent capabilities) — GateRoles are
defined per-Gate as part of the Workflow Stage configuration and may
be arbitrary slugs chosen by the workflow author.

Validation rules (enforced by :func:`_validate_gate_role`):

* 1〜40 NFC-normalized characters.
* Lowercase ASCII letters, digits, and hyphens only.
* Must start with a lowercase letter.
* No consecutive hyphens (``--``).
* No trailing hyphen (covered by the regex anchor).
"""


__all__ = [
    "GateRole",
]
