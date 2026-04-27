"""Outbox event-kind → handler registry.

Each ``domain_event_outbox`` row carries an ``event_kind`` enum
identifying the side effect the dispatcher should perform
(DirectiveIssued → Task creation, TaskAssigned → WebSocket broadcast,
ExternalReviewRequested → Discord notify, etc.). This module owns the
mapping.

Contracts
---------
* :func:`register` rejects re-registration. Use :func:`clear` in tests
  to reset state — production code should never silently overwrite a
  handler.
* :func:`resolve` raises
  :class:`bakufu.infrastructure.exceptions.HandlerNotRegisteredError`
  when no handler is present. The dispatcher catches and re-marks the
  row ``PENDING`` for the next cycle.
* :func:`size` exposes the registered count for the Bootstrap
  startup-WARN logic (Confirmation K).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from bakufu.infrastructure.exceptions import HandlerNotRegisteredError

# Handlers receive a payload dict and return ``None`` (any persistence
# side effect lands in the same Unit-of-Work as the dispatcher).
type EventHandler = Callable[[dict[str, object]], Awaitable[None]]

_handlers: dict[str, EventHandler] = {}


def register(event_kind: str, handler: EventHandler) -> None:
    """Bind ``event_kind`` to ``handler``. Raises if already bound.

    Re-registration is rejected so two PRs cannot silently fight over
    the same event_kind. Tests should call :func:`clear` between
    cases.
    """
    if event_kind in _handlers:
        raise KeyError(
            f"Handler already registered for event_kind={event_kind!r}; "
            "call clear() in test setups to reset"
        )
    _handlers[event_kind] = handler


def resolve(event_kind: str) -> EventHandler:
    """Return the handler bound to ``event_kind`` or raise.

    Raises:
        HandlerNotRegisteredError: when no handler is registered. The
            dispatcher catches this and warns + re-marks the row
            ``PENDING`` for the next cycle.
    """
    handler = _handlers.get(event_kind)
    if handler is None:
        raise HandlerNotRegisteredError(event_kind)
    return handler


def clear() -> None:
    """Drop all registered handlers. Test-only helper."""
    _handlers.clear()


def size() -> int:
    """Return the registered handler count."""
    return len(_handlers)


__all__ = [
    "EventHandler",
    "clear",
    "register",
    "resolve",
    "size",
]
