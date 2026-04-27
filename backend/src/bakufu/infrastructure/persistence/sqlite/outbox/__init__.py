"""Outbox dispatcher + handler registry skeleton.

The dispatcher polls ``domain_event_outbox``, marks rows
``DISPATCHING``, looks up the handler for the row's ``event_kind`` in
:mod:`...handler_registry`, awaits the handler, and updates the row to
``DISPATCHED`` (success) / ``PENDING`` with an incremented
``attempt_count`` (failure) / ``DEAD_LETTER`` (after 5 failures).

Per Schneier 中等 3 (Confirmation K), this PR registers **zero**
handlers — every Outbox row stays ``PENDING`` until subsequent
``feature/{event-kind}-handler`` PRs land. The dispatcher emits a
WARN at startup and on each polling cycle that finds pending rows
with an empty registry, so operators notice the partial wiring.
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.outbox import (
    dispatcher,
    handler_registry,
)

__all__ = ["dispatcher", "handler_registry"]
