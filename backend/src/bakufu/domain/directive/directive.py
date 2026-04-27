"""Directive Aggregate Root (REQ-DR-001〜003).

Implements per ``docs/features/directive``. The aggregate is
intentionally slim: five attributes, two structural invariants, one
behavior. Application-layer concerns (``$``-prefix normalization,
``target_room_id`` existence, Task creation) live in
``DirectiveService.issue()`` per §確定 G / H.

Design contracts:

* **Pre-validate rebuild (Confirmation A)** — :meth:`Directive.link_task`
  goes through :meth:`_rebuild_with_state`
  (``model_dump → swap → model_validate``).
* **NFC-only normalization (Confirmation B)** — ``Directive.text``
  applies ``unicodedata.normalize('NFC', ...)`` *without* ``strip``.
  CEO directives may include meaningful leading / trailing whitespace
  and multi-paragraph blocks; the agent ``Persona.prompt_body`` /
  room ``PromptKit.prefix_markdown`` precedent applies here too.
* **task_id transition uniqueness (Confirmation C / D)** — only the
  ``link_task`` path watches for transition violations. The
  constructor path accepts any ``TaskId | None`` value to support
  Repository hydration of an already-linked Directive without a
  separate "rebuild" code path.
* **No idempotency (Confirmation D)** — a second ``link_task`` is
  *always* a Fail Fast, even when the new TaskId equals the existing
  one. Re-issuing a directive means creating a new Directive.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.directive.aggregate_validators import (
    _validate_text_range,
)
from bakufu.domain.value_objects import (
    DirectiveId,
    RoomId,
    TaskId,
)


class Directive(BaseModel):
    """CEO directive issued against a target :class:`Room` (REQ-DR-001).

    The aggregate captures the *intent* of an instruction: the text
    body, the room it is delegated to, the time it was issued, and
    the optional generated Task it was linked to. ``DirectiveService``
    (application layer) is responsible for creating the Task and
    calling :meth:`link_task` to establish the back-reference.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: DirectiveId
    text: str
    target_room_id: RoomId
    # ``created_at`` arrives as a tz-aware ``datetime`` from the
    # application layer (see Directive detailed-design §設計判断の補足
    # "なぜ created_at を引数で受け取るか"). The post-validator below
    # rejects naive datetimes so the contract is enforced at the
    # aggregate boundary rather than by every caller.
    created_at: datetime
    task_id: TaskId | None = None

    # ---- pre-validation -------------------------------------------------
    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        # Confirmation B: NFC only — no ``strip``. CEO directives may
        # rely on leading / trailing whitespace + newlines.
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("created_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        # Naive datetimes carry no timezone info and would silently
        # round-trip through SQLite as wall-clock strings, breaking
        # ordering. Fail Fast at the aggregate boundary instead.
        if value.tzinfo is None:
            raise ValueError(
                "Directive.created_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Run the structural invariant checks.

        Confirmation C: only ``_validate_text_range`` runs at
        construction time. ``_validate_task_link_immutable`` watches
        the *transition* enforced inside :meth:`link_task` itself,
        not the snapshot value, because the constructor path is also
        used to hydrate Directives from a Repository where the
        ``task_id`` may already be a real value.
        """
        _validate_text_range(self.text)
        return self

    # ---- behaviors (Tell, Don't Ask) ------------------------------------
    def link_task(self, task_id: TaskId) -> Directive:
        """Bind this Directive to ``task_id``; reject re-linking.

        Returns a new :class:`Directive` instance with ``task_id``
        populated. A subsequent call against the new instance always
        Fails Fast — there is no idempotent "same TaskId" path
        (Confirmation D).

        Raises:
            DirectiveInvariantViolation: ``kind='task_already_linked'``
                (MSG-DR-002) when this Directive already has a
                non-``None`` ``task_id``.
        """
        # Local import keeps the module-level import graph minimal —
        # the validator only matters on the failing path.
        from bakufu.domain.directive.aggregate_validators import (
            _validate_task_link_immutable,
        )

        _validate_task_link_immutable(
            directive_id=self.id,
            existing_task_id=self.task_id,
            attempted_task_id=task_id,
        )
        return self._rebuild_with_state({"task_id": task_id})

    # ---- internal -------------------------------------------------------
    def _rebuild_with_state(self, updates: dict[str, Any]) -> Directive:
        """Pre-validate rebuild for scalar attribute updates.

        Confirmation A — same pattern as
        :class:`bakufu.domain.agent.agent.Agent` and
        :class:`bakufu.domain.room.room.Room`.
        """
        state = self.model_dump()
        state.update(updates)
        return Directive.model_validate(state)


__all__ = [
    "Directive",
]
