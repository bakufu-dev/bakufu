"""Aggregate 内部で保持される参照型 Value Object。

含まれるもの:
- :class:`RoomRef` — Room Aggregate へのフローズン参照（Empire 内で使用）。
- :class:`AgentRef` — Agent Aggregate へのフローズン参照（Empire 内で使用）。
- :class:`CompletionPolicy` — Stage の完了判定方法（Workflow VO）。
- :class:`NotifyChannel` — ``EXTERNAL_REVIEW`` Stage 用の Webhook チャネル。
- :class:`AuditEntry` — ExternalReviewGate 監査証跡の 1 行。
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from bakufu.domain.value_objects.enums import AuditAction, Role
from bakufu.domain.value_objects.helpers import (
    NormalizedAgentName,
    NormalizedShortName,
    mask_discord_webhook,
)
from bakufu.domain.value_objects.identifiers import AgentId, OwnerId, RoomId

# ---------------------------------------------------------------------------
# 参照型 Value Object（Empire Aggregate 内部で保持）
# ---------------------------------------------------------------------------


class RoomRef(BaseModel):
    """:class:`Empire` 内部で保持される Room Aggregate へのフローズン参照。

    等価性とハッシュは構造的（Pydantic が ``archived`` を含む全フィールドで自動実装）
    である。したがって 2 つの ``RoomRef`` は ``room_id`` *と* archived 状態の両方が
    一致するときのみ等しいと判定される — ``Empire.archive_room`` 中の正しいリスト
    差分計算のために必要。
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
    """:class:`Empire` 内部で保持される Agent Aggregate へのフローズン参照。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    agent_id: AgentId
    name: NormalizedAgentName
    role: Role


# ---------------------------------------------------------------------------
# CompletionPolicy VO
# ---------------------------------------------------------------------------
type CompletionPolicyKind = Literal[
    "approved_by_reviewer",
    "all_checklist_checked",
    "manual",
]


class CompletionPolicy(BaseModel):
    """:class:`Stage` の完了判定方法（Workflow detailed-design §VO）。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    kind: CompletionPolicyKind
    description: str = Field(default="", min_length=0, max_length=200)


# ---------------------------------------------------------------------------
# NotifyChannel VO（Workflow §Confirmation G — SSRF / A10 対策）
# ---------------------------------------------------------------------------
type NotifyChannelKind = Literal["discord"]
"""MVP では ``'discord'`` のみ受け付ける。``'slack'`` / ``'email'`` は、ターゲット
正規化、SSRF ルール、シークレット マスキングのコントラクトが凍結される Phase 2
まで延期 — Workflow detailed-design §確定 G を参照。"""

# G7: Discord Webhook URL のパス用アンカー付き正規表現。
# id  = 1〜30 桁の数字（Discord snowflake の範囲）
# tok = 1〜100 文字の URL 安全文字（Base64 アルファベット + '-' + '_'）
_DISCORD_WEBHOOK_PATH_RE = re.compile(r"^/api/webhooks/[0-9]{1,30}/[A-Za-z0-9_\-]{1,100}$")


