"""Attachment and Deliverable value objects for the Task feature.

Implements Task detailed-design §確定 R1-E: per-Stage deliverable snapshots
and the file-reference (Attachment) VO with storage.md validation rules.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bakufu.domain.value_objects.identifiers import AgentId, StageId

# ---------------------------------------------------------------------------
# Attachment / Deliverable VOs (Task feature §確定 R1-E)
# ---------------------------------------------------------------------------
# §Attachment storage.md 凍結値. Mirror them as module-level constants so the
# field validators read clearly and tests can import the same source.

_ATTACHMENT_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MiB
_ATTACHMENT_MAX_FILENAME_CHARS: int = 255
_ATTACHMENT_FILENAME_REJECTED_CHARS: frozenset[str] = frozenset(
    {"/", "\\", "\0"} | {chr(c) for c in range(0x00, 0x20)} | {chr(0x7F)}
)
# Windows reserved device names — case-insensitive, with or without extensions.
_ATTACHMENT_WINDOWS_RESERVED: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
# Whitelist per storage.md §MIME タイプ検証 (text/html / text/csv 拒否).
_ATTACHMENT_MIME_WHITELIST: frozenset[str] = frozenset(
    {
        "text/markdown",
        "text/plain",
        "application/json",
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "application/octet-stream",
    }
)
_DELIVERABLE_BODY_MAX_CHARS: int = 1_000_000


class Attachment(BaseModel):
    """File reference held inside :class:`Deliverable`.

    Implements the storage.md §filename サニタイズ規則 6 段階, the MIME
    whitelist, the 10 MiB byte cap, and the 64-hex sha256 contract per
    Task detailed-design §VO: Attachment. The Aggregate (Task) does not
    re-validate these — the VO ``model_validator(mode='after')`` is the
    single gate so a hydration path (Repository round-trip) hits the same
    checks as construction time.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    sha256: str
    filename: str
    mime_type: str
    size_bytes: int

    @field_validator("sha256", mode="after")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if not _ATTACHMENT_SHA256_RE.fullmatch(value):
            raise ValueError(
                "Attachment.sha256 must match ^[a-f0-9]{64}$ (lowercase hex, 64 chars)"
            )
        return value

    @field_validator("filename", mode="before")
    @classmethod
    def _normalize_filename(cls, value: object) -> object:
        # Storage.md §filename サニタイズ規則 step 1-2: NFC normalize first
        # so the length / character checks below see the canonical form.
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("filename", mode="after")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        # Step 1: length (NFC-normalized code-point count).
        length = len(value)
        if not (1 <= length <= _ATTACHMENT_MAX_FILENAME_CHARS):
            raise ValueError(
                f"Attachment.filename must be 1-{_ATTACHMENT_MAX_FILENAME_CHARS} "
                f"NFC-normalized characters (got length={length})"
            )
        # Step 3: rejected characters (path separators, NUL, control chars).
        bad_chars = sorted({ch for ch in value if ch in _ATTACHMENT_FILENAME_REJECTED_CHARS})
        if bad_chars:
            raise ValueError(
                f"Attachment.filename contains rejected characters: {bad_chars!r} "
                "(path separators / NUL / ASCII control chars are not allowed)"
            )
        # Step 4: rejected sequences.
        if ".." in value:
            raise ValueError("Attachment.filename must not contain '..' (path traversal sequence)")
        if value.startswith(".") or value.endswith("."):
            raise ValueError(
                "Attachment.filename must not start or end with '.' "
                "(Windows / POSIX hidden / extension trick)"
            )
        if value != value.strip():
            raise ValueError("Attachment.filename must not start or end with whitespace")
        if ":" in value:
            raise ValueError(
                "Attachment.filename must not contain ':' (Windows ADS / drive-letter trick)"
            )
        # Step 5: Windows reserved device names (with or without extension).
        stem = value.split(".", 1)[0].upper()
        if stem in _ATTACHMENT_WINDOWS_RESERVED:
            raise ValueError(f"Attachment.filename uses a reserved Windows device name: {stem!r}")
        # Step 6: basename round-trip (path-traversal double-defense).
        # ``PurePosixPath`` reads ``/`` as a separator regardless of the
        # host OS, mirroring the storage.md sanitization rule which
        # rejects POSIX path components by design.
        if PurePosixPath(value).name != value:
            raise ValueError(
                "Attachment.filename must equal its basename (path components are not allowed)"
            )
        return value

    @field_validator("mime_type", mode="after")
    @classmethod
    def _validate_mime(cls, value: str) -> str:
        if value not in _ATTACHMENT_MIME_WHITELIST:
            raise ValueError(
                f"Attachment.mime_type must be one of "
                f"{sorted(_ATTACHMENT_MIME_WHITELIST)!r} (got {value!r}); "
                "text/html and text/csv are rejected by storage.md."
            )
        return value

    @field_validator("size_bytes", mode="after")
    @classmethod
    def _validate_size(cls, value: int) -> int:
        if not (0 <= value <= _ATTACHMENT_MAX_BYTES):
            raise ValueError(
                f"Attachment.size_bytes must satisfy 0 <= size <= "
                f"{_ATTACHMENT_MAX_BYTES} (got {value})"
            )
        return value


class Deliverable(BaseModel):
    """Per-Stage deliverable snapshot held inside :class:`Task`.

    The Aggregate Root keeps a ``dict[StageId, Deliverable]`` so the
    "Stage ごとに最新 1 件" contract (Task detailed-design §確定 R1-E)
    is enforced by Python dict semantics. ``body_markdown`` is the
    raw CEO/Agent-authored content — masking happens at the Repository
    layer (``MaskedText`` TypeDecorator on ``task_deliverables.body_markdown``,
    landed in ``feature/task-repository``).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    stage_id: StageId
    body_markdown: str = Field(default="", max_length=_DELIVERABLE_BODY_MAX_CHARS)
    attachments: list[Attachment] = []
    committed_by: AgentId
    committed_at: datetime

    @field_validator("committed_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Deliverable.committed_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value


__all__ = [
    "Attachment",
    "Deliverable",
]
