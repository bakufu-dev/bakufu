"""Infrastructure-layer exceptions.

These exceptions are raised by Bootstrap stages and the masking gateway.
They map 1:1 with MSG-PF-001〜008 in
``docs/features/persistence-foundation/detailed-design/messages.md``.

* :class:`BakufuConfigError` — DATA_DIR / engine / migration / FS init
  failures (MSG-PF-001 / 002 / 003 / 008). Bootstrap catches and exits
  with a non-zero code.
* :class:`BakufuMigrationError` — Alembic ``upgrade`` failures (MSG-PF-004).
  Subclass of :class:`BakufuConfigError` so the Bootstrap top-level
  ``except`` still catches it; subclassing keeps log filtering possible.
* :class:`HandlerNotRegisteredError` — raised by the Outbox handler
  registry when an event_kind has no registered handler. The Outbox
  dispatcher catches and warns, returning the row to ``status='PENDING'``.
"""

from __future__ import annotations


class BakufuConfigError(Exception):
    """Raised when infrastructure configuration cannot be established.

    Carries an MSG-PF-NNN identifier in :attr:`msg_id` so downstream log
    formatters / test assertions can branch on the specific failure
    without parsing free-form text.
    """

    def __init__(self, *, msg_id: str, message: str) -> None:
        super().__init__(message)
        self.msg_id: str = msg_id
        self.message: str = message


class BakufuMigrationError(BakufuConfigError):
    """Alembic ``upgrade`` failure (MSG-PF-004).

    Inherits from :class:`BakufuConfigError` so a top-level ``except``
    in the Bootstrap loop still catches the failure while preserving the
    ability to filter migration-specific issues in test setups.
    """


class HandlerNotRegisteredError(KeyError):
    """Raised by :class:`HandlerRegistry.resolve` when no handler exists.

    Inherits from :class:`KeyError` so callers that already handle
    "missing key" generically degrade gracefully. The Outbox dispatcher
    catches this and re-marks the row ``PENDING`` for the next cycle.
    """


__all__ = [
    "BakufuConfigError",
    "BakufuMigrationError",
    "HandlerNotRegisteredError",
]