class NotifyChannel(BaseModel):
    """``EXTERNAL_REVIEW`` Stage に紐づく Webhook チャネル。

    ``§Confirmation G`` のルール **G1〜G10** を ``target`` 上の単一の
    ``field_validator`` として実装する。これにより、いずれか 1 つの違反でも
    インスタンスが観測可能になる *前* に ``pydantic.ValidationError`` を発生
    させる。``mode='json'`` へのシリアライザ ダウングレードはシークレットの
    ``token`` セグメントを伏字化する（G「target のシークレット扱い」）。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    kind: NotifyChannelKind
    target: str = Field(min_length=1, max_length=500)

    # G1 / G2 / G3 / G4 / G5 / G6 / G7 / G8 / G9 / G10 — 単一ゲート。
    @field_validator("target", mode="after")
    @classmethod
    def _validate_target(cls, target: str) -> str:
        # G2: urllib.parse.urlparse でパース（startswith / 正規表現の近道は使わない）。
        parsed = urlparse(target)
        # G3: HTTPS のみ（urlparse は scheme を小文字化済み）。
        if parsed.scheme != "https":
            raise ValueError(
                f"NotifyChannel.target violates G3 (scheme): expected 'https', "
                f"got {parsed.scheme!r}"
            )
        # G4: hostname は厳密に 'discord.com' でなければならない（urlparse がホストを
        # 小文字化）。
        if parsed.hostname != "discord.com":
            raise ValueError(
                f"NotifyChannel.target violates G4 (hostname): expected "
                f"'discord.com', got {parsed.hostname!r}"
            )
        # G5: port は未設定または 443 のみ。
        if parsed.port not in (None, 443):
            raise ValueError(
                f"NotifyChannel.target violates G5 (port): expected None or 443, "
                f"got {parsed.port!r}"
            )
        # G6: userinfo は持たない — 'https://attacker@discord.com/...' トリックを阻止。
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "NotifyChannel.target violates G6 (userinfo): URL must not "
                "contain user/password info"
            )
        # G7 + G10: path は Discord Webhook 正規表現と完全一致（大文字小文字を区別）。
        if not _DISCORD_WEBHOOK_PATH_RE.fullmatch(parsed.path):
            raise ValueError(
                "NotifyChannel.target violates G7/G10 (path): expected "
                "/api/webhooks/<id>/<token> (lowercase 'api/webhooks')"
            )
        # G8: query は空でなければならない。
        if parsed.query != "":
            raise ValueError("NotifyChannel.target violates G8 (query): expected empty")
        # G9: fragment は空でなければならない。
        if parsed.fragment != "":
            raise ValueError("NotifyChannel.target violates G9 (fragment): expected empty")
        return target

    # VO が JSON にシリアライズされる際は常にシークレット トークン セグメントを伏字化
    # する（model_dump(mode='json') / model_dump_json()）。Python モードのデフォルト
    # model_dump() はプロセス内 Workflow 操作のため raw target を保持する。永続化 /
    # ログ境界は常に JSON モードを通る。
    @field_serializer("target", when_used="json")
    def _serialize_target_masked(self, target: str) -> str:
        return mask_discord_webhook(target)


# ---------------------------------------------------------------------------
# AuditEntry VO（ExternalReviewGate feature §確定 K）
# ---------------------------------------------------------------------------
_AUDIT_COMMENT_MAX_CHARS: int = 2_000


class AuditEntry(BaseModel):
    """:class:`ExternalReviewGate.audit_trail` の 1 行。

    Gate Aggregate 内部に追記専用で保存される。
    ``docs/features/external-review-gate/detailed-design.md`` §確定 C を参照。
    「誰がいつ何度見たか」要件（§確定 G）により、``record_view`` 呼び出しの度に
    新しいエントリが生成される — 同一アクター・同一時刻・同一コメントでも
    **重複排除しない**。フィールドは絞り込まれている:

    * ``id`` — それ以外が等しいエントリを区別する UUIDv4。
    * ``actor_id`` — アクションを発火した人間の :class:`OwnerId`。
    * ``action`` — :class:`AuditAction` 識別子（MVP では VIEWED / APPROVED /
      REJECTED / CANCELLED）。
    * ``comment`` — 自由形式の NFC 正規化テキスト、0〜2000 文字、
      **strip は適用しない**（directive / task / agent の LLM スタックトレース
      先例がここでも踏襲される）。
    * ``occurred_at`` — UTC タイムゾーン付きの瞬間。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: UUID
    actor_id: OwnerId
    action: AuditAction
    comment: str = Field(default="", max_length=_AUDIT_COMMENT_MAX_CHARS)
    occurred_at: datetime

    @field_validator("comment", mode="before")
    @classmethod
    def _normalize_comment(cls, value: object) -> object:
        # NFC のみ — 先頭の空白や複数行コンテキストを保持する（CEO のコメントは
        # インデント引用を含むことがある）。
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("occurred_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "AuditEntry.occurred_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value


__all__ = [
    "AgentRef",
    "AuditEntry",
    "CompletionPolicy",
    "CompletionPolicyKind",
    "NotifyChannel",
    "NotifyChannelKind",
    "RoomRef",
]
