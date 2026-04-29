"""InternalReviewGate 用の Verdict Value Object。

Verdict は InternalReviewGate に提出されるエージェント 1 体のレビュー判定を表す。
Aggregate 内では追記専用で保持され、各エントリは厳密に 1 つのロールに対応する。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bakufu.domain.value_objects.enums import VerdictDecision
from bakufu.domain.value_objects.gate_role import GateRole
from bakufu.domain.value_objects.identifiers import AgentId

# ---------------------------------------------------------------------------
# Verdict VO（InternalReviewGate feature）
# ---------------------------------------------------------------------------
_VERDICT_COMMENT_MAX_CHARS: int = 5_000


class Verdict(BaseModel):
    """:class:`InternalReviewGate` に提出されるエージェント 1 体の判定。

    Aggregate 内では ``tuple[Verdict, ...]`` として保持され、タプルは追記専用
    （frozen Aggregate 再構築パターン）。各エントリは厳密に 1 つの :attr:`role`
    に対応する — 重複ロールは ``aggregate_validators._validate_no_duplicate_roles``
    で拒否される。

    フィールド:

    * ``role`` — 提出エージェントが代表する :data:`GateRole` slug。
    * ``agent_id`` — 提出エージェントの UUID。
    * ``decision`` — :class:`VerdictDecision`（APPROVED / REJECTED）。
    * ``comment`` — 自由形式の NFC 正規化テキスト、0〜5000 文字。
      **strip は適用しない**（先頭空白に意味を持たせ得る複数行レビュー コメント
      は保持しなければならない — ``AuditEntry.comment`` / ``Directive.text`` と
      同じ先例）。
    * ``decided_at`` — 判定が提出された UTC tz-aware モーメント。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    role: GateRole
    agent_id: AgentId
    decision: VerdictDecision
    comment: str = Field(default="", max_length=_VERDICT_COMMENT_MAX_CHARS)
    decided_at: datetime

    @field_validator("comment", mode="before")
    @classmethod
    def _normalize_comment(cls, value: object) -> object:
        """NFC 正規化のみ — strip は意図的に **適用しない**。"""
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("decided_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Verdict.decided_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value


__all__ = [
    "_VERDICT_COMMENT_MAX_CHARS",
    "Verdict",
]
