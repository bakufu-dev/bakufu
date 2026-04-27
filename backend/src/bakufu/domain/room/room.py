"""Room Aggregate Root (REQ-RM-001〜006).

Implements per ``docs/features/room``. The aggregate dispatches over four
helpers in :mod:`bakufu.domain.room.aggregate_validators` and composes
:class:`AgentMembership` + :class:`PromptKit` VOs from
:mod:`bakufu.domain.room.value_objects`.

Design contracts:

* **Pre-validate rebuild (Confirmation A)** — ``add_member`` /
  ``remove_member`` / ``update_prompt_kit`` / ``archive`` all go through
  :meth:`Room._rebuild_with` (``model_dump → swap → model_validate``).
* **NFC pipeline (Confirmation B)** — ``Room.name`` and ``Room.description``
  reuse the empire / workflow / agent ``nfc_strip`` helper. Length judgement
  happens in the aggregate validators so the resulting
  :class:`RoomInvariantViolation` carries ``kind='name_range'`` /
  ``'description_too_long'`` with MSG-RM-001 / 002 wording.
* **archive idempotency (Confirmation D)** — ``archive()`` always returns a
  *new* instance. Idempotency means "result state matches", not "object
  identity". Pydantic v2 frozen + ``model_validate`` rebuild guarantees
  this; the docstring documents the contract so callers do not rely on
  ``is`` comparisons.
* **archived terminal (Confirmation E)** — ``add_member`` / ``remove_member``
  / ``update_prompt_kit`` Fail Fast on archived Rooms with
  ``kind='room_archived'`` (MSG-RM-006). ``archive()`` itself is idempotent
  and bypasses this check.
* **`(agent_id, role)` pair uniqueness (Confirmation F)** — same agent can
  hold multiple roles; the validator uses the pair as the key.
* **Application-layer responsibilities** — Workflow existence, Agent
  existence, leader-required-by-Workflow, and Empire-scoped name uniqueness
  live in ``RoomService`` / ``EmpireService``. The aggregate trusts only
  what it can observe locally.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room.aggregate_validators import (
    _validate_description_length,
    _validate_member_capacity,
    _validate_member_unique,
    _validate_name_range,
)
from bakufu.domain.room.value_objects import AgentMembership, PromptKit
from bakufu.domain.value_objects import (
    AgentId,
    Role,
    RoomId,
    WorkflowId,
    nfc_strip,
)


class Room(BaseModel):
    """Editable composition space within an :class:`Empire` (REQ-RM-001).

    Composes a :class:`PromptKit` preamble and ``list[AgentMembership]`` over
    a fixed :class:`WorkflowId`. The aggregate enforces structural invariants
    only — Workflow existence and leader-required-by-Workflow checks belong
    to the application layer because they require external knowledge.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: RoomId
    name: str
    description: str = ""
    workflow_id: WorkflowId
    members: list[AgentMembership] = []
    prompt_kit: PromptKit = PromptKit()
    archived: bool = False

    # ---- pre-validation -------------------------------------------------
    @field_validator("name", "description", mode="before")
    @classmethod
    def _normalize_short_text(cls, value: object) -> object:
        # NFC + strip pipeline shared with empire / workflow / agent (Confirmation B).
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Dispatch over the aggregate-level helpers in deterministic order.

        Order: name range → description length → member uniqueness → member
        capacity. Earlier failures hide later ones so error messages stay
        focused on the root cause.
        """
        _validate_name_range(self.name)
        _validate_description_length(self.description)
        _validate_member_unique(self.members)
        _validate_member_capacity(self.members)
        return self

    # ---- behaviors (Tell, Don't Ask) ------------------------------------
    def add_member(self, membership: AgentMembership) -> Room:
        """Append ``membership`` to ``members``; aggregate validation catches duplicates.

        Fail Fast on archived Rooms (Confirmation E). The
        ``(agent_id, role)`` pair-uniqueness check fires inside
        :meth:`_check_invariants` after the rebuild.

        Raises:
            RoomInvariantViolation: ``kind='room_archived'`` (MSG-RM-006) if
                the Room is already archived; ``kind='member_duplicate'``
                (MSG-RM-003) if the pair already exists; ``kind='capacity_exceeded'``
                (MSG-RM-004) if adding pushes the count over :data:`MAX_MEMBERS`.
        """
        self._reject_if_archived()
        return self._rebuild_with(members=[*self.members, membership])

    def remove_member(self, agent_id: AgentId, role: Role) -> Room:
        """Drop the membership matching ``(agent_id, role)``.

        Fail Fast on archived Rooms (Confirmation E) and on missing pair
        (MSG-RM-005) — the caller cannot blindly retry a remove without
        observing the current member list.

        Raises:
            RoomInvariantViolation: ``kind='room_archived'`` (MSG-RM-006);
                ``kind='member_not_found'`` (MSG-RM-005) when no membership
                matches the pair.
        """
        self._reject_if_archived()
        if not any(m.agent_id == agent_id and m.role == role for m in self.members):
            raise RoomInvariantViolation(
                kind="member_not_found",
                message=(
                    f"[FAIL] Member not found: agent_id={agent_id}, role={role.value}\n"
                    f"Next: Verify the (agent_id, role) pair via "
                    f"GET /rooms/{{room_id}}/members; the agent may have been "
                    f"already removed or never had this role."
                ),
                detail={"agent_id": str(agent_id), "role": role.value},
            )
        return self._rebuild_with(
            members=[m for m in self.members if not (m.agent_id == agent_id and m.role == role)],
        )

    def update_prompt_kit(self, prompt_kit: PromptKit) -> Room:
        """Replace ``prompt_kit`` with ``prompt_kit``.

        Fail Fast on archived Rooms (Confirmation E). PromptKit length
        violations surface as :class:`pydantic.ValidationError` at VO
        construction time (Confirmation I two-stage catch), so by the time
        this method is invoked the VO is already valid.

        Raises:
            RoomInvariantViolation: ``kind='room_archived'`` (MSG-RM-006).
        """
        self._reject_if_archived()
        return self._rebuild_with(prompt_kit=prompt_kit)

    def archive(self) -> Room:
        """Return a new :class:`Room` with ``archived=True`` (Confirmation D).

        Idempotent: calling on an already-archived Room yields a fresh Room
        that is **structurally equal** to the input but has a different
        ``id()``. Callers must not rely on object identity — always reassign
        the returned value (``room = room.archive()``). Same contract Norman
        approved for the agent / empire ``archive()`` behaviors.
        """
        return self._rebuild_with_state({"archived": True})

    # ---- internal -------------------------------------------------------
    def _reject_if_archived(self) -> None:
        """Raise ``room_archived`` (MSG-RM-006) when the Room is terminal.

        Confirmation E: archived Rooms reject all mutating behaviors except
        :meth:`archive` itself, which stays idempotent for retry tolerance.
        """
        if self.archived:
            raise RoomInvariantViolation(
                kind="room_archived",
                message=(
                    f"[FAIL] Cannot modify archived Room: room_id={self.id}\n"
                    f"Next: Create a new Room; unarchive is not supported in "
                    f"MVP (Phase 2 will add RoomService.unarchive)."
                ),
                detail={"room_id": str(self.id)},
            )

    def _rebuild_with(
        self,
        *,
        members: list[AgentMembership] | None = None,
        prompt_kit: PromptKit | None = None,
    ) -> Room:
        """Re-construct via ``model_validate`` so ``_check_invariants`` re-fires."""
        state = self.model_dump()
        if members is not None:
            state["members"] = [m.model_dump() for m in members]
        if prompt_kit is not None:
            state["prompt_kit"] = prompt_kit.model_dump()
        return Room.model_validate(state)

    def _rebuild_with_state(self, updates: dict[str, Any]) -> Room:
        """Pre-validate rebuild for scalar attribute updates (e.g. ``archived``)."""
        state = self.model_dump()
        state.update(updates)
        return Room.model_validate(state)


__all__ = [
    "Room",
]
