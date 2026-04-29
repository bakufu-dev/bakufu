"""Workflow Aggregate Root（REQ-WF-001〜006）。

本モジュールは :class:`Workflow` クラス自体のみを所有する。ディスパッチ対象の 10
個の不変条件ヘルパは :mod:`bakufu.domain.workflow.dag_validators` に、内部 Entity
は :mod:`bakufu.domain.workflow.entities` に置かれる。このディレクトリ分割は
Confirmation F twin-defense の *物理的* 根拠である: Aggregate レベル チェックは
そもそもファイルを共有しないため、Stage 自己検証とコードを共有できない。

設計コントラクト（再設計レビュー無しに破壊しないこと）:

* **Pre-validate rebuild（Confirmation A）** — 全ての状態変更ビヘイビアは
  ``model_dump()`` でシリアライズし、対象コレクションをスワップし、
  ``Workflow.model_validate(...)`` を再実行する。``model_copy(update=...)`` は
  Pydantic v2 がデフォルトで ``validate=False`` とするため意図的に避ける。
* **NotifyChannel SSRF / トークン マスキング（Confirmation G）** —
  :class:`bakufu.domain.value_objects.NotifyChannel` 内部で処理される。本モジュール
  は検証済み VO を消費するだけで URL 形状は再チェックしない。
"""

from __future__ import annotations

from typing import Any, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import (
    StageInvariantViolation,
    WorkflowInvariantViolation,
)
from bakufu.domain.value_objects import StageId, WorkflowId, nfc_strip
from bakufu.domain.workflow.dag_validators import (
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    _validate_capacity,
    _validate_dag_reachability,
    _validate_dag_sink_exists,
    _validate_entry_in_stages,
    _validate_external_review_notify,
    _validate_required_role_non_empty,
    _validate_stage_id_unique,
    _validate_transition_determinism,
    _validate_transition_id_unique,
    _validate_transition_refs,
)
from bakufu.domain.workflow.entities import Stage, Transition


