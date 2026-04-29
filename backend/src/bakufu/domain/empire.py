"""Empire Aggregate Root.

Implements ``REQ-EM-001``〜``REQ-EM-005`` per ``docs/features/empire``.

Design contract (do not break without re-running design review):

* **Pre-validate rebuild (Confirmation A)** — every state-changing behavior
  serializes the current state via ``model_dump()``, swaps the target list,
  and re-runs ``Empire.model_validate(...)`` so the ``model_validator(mode='after')``
  fires on the *candidate* aggregate. Failure raises
  :class:`EmpireInvariantViolation` *before* any new instance is observable,
  keeping the original aggregate strictly unchanged. ``model_copy(update=...)``
  is intentionally avoided because Pydantic v2 defaults it to ``validate=False``.
* **NFC normalization pipeline (Confirmation B)** — ``raw → NFC → strip → len``;
  the resulting cleaned form is what gets persisted and what ``MSG-EM-001``'s
  ``{length}`` reports.
* **Capacity (Confirmation C)** — ``len(rooms) ≤ 100`` and ``len(agents) ≤ 100``.
* **Linear search (Confirmation D)** — ``archive_room`` walks ``rooms`` linearly
  rather than maintaining a side-index dict. ``N ≤ 100`` keeps this trivially
  cheap and avoids parallel-state bugs.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.exceptions import EmpireInvariantViolation
from bakufu.domain.value_objects import (
    AgentRef,
    EmpireId,
    RoomId,
    RoomRef,
    nfc_strip,
)

# Capacity ceiling per detailed-design §Confirmation C. Module-level constant
# so test/factory code can import the same source of truth.
MAX_ROOMS: int = 100
MAX_AGENTS: int = 100

# Empire.name length bounds per detailed-design §Confirmation B.
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80


class Empire(BaseModel):
    """Root aggregate that owns the references to Rooms and Agents.

    State-changing methods (:meth:`hire_agent`, :meth:`establish_room`,
    :meth:`archive_room`) return a *new* :class:`Empire` instance — this
    aggregate is frozen.  The caller swaps its own reference; Pydantic v2's
    ``frozen=True`` makes in-place mutation impossible at the language level,
    so concurrent callers cannot observe a partially-updated aggregate.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: EmpireId
    name: str
    archived: bool = False
    # Pydantic v2 deep-copies these defaults per instance, so the empty-list
    # literal is safe and pyright-friendly (no `default_factory=list` Unknown).
    rooms: list[RoomRef] = []
    agents: list[AgentRef] = []

    # ------------------------------------------------------------------
    # Pre-validation hooks
    # ------------------------------------------------------------------
    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        """Apply the Confirmation B pipeline up to (but not including) ``len``.

        Delegates to :func:`nfc_strip` so Empire / Room / Agent / Workflow share
        the **single** NFC+strip implementation (DRY). Length / range judgment
        is intentionally kept in :meth:`_check_invariants` so the resulting
        :class:`EmpireInvariantViolation` carries the structured
        ``kind='name_range'`` rather than a generic Pydantic ``ValidationError``.
        """
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Run all aggregate-level invariants on the candidate instance.

        Custom (non-``ValueError``) exceptions raised here propagate to the
        caller without being wrapped in ``ValidationError`` — Pydantic v2's
        documented behavior for ``mode='after'`` validators.
        """
        self._check_name_range()
        self._check_capacity()
        self._check_no_duplicates()
        return self

    # ------------------------------------------------------------------
    # Invariant checks (split for SRP / readability)
    # ------------------------------------------------------------------
    def _check_name_range(self) -> None:
        length = len(self.name)
        if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
            raise EmpireInvariantViolation(
                kind="name_range",
                message=(
                    f"[FAIL] Empire name must be "
                    f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters "
                    f"(got {length})"
                ),
                detail={"length": length},
            )

    def _check_capacity(self) -> None:
        agents_count = len(self.agents)
        if agents_count > MAX_AGENTS:
            raise EmpireInvariantViolation(
                kind="capacity_exceeded",
                message=(
                    f"[FAIL] Empire invariant violation: "
                    f"agents capacity {MAX_AGENTS} exceeded (got {agents_count})"
                ),
                detail={"agents_count": agents_count, "max_agents": MAX_AGENTS},
            )
        rooms_count = len(self.rooms)
        if rooms_count > MAX_ROOMS:
            raise EmpireInvariantViolation(
                kind="capacity_exceeded",
                message=(
                    f"[FAIL] Empire invariant violation: "
                    f"rooms capacity {MAX_ROOMS} exceeded (got {rooms_count})"
                ),
                detail={"rooms_count": rooms_count, "max_rooms": MAX_ROOMS},
            )

    def _check_no_duplicates(self) -> None:
        seen_agents: set[Any] = set()
        for agent in self.agents:
            if agent.agent_id in seen_agents:
                raise EmpireInvariantViolation(
                    kind="agent_duplicate",
                    message=f"[FAIL] Agent already hired: agent_id={agent.agent_id}",
                    detail={"agent_id": str(agent.agent_id)},
                )
            seen_agents.add(agent.agent_id)

        seen_rooms: set[Any] = set()
        for room in self.rooms:
            if room.room_id in seen_rooms:
                raise EmpireInvariantViolation(
                    kind="room_duplicate",
                    message=f"[FAIL] Room already established: room_id={room.room_id}",
                    detail={"room_id": str(room.room_id)},
                )
            seen_rooms.add(room.room_id)

    # ------------------------------------------------------------------
    # Behaviors (Tell, Don't Ask)
    # ------------------------------------------------------------------
    def hire_agent(self, agent_ref: AgentRef) -> Empire:
        """Return a new :class:`Empire` with ``agent_ref`` appended to ``agents``.

        Raises:
            EmpireInvariantViolation: if ``agent_ref.agent_id`` duplicates an
                existing agent (``kind='agent_duplicate'``) or the resulting
                count exceeds :data:`MAX_AGENTS` (``kind='capacity_exceeded'``).
                The original aggregate is left unchanged.
        """
        return self._rebuild_with(agents=[*self.agents, agent_ref])

    def establish_room(self, room_ref: RoomRef) -> Empire:
        """Return a new :class:`Empire` with ``room_ref`` appended to ``rooms``.

        Raises:
            EmpireInvariantViolation: on duplicate ``room_id`` or capacity
                breach. Original aggregate unchanged.
        """
        return self._rebuild_with(rooms=[*self.rooms, room_ref])

    def archive_room(self, room_id: RoomId) -> Empire:
        """Return a new :class:`Empire` with the matching room marked archived.

        The room is *not* physically removed — bakufu's audit trail must be
        able to resolve historical ``room_id`` references (detailed-design
        §"なぜ archive_room は物理削除しないか"). Re-archiving an already
        archived room is idempotent: the resulting room state is the same.

        Raises:
            EmpireInvariantViolation: if no room matches (``kind='room_not_found'``).
        """
        for index, room in enumerate(self.rooms):
            if room.room_id == room_id:
                archived_ref = room.model_copy(update={"archived": True})
                new_rooms = [*self.rooms[:index], archived_ref, *self.rooms[index + 1 :]]
                return self._rebuild_with(rooms=new_rooms)
        raise EmpireInvariantViolation(
            kind="room_not_found",
            message=f"[FAIL] Room not found in Empire: room_id={room_id}",
            detail={"room_id": str(room_id)},
        )

    def archive(self) -> Empire:
        """Return a new :class:`Empire` with ``archived=True``.

        Implements the logical delete (UC-EM-010 / 確定 H). Returns a new
        frozen instance; callers pass the result to
        ``EmpireRepository.save(archived_empire)`` to persist the state
        change inside the Unit-of-Work.
        """
        return Empire.model_validate(self.model_dump() | {"archived": True})

    # ------------------------------------------------------------------
    # Internal: pre-validate rebuild (Confirmation A)
    # ------------------------------------------------------------------
    def _rebuild_with(
        self,
        *,
        rooms: list[RoomRef] | None = None,
        agents: list[AgentRef] | None = None,
    ) -> Empire:
        """Re-construct via ``model_validate`` so ``model_validator`` re-fires.

        The candidate dict is built from ``model_dump()`` (which yields fully
        primitive structures) so swapped-in lists end up homogeneous: Pydantic
        re-coerces dicts back into ``RoomRef`` / ``AgentRef`` instances during
        validation, matching the form taken when an Empire is first constructed.
        """
        state = self.model_dump()
        if rooms is not None:
            state["rooms"] = [room.model_dump() for room in rooms]
        if agents is not None:
            state["agents"] = [agent.model_dump() for agent in agents]
        return Empire.model_validate(state)


__all__ = [
    "MAX_AGENTS",
    "MAX_NAME_LENGTH",
    "MAX_ROOMS",
    "MIN_NAME_LENGTH",
    "Empire",
]

