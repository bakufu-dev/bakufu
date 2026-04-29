"""Agent 固有の Value Object（Persona / ProviderConfig / SkillRef）。

これらの VO はファイル レベル境界が責務境界を反映するよう、グローバルな
:mod:`bakufu.domain.value_objects` ではなく ``agent/`` パッケージに置く —
Norman が workflow パッケージで承認したのと同じパターン。``SkillId`` と
``ProviderKind`` はフィーチャー境界（Skill loader、LLM Adapter）を跨ぐため
グローバル モジュールに残す。

Persona / archetype / display_name のバリデーションは全て
:func:`bakufu.domain.value_objects.nfc_strip` パイプラインを共有する
（Confirmation B の共有ポリシーを empire / workflow から継承）。``prompt_body``
は NFC のみを適用する — Markdown の先頭／末尾改行は下流レンダラが依存するため
保持しなければならない（Confirmation E）。

``SkillRef.path`` は :mod:`bakufu.domain.agent.path_validators` の H1〜H10
完全トラバーサル防御パイプラインを実行する。
"""

from __future__ import annotations

import unicodedata
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bakufu.domain.agent.path_validators import _validate_skill_path
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind, SkillId, nfc_strip

# ---------------------------------------------------------------------------
# Persona（Agent feature §確定 E の長さポリシー）
# ---------------------------------------------------------------------------
DISPLAY_NAME_MIN: int = 1
DISPLAY_NAME_MAX: int = 40
ARCHETYPE_MAX: int = 80
PROMPT_BODY_MAX: int = 10_000


class Persona(BaseModel):
    """:class:`Agent` に紐づくキャラクタ／著作プロフィール。

    ``display_name`` と ``archetype`` は NFC + strip を通過する（Confirmation E）。
    ``prompt_body`` は NFC のみ — strip は下流のプロンプト レンダリングが依存する
    Markdown の先頭／末尾空白を食ってしまう。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    display_name: str
    archetype: str = ""
    prompt_body: str = ""

    @field_validator("display_name", "archetype", mode="before")
    @classmethod
    def _normalize_short_name(cls, value: object) -> object:
        return nfc_strip(value)

    @field_validator("prompt_body", mode="before")
    @classmethod
    def _normalize_prompt_body(cls, value: object) -> object:
        # NFC のみ — Markdown の先頭／末尾空白を保持する。
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_self_invariants(self) -> Self:
        display_name_len = len(self.display_name)
        if not (DISPLAY_NAME_MIN <= display_name_len <= DISPLAY_NAME_MAX):
            raise AgentInvariantViolation(
                kind="display_name_range",
                message=(
                    f"[FAIL] Persona.display_name must be "
                    f"{DISPLAY_NAME_MIN}-{DISPLAY_NAME_MAX} characters "
                    f"(got {display_name_len})"
                ),
                detail={"length": display_name_len},
            )
        archetype_len = len(self.archetype)
        if archetype_len > ARCHETYPE_MAX:
            raise AgentInvariantViolation(
                kind="archetype_too_long",
                message=(
                    f"[FAIL] Persona.archetype must be 0-{ARCHETYPE_MAX} characters "
                    f"(got {archetype_len})"
                ),
                detail={"length": archetype_len},
            )
        prompt_body_len = len(self.prompt_body)
        if prompt_body_len > PROMPT_BODY_MAX:
            raise AgentInvariantViolation(
                kind="persona_too_long",
                message=(
                    f"[FAIL] Persona.prompt_body must be 0-{PROMPT_BODY_MAX} "
                    f"characters (got {prompt_body_len})"
                ),
                detail={"length": prompt_body_len},
            )
        return self


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------
PROVIDER_MODEL_MIN: int = 1
PROVIDER_MODEL_MAX: int = 80


class ProviderConfig(BaseModel):
    """:class:`Agent` 内部の LLM プロバイダ構成エントリ。

    ``provider_kind`` enum により既知のプロバイダのみが通過する。「この provider の
    Adapter が MVP で実装済みか」のチェックは VO ではなくアプリケーション層
    （``AgentService.hire``）の責務である — 責務分離は Agent detailed-design §確定 I
    を参照。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    provider_kind: ProviderKind
    model: str = Field(min_length=PROVIDER_MODEL_MIN, max_length=PROVIDER_MODEL_MAX)
    is_default: bool = False

    @field_validator("model", mode="before")
    @classmethod
    def _strip_model(cls, value: object) -> object:
        # Confirmation E に従い strip のみ（NFC 無し） — モデル名は実運用上 ASCII
        # 識別子であり、NFC を適用しても動作上の効果はない。
        if isinstance(value, str):
            return value.strip()
        return value


# ---------------------------------------------------------------------------
# SkillRef（H1〜H10 のパス トラバーサル防御は path_validators に委譲）
# ---------------------------------------------------------------------------
SKILL_NAME_MIN: int = 1
SKILL_NAME_MAX: int = 80


class SkillRef(BaseModel):
    """``BAKUFU_DATA_DIR/skills/`` 内の Skill Markdown ファイルへの参照。

    パス検証コントラクトは包括的（10 個の独立したチェック）。完全な順序付きポリシー
    は :func:`bakufu.domain.agent.path_validators._validate_skill_path` を参照。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    skill_id: SkillId
    name: str = Field(min_length=SKILL_NAME_MIN, max_length=SKILL_NAME_MAX)
    path: str

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @field_validator("path", mode="after")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        # H1〜H10 を一度に実行。NFC 正規化された形を返し、保存値が正準形となる
        # （以降のコード経路は未正規化文字列を見ない）。
        return _validate_skill_path(value)


__all__ = [
    "ARCHETYPE_MAX",
    "DISPLAY_NAME_MAX",
    "DISPLAY_NAME_MIN",
    "PROMPT_BODY_MAX",
    "PROVIDER_MODEL_MAX",
    "PROVIDER_MODEL_MIN",
    "SKILL_NAME_MAX",
    "SKILL_NAME_MIN",
    "Persona",
    "ProviderConfig",
    "SkillRef",
]
