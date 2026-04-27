"""Secret masking gateway.

The single source of truth for redacting secrets *before* they hit any
persistence boundary (SQLite rows, structured log files, audit log).
Two consumer surfaces:

* :func:`bakufu.infrastructure.security.masking.mask` — single-string
  redaction.
* :func:`bakufu.infrastructure.security.masking.mask_in` — recursive
  walker for ``dict`` / ``list`` / ``tuple`` payloads.

Wiring contracts (Confirmation B) live in the table modules under
``infrastructure/persistence/sqlite/tables/``: each table that holds
secret-bearing columns declares its columns with the
:class:`MaskedJSONEncoded` / :class:`MaskedText` TypeDecorators
(defined in :mod:`bakufu.infrastructure.persistence.sqlite.base`) so
that ``process_bind_param`` routes the values through this gateway
on every Core / ORM bind. See
``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D for why event listeners were reverse-rejected
(BUG-PF-001).
"""
