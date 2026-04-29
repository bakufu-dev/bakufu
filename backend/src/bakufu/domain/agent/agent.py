"""Agent Aggregate Root（REQ-AG-001〜006）。

``docs/features/agent`` に従って実装する。Aggregate は
:mod:`bakufu.domain.agent.aggregate_validators` の 5 つのヘルパへディスパッチし、
SkillRef.path のトラバーサル防御（H1〜H10）は
:mod:`bakufu.domain.agent.path_validators` に委譲する。

設計コントラクト:

* **Pre-validate rebuild（Confirmation A）** — ``set_default_provider`` /
  ``add_skill`` / ``remove_skill`` / ``archive`` はすべて :meth:`Agent._rebuild_with`
  （``model_dump → swap → model_validate``）を経由する。
* **NFC パイプライン（Confirmation E）** — ``Agent.name`` は empire / workflow の
  ``nfc_strip`` ヘルパを再利用する。長さ判定はモデル バリデータで行うため、結果の
  :class:`AgentInvariantViolation` は MSG-AG-001 文言の ``kind='name_range'`` を持つ。
* **archive 冪等性（Confirmation D）** — ``archive()`` は常に *新* インスタンスを
  返す。冪等性とは「結果状態が一致する」ことであり「オブジェクト同一性」ではない。
  Pydantic v2 frozen + ``model_validate`` 再構築がこれを構造的に保証する。docstring
  とテストでコントラクトを文書化し、利用者が ``is`` 比較に依存しないようにする。
* **provider_kind MVP ゲート（Confirmation I）** — Aggregate には *実装しない*。
  ``AgentService.hire()``（Phase-2 アプリケーション サービス）が責任を持つ。
  Aggregate は enum 値が適切に整形されていることを信頼し、Adapter の存在判定は
  サービスに委ねる。
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.agent.aggregate_validators import (
    _validate_default_provider_count,
    _validate_provider_capacity,
    _validate_provider_kind_unique,
    _validate_skill_capacity,
    _validate_skill_id_unique,
)
from bakufu.domain.agent.value_objects import (
    Persona,
    ProviderConfig,
    SkillRef,
)
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import (
    AgentId,
    EmpireId,
    ProviderKind,
    Role,
    SkillId,
    nfc_strip,
)

# Confirmation E: 名前長境界（NFC + strip 後で 1〜40）。
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 40


class Agent(BaseModel):
    """:class:`Empire` が所有する雇用可能な LLM エージェント。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: AgentId
    # ``empire_id`` は ``feature/agent-repository``（Issue #32）が要求する逆参照。
    # リポジトリは Empire の下に Agent を永続化するため、テーブル レベルの FK
    # ``agents.empire_id REFERENCES empires.id ON DELETE CASCADE`` が値を取得できる
    # 場所が必要であり、``find_by_name`` も ``WHERE empire_id = :empire_id`` で
    # ルックアップをスコープできる — detailed-design §確定 F。
    empire_id: EmpireId
    name: str
    persona: Persona
    role: Role
    providers: list[ProviderConfig]
    skills: list[SkillRef] = []
    archived: bool = False

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Aggregate レベルのヘルパを決定的順序でディスパッチする。

        順序: name range → provider capacity / 一意性 / default 個数 →
        skill capacity / 一意性。先行する失敗が後続を隠すため、エラー メッセージは
        根本原因に集中する。
        """
        self._check_name_range()
        _validate_provider_capacity(self.providers)
        _validate_provider_kind_unique(self.providers)
        _validate_default_provider_count(self.providers)
        _validate_skill_capacity(self.skills)
        _validate_skill_id_unique(self.skills)
        return self

    def _check_name_range(self) -> None:
        length = len(self.name)
        if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
            raise AgentInvariantViolation(
                kind="name_range",
                message=(
                    f"[FAIL] Agent name must be "
                    f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters "
                    f"(got {length})"
                ),
                detail={"length": length},
            )

    # ---- 振る舞い（Tell, Don't Ask） -----------------------------------
    def set_default_provider(self, provider_kind: ProviderKind) -> Agent:
        """``provider_kind`` が一致するエントリにデフォルト プロバイダを切り替える。

        ``providers`` を線形スキャンする（N ≤ 10 で小さい）。kind が未登録の場合
        例外を送出する — 呼び元は構成されていない provider をデフォルトにできない。

        Raises:
            AgentInvariantViolation: ``provider_kind`` に一致する
                ``ProviderConfig`` がないとき ``kind='provider_not_found'``。
        """
        if not any(provider.provider_kind == provider_kind for provider in self.providers):
            raise AgentInvariantViolation(
                kind="provider_not_found",
                message=f"[FAIL] provider_kind not registered: {provider_kind}",
                detail={"provider_kind": str(provider_kind)},
            )
        new_providers = [
            ProviderConfig(
                provider_kind=provider.provider_kind,
                model=provider.model,
                is_default=(provider.provider_kind == provider_kind),
            )
            for provider in self.providers
        ]
        return self._rebuild_with(providers=new_providers)

    def add_skill(self, skill_ref: SkillRef) -> Agent:
        """``skill_ref`` を ``skills`` に追加する。重複は Aggregate 検証で捕捉される。"""
        return self._rebuild_with(skills=[*self.skills, skill_ref])

    def remove_skill(self, skill_id: SkillId) -> Agent:
        """``skill_id`` が一致する SkillRef を削除する。

        Raises:
            AgentInvariantViolation: ``kind='skill_not_found'``（MSG-AG-008）。
        """
        if not any(skill.skill_id == skill_id for skill in self.skills):
            raise AgentInvariantViolation(
                kind="skill_not_found",
                message=f"[FAIL] Skill not found in agent: skill_id={skill_id}",
                detail={"skill_id": str(skill_id)},
            )
        return self._rebuild_with(
            skills=[skill for skill in self.skills if skill.skill_id != skill_id],
        )

    def archive(self) -> Agent:
        """``archived=True`` を持つ新しい :class:`Agent` を返す（Confirmation D）。

        冪等: 既にアーカイブ済みの Agent に対して呼んでも、入力と **構造的に等しく**、
        ``id()`` のみ異なる新規 Agent を生成する。呼び元はオブジェクト同一性に依存
        してはならず、常に返値を代入し直すこと（``agent = agent.archive()``）。
        """
        return self._rebuild_with_state({"archived": True})

    # ---- 内部実装: 事前検証 rebuild（Confirmation A） -------------------
    def _rebuild_with(
        self,
        *,
        providers: list[ProviderConfig] | None = None,
        skills: list[SkillRef] | None = None,
    ) -> Agent:
        """``model_validate`` で再構築し ``_check_invariants`` を再発火させる。"""
        state = self.model_dump()
        if providers is not None:
            state["providers"] = [provider.model_dump() for provider in providers]
        if skills is not None:
            state["skills"] = [skill.model_dump() for skill in skills]
        return Agent.model_validate(state)

    def _rebuild_with_state(self, updates: dict[str, Any]) -> Agent:
        """スカラ属性更新（例 ``archived``）のための pre-validate rebuild。"""
        state = self.model_dump()
        state.update(updates)
        return Agent.model_validate(state)


__all__ = [
    "MAX_NAME_LENGTH",
    "MIN_NAME_LENGTH",
    "Agent",
]
