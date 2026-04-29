"""Task feature 用の Attachment / Deliverable Value Object。

Task detailed-design §確定 R1-E を実装する: Stage ごとの成果物スナップショット、
および storage.md のバリデーション規則を備えたファイル参照（Attachment）VO。
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bakufu.domain.value_objects.identifiers import AgentId, StageId

# ---------------------------------------------------------------------------
# Attachment / Deliverable VO（Task feature §確定 R1-E）
# ---------------------------------------------------------------------------
# §Attachment storage.md 凍結値。フィールド バリデータが読みやすく、テストも
# 同じ情報源を import できるよう、モジュール レベルの定数としてミラーする。

_ATTACHMENT_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MiB
_ATTACHMENT_MAX_FILENAME_CHARS: int = 255
_ATTACHMENT_FILENAME_REJECTED_CHARS: frozenset[str] = frozenset(
    {"/", "\\", "\0"} | {chr(c) for c in range(0x00, 0x20)} | {chr(0x7F)}
)
# Windows 予約デバイス名 — 大文字小文字を区別せず、拡張子の有無も問わない。
_ATTACHMENT_WINDOWS_RESERVED: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
# storage.md §MIME タイプ検証によるホワイトリスト（text/html / text/csv は拒否）。
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
    """:class:`Deliverable` 内部に保持されるファイル参照。

    storage.md §filename サニタイズ規則 6 段階、MIME ホワイトリスト、10 MiB バイト
    上限、64-hex sha256 コントラクト（Task detailed-design §VO: Attachment）を
    実装する。Aggregate（Task）はこれらを再検証しない — VO の
    ``model_validator(mode='after')`` が単一ゲートとなり、水和経路（リポジトリ往復）
    でも構築時と同じチェックが走る。
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
        # Storage.md §filename サニタイズ規則 step 1-2: 以降の長さ／文字チェックが
        # 正規形を見るよう、まず NFC 正規化する。
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("filename", mode="after")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        # Step 1: 長さ（NFC 正規化済みコードポイント数）。
        length = len(value)
        if not (1 <= length <= _ATTACHMENT_MAX_FILENAME_CHARS):
            raise ValueError(
                f"Attachment.filename must be 1-{_ATTACHMENT_MAX_FILENAME_CHARS} "
                f"NFC-normalized characters (got length={length})"
            )
        # Step 3: 拒否文字（パス区切り、NUL、制御文字）。
        bad_chars = sorted({ch for ch in value if ch in _ATTACHMENT_FILENAME_REJECTED_CHARS})
        if bad_chars:
            raise ValueError(
                f"Attachment.filename contains rejected characters: {bad_chars!r} "
                "(path separators / NUL / ASCII control chars are not allowed)"
            )
        # Step 4: 拒否シーケンス。
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
        # Step 5: Windows 予約デバイス名（拡張子の有無を問わず）。
        stem = value.split(".", 1)[0].upper()
        if stem in _ATTACHMENT_WINDOWS_RESERVED:
            raise ValueError(f"Attachment.filename uses a reserved Windows device name: {stem!r}")
        # Step 6: basename 往復（パス トラバーサル ダブル防御）。
        # ``PurePosixPath`` はホスト OS に関わらず ``/`` を区切り文字として扱うため、
        # 設計上 POSIX パス成分を拒否する storage.md サニタイズ規則と一致する。
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
    """:class:`Task` 内部に保持される Stage ごとの成果物スナップショット。

    Aggregate Root は ``dict[StageId, Deliverable]`` を保持するため、「Stage ごとに
    最新 1 件」コントラクト（Task detailed-design §確定 R1-E）が Python の dict
    セマンティクスで強制される。``body_markdown`` は CEO / Agent が書いた生のコンテ
    ンツである — 伏字化はリポジトリ層で行う（``feature/task-repository`` で投入された
    ``task_deliverables.body_markdown`` 上の ``MaskedText`` TypeDecorator）。
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
