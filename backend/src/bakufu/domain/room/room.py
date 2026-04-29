"""Room Aggregate Root（REQ-RM-001〜006）。

``docs/features/room`` に従って実装する。Aggregate は
:mod:`bakufu.domain.room.aggregate_validators` の 4 つのヘルパへディスパッチし、
:mod:`bakufu.domain.room.value_objects` から :class:`AgentMembership` と
:class:`PromptKit` の VO を組み合わせる。

設計コントラクト:

* **Pre-validate rebuild（Confirmation A）** — ``add_member`` /
  ``remove_member`` / ``update_prompt_kit`` / ``archive`` はすべて
  :meth:`Room._rebuild_with`（``model_dump → swap → model_validate``）を経由する。
* **NFC パイプライン（Confirmation B）** — ``Room.name`` と ``Room.description`` は
  empire / workflow / agent の ``nfc_strip`` ヘルパを再利用する。長さ判定は
  Aggregate バリデータで行うため、結果の :class:`RoomInvariantViolation` は
  MSG-RM-001 / 002 の文言で ``kind='name_range'`` / ``'description_too_long'``
  を持つ。
* **archive 冪等性（Confirmation D）** — ``archive()`` は常に *新* インスタンスを
  返す。冪等性とは「結果状態が一致する」ことであり「オブジェクト同一性」ではない。
  Pydantic v2 frozen + ``model_validate`` 再構築がこれを保証する。docstring が
  コントラクトを文書化するため、呼び元は ``is`` 比較に依存しない。
* **archived 終端（Confirmation E）** — ``add_member`` / ``remove_member`` /
  ``update_prompt_kit`` は archived な Room に対して ``kind='room_archived'``
  （MSG-RM-006）で Fail Fast する。``archive()`` 自体は冪等でこのチェックをバイパス
  する。
* **`(agent_id, role)` 対の一意性（Confirmation F）** — 同じエージェントが複数の
  ロールを持てる。バリデータは対をキーとして使う。
* **アプリケーション層の責務** — Workflow 存在、Agent 存在、Workflow 要求の leader、
  Empire スコープ名一意性は ``RoomService`` / ``EmpireService`` に置く。Aggregate
  はローカルに観測できる範囲のみを信頼する。
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room.aggregate_validators import (
    _validate_description_length,
    _validate_member_capacity,
    _validate_member_unique,
    _validate_name_range,
)
from bakufu.domain.room.value_objects import AgentMembership, PromptKit
from bakufu.domain.value_objects import (
    AgentId,
    Role,
    RoomId,
    WorkflowId,
    nfc_strip,
)


class Room(BaseModel):
    """:class:`Empire` 内の編集可能な構成スペース（REQ-RM-001）。

    固定の :class:`WorkflowId` 上で :class:`PromptKit` プリアンブルと
    ``list[AgentMembership]`` を構成する。Aggregate は構造的不変条件のみを強制する
    — Workflow 存在および Workflow 要求 leader チェックは外部知識を要するため
    アプリケーション層の責務。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: RoomId
    name: str
    description: str = ""
    workflow_id: WorkflowId
    members: list[AgentMembership] = []
    prompt_kit: PromptKit = PromptKit()
    archived: bool = False

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("name", "description", mode="before")
    @classmethod
    def _normalize_short_text(cls, value: object) -> object:
        # empire / workflow / agent と共有する NFC + strip パイプライン
        # （Confirmation B）。
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Aggregate レベル ヘルパを決定的順序でディスパッチする。

        順序: name range → description length → member 一意性 → member 容量。
        先行する失敗が後続を隠すため、エラー メッセージは根本原因に集中する。
        """
        _validate_name_range(self.name)
        _validate_description_length(self.description)
        _validate_member_unique(self.members)
        _validate_member_capacity(self.members)
        return self

    # ---- 振る舞い（Tell, Don't Ask） -----------------------------------
    def add_member(self, membership: AgentMembership) -> Room:
        """``membership`` を ``members`` に追加。重複は Aggregate 検証で捕捉される。

        archived な Room には Fail Fast（Confirmation E）。
        ``(agent_id, role)`` 対の一意性チェックは rebuild 後の
        :meth:`_check_invariants` 内部で発火する。

        Raises:
            RoomInvariantViolation: 既にアーカイブ済みの場合
                ``kind='room_archived'``（MSG-RM-006）。対が既存の場合
                ``kind='member_duplicate'``（MSG-RM-003）。追加で件数が
                :data:`MAX_MEMBERS` を超える場合 ``kind='capacity_exceeded'``
                （MSG-RM-004）。
        """
        self._reject_if_archived()
        return self._rebuild_with(members=[*self.members, membership])

    def remove_member(self, agent_id: AgentId, role: Role) -> Room:
        """``(agent_id, role)`` に一致するメンバーシップを削除する。

        archived な Room には Fail Fast（Confirmation E）。対が見つからない場合も
        Fail Fast（MSG-RM-005） — 呼び元は現在のメンバ リストを観測せずに削除を盲目
        的に再試行できない。

        Raises:
            RoomInvariantViolation: ``kind='room_archived'``（MSG-RM-006）。対に
                一致するメンバーシップが無い場合 ``kind='member_not_found'``
                （MSG-RM-005）。
        """
        self._reject_if_archived()
        if not any(m.agent_id == agent_id and m.role == role for m in self.members):
            raise RoomInvariantViolation(
                kind="member_not_found",
                message=(
                    f"[FAIL] Member not found: agent_id={agent_id}, role={role.value}\n"
                    f"Next: Verify the (agent_id, role) pair via "
                    f"GET /rooms/{{room_id}}/members; the agent may have been "
                    f"already removed or never had this role."
                ),
                detail={"agent_id": str(agent_id), "role": role.value},
            )
        return self._rebuild_with(
            members=[m for m in self.members if not (m.agent_id == agent_id and m.role == role)],
        )

    def update_prompt_kit(self, prompt_kit: PromptKit) -> Room:
        """``prompt_kit`` を新しい ``prompt_kit`` に置き換える。

        archived な Room には Fail Fast（Confirmation E）。PromptKit の長さ違反は
        VO 構築時に :class:`pydantic.ValidationError` として表面化するため
        （Confirmation I の 2 段階キャッチ）、本メソッドが呼ばれる時点では VO は
        既に valid。

        Raises:
            RoomInvariantViolation: ``kind='room_archived'``（MSG-RM-006）。
        """
        self._reject_if_archived()
        return self._rebuild_with(prompt_kit=prompt_kit)

    def archive(self) -> Room:
        """``archived=True`` を持つ新しい :class:`Room` を返す（Confirmation D）。

        冪等: 既にアーカイブ済みの Room に対して呼んでも、入力と **構造的に等しく**、
        ``id()`` のみ異なる新規 Room を生成する。呼び元はオブジェクト同一性に依存
        してはならず、常に返値を代入し直すこと（``room = room.archive()``）。Norman
        が agent / empire の ``archive()`` 振る舞いで承認したのと同じコントラクト。
        """
        return self._rebuild_with_state({"archived": True})

    # ---- 内部実装 -------------------------------------------------------
    def _reject_if_archived(self) -> None:
        """Room が終端状態のとき ``room_archived``（MSG-RM-006）を送出する。

        Confirmation E: archived な Room は :meth:`archive` 自身を除く全ての変異
        振る舞いを拒否する。``archive`` は再試行耐性のため冪等のまま保たれる。
        """
        if self.archived:
            raise RoomInvariantViolation(
                kind="room_archived",
                message=(
                    f"[FAIL] Cannot modify archived Room: room_id={self.id}\n"
                    f"Next: Create a new Room; unarchive is not supported in "
                    f"MVP (Phase 2 will add RoomService.unarchive)."
                ),
                detail={"room_id": str(self.id)},
            )

    def _rebuild_with(
        self,
        *,
        members: list[AgentMembership] | None = None,
        prompt_kit: PromptKit | None = None,
    ) -> Room:
        """``model_validate`` で再構築し ``_check_invariants`` を再発火させる。"""
        state = self.model_dump()
        if members is not None:
            state["members"] = [m.model_dump() for m in members]
        if prompt_kit is not None:
            state["prompt_kit"] = prompt_kit.model_dump()
        return Room.model_validate(state)

    def _rebuild_with_state(self, updates: dict[str, Any]) -> Room:
        """スカラ属性更新（例 ``archived``）のための pre-validate rebuild。"""
        state = self.model_dump()
        state.update(updates)
        return Room.model_validate(state)


__all__ = [
    "Room",
]
