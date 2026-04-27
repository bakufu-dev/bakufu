"""Application layer.

Sits between :mod:`bakufu.domain` (pure DDD aggregates) and
:mod:`bakufu.infrastructure` (SQLite / FS / process I/O). The layer
owns:

* **Ports** (:mod:`bakufu.application.ports`) — :class:`typing.Protocol`
  contracts that the infrastructure layer must satisfy. Hexagonal
  Architecture's "ports and adapters" pattern.
* **Services** (later PRs) — orchestration / Unit-of-Work coordination
  / cross-aggregate Tx boundaries.

Dependency direction is **strictly** ``domain ← application ←
infrastructure``: this package may import from ``domain`` but not from
``infrastructure``; ``infrastructure`` imports the ports defined here
to declare adapter classes.
"""
