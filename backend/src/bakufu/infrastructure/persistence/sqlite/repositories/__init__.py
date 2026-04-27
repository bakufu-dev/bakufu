"""SQLite Repository adapters (one module per Aggregate).

Each module exports a class that satisfies the matching
:class:`typing.Protocol` defined in :mod:`bakufu.application.ports`.
Empire (PR #25) is the first Repository PR; the same pattern applies
to subsequent ``feature/{aggregate}-repository`` PRs:

* ``__init__(session: AsyncSession)`` — keeps the caller-managed Tx
  boundary (Repositories never call ``session.commit()`` /
  ``session.rollback()``).
* ``find_by_id`` / ``count`` / ``save`` are ``async def``.
* Reference / child tables are updated via delete-then-insert
  (§確定 B) inside the caller's transaction.
* ``_to_row`` / ``_from_row`` are private and convert between domain
  Aggregate Roots and ``dict`` payloads (§確定 C).
"""
