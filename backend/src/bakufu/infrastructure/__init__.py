"""bakufu infrastructure layer.

Holds all I/O-heavy code: SQLite + Alembic persistence, secret masking
gateway, OS-bound configuration (DATA_DIR / pid_registry GC), and the
Backend bootstrap sequence. The dependency direction is **strictly**
``domain → no one`` and ``infrastructure → domain``: domain code must not
import from this package, and the test suite enforces that contract via
``tests/architecture/test_dependency_direction.py``.

See ``docs/features/persistence-foundation`` for the full design.
"""
