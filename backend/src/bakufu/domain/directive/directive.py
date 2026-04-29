"""Directive Aggregate Root（REQ-DR-001〜003）。

``docs/features/directive`` に従って実装する。Aggregate は意図的にスリム: 5 つの
属性、2 つの構造的不変条件、1 つの振る舞い。アプリケーション層の関心事
（``$`` プレフィックス正規化、``target_room_id`` 存在検証、Task 作成）は §確定 G / H
により ``DirectiveService.issue()`` に置く。

設計コントラクト:

* **Pre-validate rebuild（Confirmation A）** — :meth:`Directive.link_task` は
  :meth:`_rebuild_with_state`（``model_dump → swap → model_validate``）を経由する。
* **NFC のみの正規化（Confirmation B）** — ``Directive.text`` は ``strip`` *無し* で
  ``unicodedata.normalize('NFC', ...)`` を適用する。CEO ディレクティブには意味のある
  先頭／末尾空白や複数段落ブロックを含み得るため、Agent ``Persona.prompt_body`` /
  Room ``PromptKit.prefix_markdown`` の先例がここでも適用される。
* **task_id 遷移の一意性（Confirmation C / D）** — ``link_task`` 経路だけが遷移違反を
  監視する。コンストラクタ経路は任意の ``TaskId | None`` 値を受理する。これにより、
  既にリンク済みの Directive をリポジトリから水和する際に「rebuild」用の別経路を
  必要としない。
* **冪等性なし（Confirmation D）** — 2 回目の ``link_task`` は新 TaskId が既存と
  一致しても *常に* Fail Fast。ディレクティブの再発行とは新しい Directive の作成を
  意味する。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.directive.aggregate_validators import (
    _validate_text_range,
)
from bakufu.domain.value_objects import (
    DirectiveId,
    RoomId,
    TaskId,
)


class Directive(BaseModel):
    """対象 :class:`Room` に対して CEO が発行するディレクティブ（REQ-DR-001）。

    Aggregate は指示の *意図* を捉える: テキスト本文、委譲先の Room、発行時刻、
    リンクされた生成 Task（任意）。``DirectiveService``（アプリケーション層）が
    Task を作成し、:meth:`link_task` を呼び出して逆参照を確立する。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: DirectiveId
    text: str
    target_room_id: RoomId
    # ``created_at`` はアプリケーション層から tz-aware ``datetime`` として渡される
    # （Directive detailed-design §設計判断の補足「なぜ created_at を引数で受け取るか」
    # を参照）。下の post-validator が naive datetime を拒否するため、コントラクトは
    # 各呼び出し元ではなく Aggregate 境界で強制される。
    created_at: datetime
    task_id: TaskId | None = None

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        # Confirmation B: NFC のみ — ``strip`` 無し。CEO ディレクティブは先頭／末尾
        # 空白や改行に意味を持たせている可能性がある。
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("created_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        # naive datetime はタイムゾーン情報を持たず、SQLite を壁時計文字列として
        # サイレントに往復し、順序が壊れる。Aggregate 境界で Fail Fast する。
        if value.tzinfo is None:
            raise ValueError(
                "Directive.created_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """構造的不変条件チェックを実行する。

        Confirmation C: 構築時に走るのは ``_validate_text_range`` のみ。
        ``_validate_task_link_immutable`` は :meth:`link_task` 内部で強制される *遷移*
        を監視するもので、スナップショット値は対象としない。コンストラクタ経路は
        ``task_id`` が既に実値となっている Directive をリポジトリから水和する用途
        にも使われるため。
        """
        _validate_text_range(self.text)
        return self

    # ---- 振る舞い（Tell, Don't Ask） -----------------------------------
    def link_task(self, task_id: TaskId) -> Directive:
        """この Directive を ``task_id`` に紐づける。再リンクは拒否する。

        ``task_id`` が埋まった新しい :class:`Directive` インスタンスを返す。新インス
        タンスに対する次回呼び出しは常に Fail Fast — 「同じ TaskId だから OK」と
        いう冪等経路は存在しない（Confirmation D）。

        Raises:
            DirectiveInvariantViolation: この Directive が既に non-``None`` の
                ``task_id`` を持つ場合に ``kind='task_already_linked'``（MSG-DR-002）。
        """
        # ローカル import によりモジュール レベルの import グラフを最小に保つ —
        # バリデータは失敗経路でのみ意味を持つ。
        from bakufu.domain.directive.aggregate_validators import (
            _validate_task_link_immutable,
        )

        _validate_task_link_immutable(
            directive_id=self.id,
            existing_task_id=self.task_id,
            attempted_task_id=task_id,
        )
        return self._rebuild_with_state({"task_id": task_id})

    # ---- 内部実装 -------------------------------------------------------
    def _rebuild_with_state(self, updates: dict[str, Any]) -> Directive:
        """スカラ属性更新のための pre-validate rebuild。

        Confirmation A — :class:`bakufu.domain.agent.agent.Agent` および
        :class:`bakufu.domain.room.room.Room` と同じパターン。
        """
        state = self.model_dump()
        state.update(updates)
        return Directive.model_validate(state)


__all__ = [
    "Directive",
]
