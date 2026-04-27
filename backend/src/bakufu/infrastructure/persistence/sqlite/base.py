"""Declarative base + cross-cutting :class:`TypeDecorator` adapters.

Every table in the bakufu SQLite schema inherits from :class:`Base`
(re-exported below). The custom column types here are **mandatory**
for any table that holds the corresponding semantic value:

* :class:`UUIDStr` — store ``uuid.UUID`` as a 32-character hex string
  in SQLite (no native UUID type; ``BLOB(16)`` was rejected because it
  hurts ``sqlite3`` CLI debuggability).
* :class:`UTCDateTime` — Fail-Fast on naive ``datetime`` and store
  the UTC ISO-8601 string. The "always tz-aware" contract eliminates
  every "is this UTC or local?" bug in downstream code.
* :class:`JSONEncoded` — ``dict`` / ``list`` → ``json.dumps`` with
  ``sort_keys=True`` so logical equality is byte-equal in the row.

The masking listeners live in the table modules, not here, because
the responsibility (which columns are secret-bearing) is per-table.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CHAR, Dialect, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common declarative base for all bakufu SQLite tables."""


class UUIDStr(TypeDecorator[UUID]):
    """Store a :class:`uuid.UUID` as ``CHAR(32)`` hex in SQLite.

    The 32-character hex form (no dashes) keeps the storage compact
    while remaining trivially inspectable from the ``sqlite3`` CLI.
    Round-trips ``uuid.UUID`` so ORM-side code never sees a string
    representation.
    """

    impl = CHAR(32)
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: UUID | str | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect  # unused; SQLite is the only target
        if value is None:
            return None
        if isinstance(value, UUID):
            return value.hex
        # Accept str inputs too so ad-hoc INSERTs from raw SQL still
        # round-trip cleanly. ``UUID(str)`` validates the format.
        return UUID(value).hex

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> UUID | None:
        del dialect
        if value is None:
            return None
        return UUID(value)


class UTCDateTime(TypeDecorator[datetime]):
    """Always-UTC, always-tz-aware ``datetime`` column.

    Inserts a naive ``datetime`` raise ``ValueError`` immediately so
    timezone bugs cannot land silently. The on-disk representation is
    ISO-8601 with the ``+00:00`` offset, sortable as a string.
    """

    impl = Text()
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "UTCDateTime requires a timezone-aware datetime "
                "(received a naive value)"
            )
        return value.isoformat()

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        return datetime.fromisoformat(value)


class JSONEncoded(TypeDecorator[Any]):
    """``dict`` / ``list`` ↔ JSON text column.

    Uses ``sort_keys=True`` so two semantically-equal payloads serialize
    to byte-equal text — important for hash-comparison and migration
    diffs. ``ensure_ascii=False`` keeps Japanese strings readable in
    direct SQLite inspection.
    """

    impl = Text()
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: object,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> object:
        del dialect
        if value is None:
            return None
        return json.loads(value)


__all__ = [
    "Base",
    "JSONEncoded",
    "UTCDateTime",
    "UUIDStr",
]