class Workflow(BaseModel):
    """Stage と Transition で構成される V モデル オーケストレーション グラフ。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: WorkflowId
    name: str
    stages: list[Stage]
    transitions: list[Transition] = []
    entry_stage_id: StageId
    archived: bool = False

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Aggregate レベル ヘルパを決定的順序でディスパッチする。

        失敗箇所の特定のため順序が重要: capacity → 一意性 → 参照整合性 → 意味
        （notify / required_role） → グラフ トポロジ。先行する失敗が後続を隠す
        ため、エラー メッセージは *根本* 原因に集中する。Capacity は **最初**
        にあり、T2 DoS ペイロードが BFS に到達できないようにする。
        """
        self._check_name_range()
        _validate_capacity(self.stages, self.transitions)
        _validate_stage_id_unique(self.stages)
        _validate_transition_id_unique(self.transitions)
        _validate_entry_in_stages(self.stages, self.entry_stage_id)
        _validate_transition_refs(self.stages, self.transitions)
        _validate_transition_determinism(self.transitions)
        _validate_external_review_notify(self.stages)
        _validate_required_role_non_empty(self.stages)
        _validate_dag_reachability(self.stages, self.transitions, self.entry_stage_id)
        _validate_dag_sink_exists(self.stages, self.transitions, self.entry_stage_id)
        return self

    def _check_name_range(self) -> None:
        length = len(self.name)
        if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
            raise WorkflowInvariantViolation(
                kind="name_range",
                message=(
                    f"[FAIL] Workflow name must be "
                    f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters "
                    f"(got {length})"
                ),
                detail={"length": length},
            )

    # ---- 振る舞い（Tell, Don't Ask） -----------------------------------
    def add_stage(self, stage: Stage) -> Workflow:
        """``stage`` を追加した新しい Workflow を返す（REQ-WF-002）。"""
        return self._rebuild_with(stages=[*self.stages, stage])

    def add_transition(self, transition: Transition) -> Workflow:
        """``transition`` を追加した新しい Workflow を返す（REQ-WF-003）。"""
        return self._rebuild_with(transitions=[*self.transitions, transition])

    def remove_stage(self, stage_id: StageId) -> Workflow:
        """``stage_id`` とその接続エッジを除去した新しい Workflow を返す（REQ-WF-004）。

        Raises:
            WorkflowInvariantViolation:
                * entry stage を削除しようとした場合 ``kind='cannot_remove_entry'``
                  （MSG-WF-010）。
                * 一致する Stage が無い場合 ``kind='stage_not_found'``（MSG-WF-012）。
                * Aggregate 違反（例 ``unreachable_stage``）が rebuild から漏れる
                  場合 — 元の Workflow は変更されない。
        """
        if stage_id == self.entry_stage_id:
            raise WorkflowInvariantViolation(
                kind="cannot_remove_entry",
                message=f"[FAIL] Cannot remove entry stage: {stage_id}",
                detail={"stage_id": str(stage_id)},
            )
        if not any(stage.id == stage_id for stage in self.stages):
            raise WorkflowInvariantViolation(
                kind="stage_not_found",
                message=f"[FAIL] Stage not found in workflow: stage_id={stage_id}",
                detail={"stage_id": str(stage_id)},
            )
        new_stages = [stage for stage in self.stages if stage.id != stage_id]
        new_transitions = [
            transition
            for transition in self.transitions
            if transition.from_stage_id != stage_id and transition.to_stage_id != stage_id
        ]
        return self._rebuild_with(stages=new_stages, transitions=new_transitions)

    @classmethod
    def from_dict(cls, payload: object) -> Workflow:
        """一括 import ファクトリ（REQ-WF-006）。

        ``object`` を受け取るので、dict 以外を渡した呼び元も Pydantic の混乱した
        低レベル エラーでクラッシュさせる代わりに、構造化された
        ``WorkflowInvariantViolation`` 経路に到達できる。

        Pydantic ``ValidationError``（型、UUID、欠落フィールド、NotifyChannel URL
        の G1〜G10 アローリスト、MVP ``kind`` 制約）はそのまま伝播するため、呼び元
        は loc / error 構造を内省できる。

        ``StageInvariantViolation`` は ``detail`` に該当 stage index を添付して
        ``WorkflowInvariantViolation(kind='from_dict_invalid')`` にラップする —
        設計ドキュメント「なぜ from_dict はクラスメソッドか」節の TC-UT-WF-027
        デバッグ追跡コントラクトを満たす。
        """
        if not isinstance(payload, dict):
            raise WorkflowInvariantViolation(
                kind="from_dict_invalid",
                message=(
                    f"[FAIL] from_dict payload invalid: "
                    f"payload must be dict, got {type(payload).__name__}"
                ),
                detail={"payload_type": type(payload).__name__},
            )
        payload_dict = cast("dict[str, Any]", payload)
        stages_payload = payload_dict.get("stages")
        if isinstance(stages_payload, list):
            stages_list = cast("list[Any]", stages_payload)
            for index, stage_payload in enumerate(stages_list):
                try:
                    Stage.model_validate(stage_payload)
                except StageInvariantViolation as exc:
                    detail: dict[str, object] = {
                        **exc.detail,
                        "stage_index": index,
                        "stage_violation_kind": exc.kind,
                    }
                    raise WorkflowInvariantViolation(
                        kind="from_dict_invalid",
                        message=f"[FAIL] from_dict payload invalid: {detail}",
                        detail=detail,
                    ) from exc
                except ValidationError:
                    # 呼び元が内省できるよう、cls.model_validate に完全な loc パス
                    # 込みの正準 Pydantic エラーを生成させる。
                    pass
        return cls.model_validate(payload_dict)

    def archive(self) -> Workflow:
        """``archived=True`` を持つ新しい :class:`Workflow` を返す（冪等）。"""
        state = self.model_dump()
        state["archived"] = True
        return Workflow.model_validate(state)

    # ---- 内部実装: 事前検証 rebuild（Confirmation A） -------------------
    def _rebuild_with(
        self,
        *,
        stages: list[Stage] | None = None,
        transitions: list[Transition] | None = None,
    ) -> Workflow:
        """``model_validate`` で再構築し ``_check_invariants`` を再発火させる。"""
        state = self.model_dump()
        if stages is not None:
            state["stages"] = [stage.model_dump() for stage in stages]
        if transitions is not None:
            state["transitions"] = [transition.model_dump() for transition in transitions]
        return Workflow.model_validate(state)


__all__ = ["Workflow"]
