"""Room 固有の Value Object（:class:`AgentMembership` / :class:`PromptKit`）。

これらの VO はファイル レベル境界が責務境界を反映するよう、グローバルな
:mod:`bakufu.domain.value_objects` ではなく ``room/`` パッケージに置く —
Norman が agent / workflow パッケージで承認したのと同じパターン。``Role`` と
``AgentId`` はフィーチャー境界を跨ぐためグローバル モジュールに残す。

``PromptKit.prefix_markdown`` は **NFC のみ**（strip 無し）を適用する: このフィールド
は Markdown テキストを保持し、先頭／末尾の改行は下流のプロンプト レンダラに対して
意味的に重要。Agent の ``Persona.prompt_body`` と同じルール（Agent §確定 E /
Room §確定 B）。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.exceptions import RoomRoleOverrideInvariantViolation
from bakufu.domain.value_objects import AgentId, DeliverableTemplateRef, Role, RoomId

# ---------------------------------------------------------------------------
# AgentMembership（Room §確定 F — (agent_id, role) 対が一意キー）
# ---------------------------------------------------------------------------


class AgentMembership(BaseModel):
    """フローズン メンバシップ エントリ: :class:`Role` を担う :class:`Agent`。

    Room Aggregate は ``list[AgentMembership]`` を保持し、``(agent_id, role)`` 対の
    一意性を強制する — ``agent_id`` 単独 **ではない** — そのため 1 体のエージェントが
    複数のロールを持てる（例 LEADER + REVIEWER）。``joined_at`` をロール毎に保存する
    ことで、UI は「X 日に LEADER として参加、Y 日に REVIEWER 追加」のような表示が
    自然にできる。

    ``docs/design/domain-model/value-objects.md`` §AgentMembership に格納。現時点で
    この VO を構成するのは Room のみ。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    agent_id: AgentId
    role: Role
    joined_at: datetime


# ---------------------------------------------------------------------------
# PromptKit（Room §確定 G — 単一属性 VO、Phase-2 拡張のために構造を維持）
# ---------------------------------------------------------------------------
PROMPT_KIT_PREFIX_MAX: int = 10_000


class PromptKit(BaseModel):
    """Room スコープのシステム プロンプト プリアンブル（Markdown テキスト）。

    現時点では単一属性 VO。構造は Phase 2 が ``variables``、``role_specific_prefix``、
    ``sections`` で拡張する際に :class:`Room` のスキーマ マイグレーションを強いない
    ようにするため存在する（Room §確定 G）。

    永続化層は ``prefix_markdown`` が SQLite の ``rooms`` 行に到達する *前* に
    シークレット マスキングを適用する —
    ``docs/design/domain-model/storage.md`` §シークレットマスキング規則 を参照。
    Aggregate は UI が変更されない値を読み戻せるように生のユーザ入力を保持する。
    マスキング ゲートウェイは **永続化境界のみ** に存在する。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    prefix_markdown: str = ""

    @field_validator("prefix_markdown", mode="before")
    @classmethod
    def _normalize_prefix(cls, value: object) -> object:
        # NFC のみ — Markdown の先頭／末尾空白を保持する（Room §確定 B）。
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_self_invariants(self) -> Self:
        """長さ上限超過時に :class:`pydantic.ValidationError` を送出（MSG-RM-007）。

        Room detailed-design §確定 I は PromptKit の長さ違反が
        ``RoomInvariantViolation`` ではなく ``ValidationError`` として表面化する
        ことを凍結する — Room Aggregate がスコープに入る *前* に失敗するため。
        ``RoomService.update_prompt_kit`` は 2 層で捕捉する（VO 構築 →
        ``ValidationError``、Aggregate 振る舞い → archived 終端 等）。
        """
        length = len(self.prefix_markdown)
        if length > PROMPT_KIT_PREFIX_MAX:
            raise ValueError(
                f"[FAIL] PromptKit.prefix_markdown must be 0-{PROMPT_KIT_PREFIX_MAX} "
                f"characters (got {length})\n"
                f"Next: Trim PromptKit content to <={PROMPT_KIT_PREFIX_MAX} "
                f"NFC-normalized characters; for richer prompts use Phase 2 "
                f"sections (variables / role_specific_prefix / sections)."
            )
        return self


class RoomRoleOverride(BaseModel):
    """Room スコープのロール別 DeliverableTemplate オーバーライド VO。

    (room_id, role) をキーとして、Room 内でこの Role が提供する
    DeliverableTemplate refs を上書き定義する。空タプルは「このロールは
    Room 内でテンプレを提供しない」の明示的宣言として有効。

    不変条件: deliverable_template_refs 内の template_id は一意でなければならない。
    重複がある場合はコンストラクタ内で RoomRoleOverrideInvariantViolation を raise する。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    room_id: RoomId
    role: Role
    deliverable_template_refs: tuple[DeliverableTemplateRef, ...] = ()

    @model_validator(mode="after")
    def _check_template_id_unique(self) -> Self:
        seen: set[object] = set()
        for ref in self.deliverable_template_refs:
            if ref.template_id in seen:
                raise RoomRoleOverrideInvariantViolation(
                    kind="duplicate_template_id",
                    message=(
                        f"[FAIL] RoomRoleOverride template_id must be unique: "
                        f"duplicate {ref.template_id!r}\n"
                        f"Next: Remove duplicate template_id from deliverable_template_refs."
                    ),
                    detail={"template_id": str(ref.template_id)},
                )
            seen.add(ref.template_id)
        return self


__all__ = [
    "PROMPT_KIT_PREFIX_MAX",
    "AgentMembership",
    "PromptKit",
    "RoomRoleOverride",
]
