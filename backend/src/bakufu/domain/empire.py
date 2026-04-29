"""Empire 集約ルート。

``docs/features/empire`` に従って ``REQ-EM-001``〜``REQ-EM-005`` を実装する。

設計契約（設計レビューを再実施しない限り変更不可）:

* **事前検証付き再構築（確定 A）** — 状態を変更するすべての振る舞いは
  ``model_dump()`` で現在の状態をシリアライズし、対象リストを差し替え、
  ``Empire.model_validate(...)`` を再実行することで *候補* 集約に対して
  ``model_validator(mode='after')`` を発火させる。失敗時は新インスタンスが
  観測可能になる *前* に :class:`EmpireInvariantViolation` を送出し、
  元の集約は厳密に変更されないままにする。``model_copy(update=...)`` は
  Pydantic v2 がデフォルトで ``validate=False`` とするため意図的に避ける。
* **NFC 正規化パイプライン（確定 B）** — ``raw → NFC → strip → len``。
  クリーニング後の形式が永続化され、``MSG-EM-001`` の ``{length}`` も
  この形式の長さを報告する。
* **容量制約（確定 C）** — ``len(rooms) ≤ 100`` かつ ``len(agents) ≤ 100``。
* **線形探索（確定 D）** — ``archive_room`` は補助インデックス dict を
  保持せず ``rooms`` を線形に走査する。``N ≤ 100`` のためコストは無視でき、
  状態の二重管理によるバグを避ける。
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.exceptions import EmpireInvariantViolation
from bakufu.domain.value_objects import (
    AgentRef,
    EmpireId,
    RoomId,
    RoomRef,
    nfc_strip,
)

# 詳細設計 §確定 C の容量上限。テスト・ファクトリコードが同じ
# 真実の源を import できるようモジュールレベル定数とする。
MAX_ROOMS: int = 100
MAX_AGENTS: int = 100

# 詳細設計 §確定 B の Empire.name 長さ範囲。
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80


class Empire(BaseModel):
    """Room と Agent への参照を保持するルート集約。

    状態を変更するメソッド（:meth:`hire_agent` / :meth:`establish_room` /
    :meth:`archive_room`）は *新しい* :class:`Empire` インスタンスを返す。
    この集約は frozen であり、呼び出し側は自身の参照を差し替える。
    Pydantic v2 の ``frozen=True`` により言語レベルでインプレース変更が
    不可能となるため、並行呼び出し側が部分更新中の集約を観測できない。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: EmpireId
    name: str
    archived: bool = False
    # Pydantic v2 はインスタンスごとにこれらのデフォルトをディープコピーするため、
    # 空リストリテラルは安全かつ pyright フレンドリー
    # （`default_factory=list` の Unknown が出ない）。
    rooms: list[RoomRef] = []
    agents: list[AgentRef] = []

    # ------------------------------------------------------------------
    # 事前検証フック
    # ------------------------------------------------------------------
    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        """確定 B のパイプラインを ``len`` 直前まで適用する。

        Empire / Room / Agent / Workflow が **単一の** NFC+strip 実装を共有する
        ため :func:`nfc_strip` に委譲する（DRY）。長さ・範囲判定は意図的に
        :meth:`_check_invariants` に残し、結果として汎用的な Pydantic
        ``ValidationError`` ではなく構造化された ``kind='name_range'`` を持つ
        :class:`EmpireInvariantViolation` を返せるようにしている。
        """
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """候補インスタンスに対して集約レベルの不変条件を全て実行する。

        ここで送出される独自例外（``ValueError`` 以外）は ``ValidationError``
        にラップされず呼び出し側へ伝搬する — これは Pydantic v2 の
        ``mode='after'`` バリデータの仕様として明記されている挙動。
        """
        self._check_name_range()
        self._check_capacity()
        self._check_no_duplicates()
        return self

    # ------------------------------------------------------------------
    # 不変条件チェック（SRP / 可読性のため分割）
    # ------------------------------------------------------------------
    def _check_name_range(self) -> None:
        length = len(self.name)
        if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
            raise EmpireInvariantViolation(
                kind="name_range",
                message=(
                    f"[FAIL] Empire name must be "
                    f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters "
                    f"(got {length})"
                ),
                detail={"length": length},
            )

    def _check_capacity(self) -> None:
        agents_count = len(self.agents)
        if agents_count > MAX_AGENTS:
            raise EmpireInvariantViolation(
                kind="capacity_exceeded",
                message=(
                    f"[FAIL] Empire invariant violation: "
                    f"agents capacity {MAX_AGENTS} exceeded (got {agents_count})"
                ),
                detail={"agents_count": agents_count, "max_agents": MAX_AGENTS},
            )
        rooms_count = len(self.rooms)
        if rooms_count > MAX_ROOMS:
            raise EmpireInvariantViolation(
                kind="capacity_exceeded",
                message=(
                    f"[FAIL] Empire invariant violation: "
                    f"rooms capacity {MAX_ROOMS} exceeded (got {rooms_count})"
                ),
                detail={"rooms_count": rooms_count, "max_rooms": MAX_ROOMS},
            )

    def _check_no_duplicates(self) -> None:
        seen_agents: set[Any] = set()
        for agent in self.agents:
            if agent.agent_id in seen_agents:
                raise EmpireInvariantViolation(
                    kind="agent_duplicate",
                    message=f"[FAIL] Agent already hired: agent_id={agent.agent_id}",
                    detail={"agent_id": str(agent.agent_id)},
                )
            seen_agents.add(agent.agent_id)

        seen_rooms: set[Any] = set()
        for room in self.rooms:
            if room.room_id in seen_rooms:
                raise EmpireInvariantViolation(
                    kind="room_duplicate",
                    message=f"[FAIL] Room already established: room_id={room.room_id}",
                    detail={"room_id": str(room.room_id)},
                )
            seen_rooms.add(room.room_id)

    # ------------------------------------------------------------------
    # 振る舞い（Tell, Don't Ask）
    # ------------------------------------------------------------------
    def hire_agent(self, agent_ref: AgentRef) -> Empire:
        """``agents`` に ``agent_ref`` を追加した新しい :class:`Empire` を返す。

        Raises:
            EmpireInvariantViolation: ``agent_ref.agent_id`` が既存の
                Agent と重複する場合（``kind='agent_duplicate'``）、または
                追加後の件数が :data:`MAX_AGENTS` を超える場合
                （``kind='capacity_exceeded'``）。元の集約は変更されない。
        """
        return self._rebuild_with(agents=[*self.agents, agent_ref])

    def establish_room(self, room_ref: RoomRef) -> Empire:
        """``rooms`` に ``room_ref`` を追加した新しい :class:`Empire` を返す。

        Raises:
            EmpireInvariantViolation: ``room_id`` 重複または容量超過時。
                元の集約は変更されない。
        """
        return self._rebuild_with(rooms=[*self.rooms, room_ref])

    def archive_room(self, room_id: RoomId) -> Empire:
        """該当 Room を archived 化した新しい :class:`Empire` を返す。

        Room は *物理削除* されない — bakufu の監査証跡は過去の ``room_id``
        参照を解決できる必要があるため（詳細設計 §"なぜ archive_room は
        物理削除しないか"）。アーカイブ済み Room の再アーカイブは冪等であり、
        結果の Room 状態は同一になる。

        Raises:
            EmpireInvariantViolation: 該当 Room が存在しない場合
                （``kind='room_not_found'``）。
        """
        for index, room in enumerate(self.rooms):
            if room.room_id == room_id:
                archived_ref = room.model_copy(update={"archived": True})
                new_rooms = [*self.rooms[:index], archived_ref, *self.rooms[index + 1 :]]
                return self._rebuild_with(rooms=new_rooms)
        raise EmpireInvariantViolation(
            kind="room_not_found",
            message=f"[FAIL] Room not found in Empire: room_id={room_id}",
            detail={"room_id": str(room_id)},
        )

    def archive(self) -> Empire:
        """``archived=True`` を持つ新しい :class:`Empire` を返す。

        論理削除（UC-EM-010 / 確定 H）を実装する。新しい frozen インスタンスを
        返すので、呼び出し側はその結果を ``EmpireRepository.save(archived_empire)``
        に渡し、Unit-of-Work 内部で状態変更を永続化する。
        """
        return Empire.model_validate(self.model_dump() | {"archived": True})

    # ------------------------------------------------------------------
    # 内部: 事前検証付き再構築（確定 A）
    # ------------------------------------------------------------------
    def _rebuild_with(
        self,
        *,
        rooms: list[RoomRef] | None = None,
        agents: list[AgentRef] | None = None,
    ) -> Empire:
        """``model_validate`` で再構築し、``model_validator`` を再発火させる。

        候補 dict は ``model_dump()`` から組み立てる（完全にプリミティブな構造を
        生成する）ため、差し替えたリストは同質になる: 検証中に Pydantic が
        dict を ``RoomRef`` / ``AgentRef`` インスタンスへ再強制し、
        Empire 初期構築時と同じ形になる。
        """
        state = self.model_dump()
        if rooms is not None:
            state["rooms"] = [room.model_dump() for room in rooms]
        if agents is not None:
            state["agents"] = [agent.model_dump() for agent in agents]
        return Empire.model_validate(state)


__all__ = [
    "MAX_AGENTS",
    "MAX_NAME_LENGTH",
    "MAX_ROOMS",
    "MIN_NAME_LENGTH",
    "Empire",
]
