"""Shared domain value objects and ID types.

This module hosts identifiers, enums, and reference VOs that other Aggregates
in the bakufu domain depend on. Per ``docs/architecture/domain-model/value-objects.md``,
ID types are conceptually distinct UUIDv4 values; for the empire feature they
are exposed as PEP 695 ``type`` aliases over ``UUID`` to keep the surface
minimal and Pydantic serialization unambiguous. Future features may refine
them via ``NewType`` without changing field shapes.

The name normalization pipeline (NFC → strip → length) is centralized in
:func:`nfc_strip` and applied to every VO/Aggregate that exposes a ``name``
field, fulfilling detailed-design §Confirmation B's "common policy across
Empire / Room / Agent names".
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# ---------------------------------------------------------------------------
# Identifier types
# ---------------------------------------------------------------------------
type EmpireId = UUID
"""Empire aggregate identifier (UUIDv4 per domain-model/value-objects.md)."""

type RoomId = UUID
"""Room aggregate identifier (UUIDv4)."""

type AgentId = UUID
"""Agent aggregate identifier (UUIDv4)."""


# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------
class Role(StrEnum):
    """Roles an :class:`AgentRef` can take.

    Mirrors the canonical list in ``docs/architecture/domain-model/value-objects.md``.
    Stored as ``str`` (StrEnum) so SQLite/JSON serialization is trivial in later
    persistence features without wrappers.
    """

    LEADER = "LEADER"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"
    REVIEWER = "REVIEWER"
    UX = "UX"
    SECURITY = "SECURITY"
    ASSISTANT = "ASSISTANT"
    DISCUSSANT = "DISCUSSANT"
    WRITER = "WRITER"
    SITE_ADMIN = "SITE_ADMIN"


# ---------------------------------------------------------------------------
# Name normalization (Confirmation B)
# ---------------------------------------------------------------------------
def nfc_strip(value: object) -> object:
    """Apply NFC normalization and ``strip`` per detailed-design §Confirmation B.

    Public so sibling Aggregates (Empire / Workflow / Agent / ...) can share
    the **single** implementation of the normalization pipeline. Operates only
    on ``str`` inputs; non-string values are passed through unchanged so
    Pydantic's downstream type validation reports them with its standard error
    shape rather than silently coercing.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).strip()
    return value


# Public alias used by sibling VOs/Aggregates that adopt the same pipeline.
type NormalizedShortName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=80),
]
"""``str`` annotated with NFC+strip BeforeValidator and 1〜80-char Field bounds.

Used by :class:`RoomRef` and any future VO with the 80-char short-name contract.
"""

type NormalizedAgentName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=40),
]
"""1〜40-char variant for :class:`AgentRef` (Agent.name regulation)."""


# ---------------------------------------------------------------------------
# Reference value objects (held inside Empire aggregate)
# ---------------------------------------------------------------------------
class RoomRef(BaseModel):
    """Frozen reference to a Room aggregate, kept inside :class:`Empire`.

    Equality and hashing are structural (Pydantic auto-implementation over all
    fields including ``archived``), so two ``RoomRef`` values compare equal
    only when both ``room_id`` *and* archived state agree — required for
    correct list diffing during ``Empire.archive_room``.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    room_id: RoomId
    name: NormalizedShortName
    archived: bool = False


class AgentRef(BaseModel):
    """Frozen reference to an Agent aggregate, kept inside :class:`Empire`."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    agent_id: AgentId
    name: NormalizedAgentName
    role: Role


__all__ = [
    "AgentId",
    "AgentRef",
    "EmpireId",
    "NormalizedAgentName",
    "NormalizedShortName",
    "Role",
    "RoomId",
    "RoomRef",
    "nfc_strip",
]
