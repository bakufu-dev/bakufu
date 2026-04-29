"""Agent HTTP API Pydantic スキーマ（§確定 A）。

Q-3: domain / infrastructure への import はゼロ。
duck typing で domain オブジェクトを変換する。
field_serializer は GET / POST / PATCH 全パスで発火し、prompt_body を masking する
（§確定 A-masking / R1-9）。
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bakufu.application.security.masking import ApplicationMasking

# ---------------------------------------------------------------------------
# 有効値定数（domain import なし — Q-3 interfaces→domain 直接依存禁止）
# ---------------------------------------------------------------------------
_VALID_PROVIDER_KINDS: frozenset[str] = frozenset(
    {"CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE", "KIMI", "COPILOT"}
)
_VALID_ROLES: frozenset[str] = frozenset(
    {
        "LEADER",
        "DEVELOPER",
        "TESTER",
        "REVIEWER",
        "UX",
        "SECURITY",
        "ASSISTANT",
        "DISCUSSANT",
        "WRITER",
        "SITE_ADMIN",
    }
)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PersonaCreate(BaseModel):
    """Persona 作成リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=40)
    archetype: str | None = Field(default=None, max_length=80)
    prompt_body: str | None = Field(default=None, max_length=10000)


class ProviderConfigCreate(BaseModel):
    """ProviderConfig 作成リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    provider_kind: str
    model: str = Field(min_length=1, max_length=80)
    is_default: bool

    @field_validator("provider_kind", mode="before")
    @classmethod
    def _validate_provider_kind(cls, value: object) -> object:
        if isinstance(value, str) and value not in _VALID_PROVIDER_KINDS:
            raise ValueError(
                f"provider_kind must be one of {sorted(_VALID_PROVIDER_KINDS)!r}, got {value!r}"
            )
        return value


class SkillRefCreate(BaseModel):
    """SkillRef 作成リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: str  # UUID 文字列として受け取り domain に委譲
    name: str = Field(min_length=1, max_length=80)
    path: str = Field(min_length=1, max_length=500)


class AgentCreate(BaseModel):
    """POST /api/empires/{empire_id}/agents リクエスト Body（§確定 A）。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    persona: PersonaCreate
    role: str
    providers: list[ProviderConfigCreate] = Field(min_length=1)
    skills: list[SkillRefCreate] = []

    @field_validator("role", mode="before")
    @classmethod
    def _validate_role(cls, value: object) -> object:
        if isinstance(value, str) and value not in _VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(_VALID_ROLES)!r}, got {value!r}")
        return value


class PersonaUpdate(BaseModel):
    """Persona 更新リクエスト要素（部分更新可、全フィールド None も有効）。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    archetype: str | None = Field(default=None, max_length=80)
    prompt_body: str | None = Field(default=None, max_length=10000)


class AgentUpdate(BaseModel):
    """PATCH /api/agents/{id} リクエスト Body（§確定 A）。

    全フィールド None も有効（no-op PATCH、既存 Agent をそのまま返す）。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=40)
    persona: PersonaUpdate | None = None
    role: str | None = None
    providers: list[ProviderConfigCreate] | None = None
    skills: list[SkillRefCreate] | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _validate_role(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, str) and value not in _VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(_VALID_ROLES)!r}, got {value!r}")
        return value

    @field_validator("providers", mode="before")
    @classmethod
    def _validate_providers_min_length(cls, value: Any) -> Any:
        # isinstance 後の list[Unknown] 問題を回避するため早期 return + cast パターン
        if not isinstance(value, list):
            return value
        items: list[Any] = cast("list[Any]", value)
        if len(items) == 0:
            raise ValueError("providers must have at least 1 item when specified")
        out: Any = items
        return out


# ---------------------------------------------------------------------------
# Response sub-schemas
# ---------------------------------------------------------------------------


class PersonaResponse(BaseModel):
    """Persona レスポンス要素（§確定 A-masking）。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str
    archetype: str
    prompt_body: str

    @field_serializer("prompt_body")
    def _mask_prompt_body(self, value: str) -> str:
        """GET / POST / PATCH 全パスで発火し prompt_body を masking する（R1-9 独立防御）。

        冪等: DB 復元済みの masked 値（``<REDACTED:*>``）にも安全に再適用できる。
        import パスは ``bakufu.application.security.masking``（interfaces → application）。
        TC-UT-AGH-009 の ``bakufu.infrastructure`` 禁止制約を維持する（§確定 I）。
        """
        return ApplicationMasking.mask(value)

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain Persona → dict 変換（duck typing, domain import なし）。"""
        if not hasattr(data, "display_name"):
            return data
        return {
            "display_name": data.display_name,
            "archetype": data.archetype,
            "prompt_body": data.prompt_body,
        }


class ProviderConfigResponse(BaseModel):
    """ProviderConfig レスポンス要素。"""

    model_config = ConfigDict(extra="forbid")

    provider_kind: str
    model: str
    is_default: bool

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain ProviderConfig → dict 変換（duck typing, domain import なし）。"""
        if not hasattr(data, "provider_kind"):
            return data
        return {
            "provider_kind": str(data.provider_kind),
            "model": data.model,
            "is_default": data.is_default,
        }


class SkillRefResponse(BaseModel):
    """SkillRef レスポンス要素。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    name: str
    path: str

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain SkillRef → dict 変換（duck typing, domain import なし）。"""
        if not hasattr(data, "skill_id"):
            return data
        return {
            "skill_id": str(data.skill_id),
            "name": data.name,
            "path": data.path,
        }


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AgentResponse(BaseModel):
    """Agent 単件レスポンス。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    empire_id: str
    name: str
    persona: PersonaResponse
    role: str
    providers: list[ProviderConfigResponse]
    skills: list[SkillRefResponse]
    archived: bool

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain Agent → dict 変換（duck typing, domain import なし）。"""
        if hasattr(data, "persona"):
            return {
                "id": str(data.id),
                "empire_id": str(data.empire_id),
                "name": data.name,
                "persona": data.persona,
                "role": str(data.role),
                "providers": list(data.providers),
                "skills": list(data.skills),
                "archived": data.archived,
            }
        return data


class AgentListResponse(BaseModel):
    """Agent 一覧レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[AgentResponse]
    total: int


__all__ = [
    "AgentCreate",
    "AgentListResponse",
    "AgentResponse",
    "AgentUpdate",
    "PersonaCreate",
    "PersonaResponse",
    "PersonaUpdate",
    "ProviderConfigCreate",
    "ProviderConfigResponse",
    "SkillRefCreate",
    "SkillRefResponse",
]
