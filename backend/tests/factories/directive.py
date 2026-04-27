"""Factories for the Directive Aggregate Root.

Per ``docs/features/directive/test-design.md``. Mirrors the
empire / workflow / agent / room pattern: every factory returns a
*valid* default instance built through the production constructor,
allows keyword overrides, and registers the result in a
:class:`WeakValueDictionary` so :func:`is_synthetic` can later flag
test-built objects without mutating the frozen Pydantic model.

Default Directive carries a short ``text`` body and ``task_id=None``.
``LinkedDirectiveFactory`` constructs the post-link state directly
(Repository hydration scenario, §確定 C). ``LongTextDirectiveFactory``
sits at the upper boundary (10000 chars).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.directive import Directive
from pydantic import BaseModel

# Module-scope registry. Values are kept weakly so GC pressure stays neutral.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module."""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """Record ``instance`` in the synthetic registry."""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


def make_directive(
    *,
    directive_id: UUID | None = None,
    text: str = "$ ブログ分析機能を作って",
    target_room_id: UUID | None = None,
    created_at: datetime | None = None,
    task_id: UUID | None = None,
) -> Directive:
    """Build a valid :class:`Directive`.

    Defaults: short ``text`` containing the ``$`` prefix the
    application layer would have normalized, ``task_id=None`` (not yet
    linked), ``created_at=datetime.now(UTC)`` so the tz-aware
    constraint is satisfied without per-test setup.
    """
    directive = Directive(
        id=directive_id if directive_id is not None else uuid4(),
        text=text,
        target_room_id=target_room_id if target_room_id is not None else uuid4(),
        created_at=created_at if created_at is not None else datetime.now(UTC),
        task_id=task_id,
    )
    _register(directive)
    return directive


def make_linked_directive(
    *,
    directive_id: UUID | None = None,
    text: str = "$ 既に紐付け済みの directive",
    target_room_id: UUID | None = None,
    task_id: UUID | None = None,
) -> Directive:
    """Build a Directive that already has a non-``None`` ``task_id``.

    Repository hydration scenario (§確定 C): the constructor accepts
    a permanent ``task_id`` value for restoring an already-linked
    Directive from disk. ``link_task`` against the returned instance
    will Fail Fast.
    """
    return make_directive(
        directive_id=directive_id,
        text=text,
        target_room_id=target_room_id,
        task_id=task_id if task_id is not None else uuid4(),
    )


def make_long_text_directive() -> Directive:
    """Build a Directive at the upper boundary (10000 NFC chars)."""
    return make_directive(text="a" * 10_000)


__all__ = [
    "is_synthetic",
    "make_directive",
    "make_linked_directive",
    "make_long_text_directive",
]
