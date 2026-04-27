"""Factories for the Room aggregate, its entities, and its VOs.

Per ``docs/features/room/test-design.md``. Mirrors the empire / workflow /
agent pattern: every factory returns a *valid* default instance built through
the production constructor, allows keyword overrides, and registers the
result in a :class:`WeakValueDictionary` so :func:`is_synthetic` can later
flag test-built objects without mutating the frozen Pydantic models.

Default Room composes one ``LeaderMembership`` and zero PromptKit prefix
content so the simplest construction path covers TC-UT-RM-001 with no extra
setup. Tests that need an empty members list pass ``members=[]`` explicitly,
which is allowed (Aggregate-level invariants accept 0〜:data:`MAX_MEMBERS`
entries — leader-required is an application-layer responsibility, see
TC-UT-RM-029).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.room import (
    AgentMembership,
    PromptKit,
    Room,
)
from bakufu.domain.value_objects import Role
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# Module-scope registry. Values are kept weakly so GC pressure stays neutral.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module."""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """Record ``instance`` in the synthetic registry."""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# AgentMembership
# ---------------------------------------------------------------------------
def make_agent_membership(
    *,
    agent_id: UUID | None = None,
    role: Role = Role.DEVELOPER,
    joined_at: datetime | None = None,
) -> AgentMembership:
    """Build a valid :class:`AgentMembership` (default role DEVELOPER)."""
    membership = AgentMembership(
        agent_id=agent_id if agent_id is not None else uuid4(),
        role=role,
        joined_at=joined_at if joined_at is not None else datetime.now(UTC),
    )
    _register(membership)
    return membership


def make_leader_membership(
    *,
    agent_id: UUID | None = None,
    joined_at: datetime | None = None,
) -> AgentMembership:
    """Build a LEADER-role :class:`AgentMembership` for populated Room scenarios."""
    return make_agent_membership(
        agent_id=agent_id,
        role=Role.LEADER,
        joined_at=joined_at,
    )


# ---------------------------------------------------------------------------
# PromptKit
# ---------------------------------------------------------------------------
def make_prompt_kit(
    *,
    prefix_markdown: str = "",
) -> PromptKit:
    """Build a valid :class:`PromptKit` (default empty prefix_markdown)."""
    kit = PromptKit(prefix_markdown=prefix_markdown)
    _register(kit)
    return kit


def make_long_prompt_kit() -> PromptKit:
    """Build a :class:`PromptKit` at the upper boundary (10000 chars)."""
    return make_prompt_kit(prefix_markdown="a" * 10_000)


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------
def make_room(
    *,
    room_id: UUID | None = None,
    name: str = "Vモデル開発室",
    description: str = "",
    workflow_id: UUID | None = None,
    members: Sequence[AgentMembership] | None = None,
    prompt_kit: PromptKit | None = None,
    archived: bool = False,
) -> Room:
    """Build a valid :class:`Room`.

    With no overrides yields the simplest valid Room: zero members, empty
    description, default empty PromptKit, ``archived=False``. Tests that need
    populated members pass them explicitly via ``members=[...]``.
    """
    if prompt_kit is None:
        prompt_kit = make_prompt_kit()
    room = Room(
        id=room_id if room_id is not None else uuid4(),
        name=name,
        description=description,
        workflow_id=workflow_id if workflow_id is not None else uuid4(),
        members=list(members) if members is not None else [],
        prompt_kit=prompt_kit,
        archived=archived,
    )
    _register(room)
    return room


def make_archived_room(**overrides: object) -> Room:
    """Build a Room with ``archived=True`` for idempotency / terminal-violation setups."""
    return make_room(archived=True, **overrides)  # pyright: ignore[reportArgumentType]


def make_populated_room(
    *,
    room_id: UUID | None = None,
    leader_agent_id: UUID | None = None,
    developer_agent_id: UUID | None = None,
) -> Room:
    """Build a Room with one LEADER + one DEVELOPER membership.

    Useful for TC-IT-RM-001 / 002 round-trip scenarios that exercise add /
    remove / update / archive transitions over a non-empty member list.
    """
    return make_room(
        room_id=room_id,
        members=[
            make_leader_membership(agent_id=leader_agent_id),
            make_agent_membership(agent_id=developer_agent_id, role=Role.DEVELOPER),
        ],
    )


__all__ = [
    "is_synthetic",
    "make_agent_membership",
    "make_archived_room",
    "make_leader_membership",
    "make_long_prompt_kit",
    "make_populated_room",
    "make_prompt_kit",
    "make_room",
]
