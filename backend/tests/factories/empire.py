"""Factories for the Empire aggregate and its reference VOs.

Per ``docs/features/empire/test-design.md`` (REQ-EM-001〜005, factories), each
factory:

* Returns a *valid* default instance built via the production constructor.
* Allows keyword overrides so individual tests can exercise specific edge
  cases without copy-pasting full kwargs.
* Registers the produced instance in :data:`_SYNTHETIC_REGISTRY` so
  :func:`is_synthetic` can later confirm "this object came from a factory".

Why a ``WeakValueDictionary`` over inline metadata?

* :class:`bakufu.domain.empire.Empire`, :class:`RoomRef` and :class:`AgentRef`
  are ``frozen=True`` Pydantic v2 models with ``extra='forbid'`` — adding a
  ``_meta.synthetic`` attribute (the naive approach) is physically impossible.
* A weak-value registry keyed by ``id(instance)`` lets us flag instances
  externally; entries auto-evict when the value is garbage collected, so
  ``id`` reuse on a freshly allocated, unrelated instance simply yields a
  cache miss instead of a false positive.

Production code MUST NOT import this module — it lives under ``tests/`` to
keep the synthetic-data boundary auditable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.empire import Empire
from bakufu.domain.value_objects import AgentRef, Role, RoomRef
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# Module-scope registry. Values are kept weakly so GC pressure stays neutral;
# we only want to know "did a factory produce this object" while it's alive.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module.

    The check is identity-based (``id``) rather than structural so two
    independently-produced equal instances are still distinguishable: only the
    actual object the factory returned is marked synthetic.
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """Record ``instance`` in the synthetic registry."""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# RoomRef factory
# ---------------------------------------------------------------------------
def make_room_ref(
    *,
    room_id: UUID | None = None,
    name: str = "ルーム",
    archived: bool = False,
) -> RoomRef:
    """Build a valid :class:`RoomRef` and register it as synthetic."""
    ref = RoomRef(
        room_id=room_id if room_id is not None else uuid4(),
        name=name,
        archived=archived,
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# AgentRef factory
# ---------------------------------------------------------------------------
def make_agent_ref(
    *,
    agent_id: UUID | None = None,
    name: str = "エージェント",
    role: Role = Role.DEVELOPER,
) -> AgentRef:
    """Build a valid :class:`AgentRef` and register it as synthetic."""
    ref = AgentRef(
        agent_id=agent_id if agent_id is not None else uuid4(),
        name=name,
        role=role,
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# Empire factory
# ---------------------------------------------------------------------------
def make_empire(
    *,
    empire_id: UUID | None = None,
    name: str = "テスト幕府",
    rooms: Sequence[RoomRef] | None = None,
    agents: Sequence[AgentRef] | None = None,
) -> Empire:
    """Build a valid :class:`Empire` and register it as synthetic.

    Defaults yield an empty Empire with no rooms or agents — the simplest
    valid aggregate state, suitable for the majority of tests that then mutate
    via the public ``hire_agent`` / ``establish_room`` / ``archive_room``
    behaviors.
    """
    empire = Empire(
        id=empire_id if empire_id is not None else uuid4(),
        name=name,
        rooms=list(rooms) if rooms is not None else [],
        agents=list(agents) if agents is not None else [],
    )
    _register(empire)
    return empire


__all__ = [
    "is_synthetic",
    "make_agent_ref",
    "make_empire",
    "make_room_ref",
]
