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
secret-bearing columns registers ``before_insert`` / ``before_update``
listeners that route the column values through this gateway.
"""
