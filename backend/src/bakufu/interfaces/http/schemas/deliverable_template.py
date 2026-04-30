"""DeliverableTemplate HTTP API Pydantic スキーマ。

リクエスト / レスポンスモデルを定義する。全スキーマに
``ConfigDict(extra="forbid")`` を適用し余分なフィールドを拒否する。

レスポンス系スキーマは ``from_attributes=True`` + ``field_validator(mode='before')``
で domain オブジェクトから直接変換する。UUID → str / StrEnum → str の変換は
schema 側 validator が責任を持つため、router が domain 層の型を知る必要はない。

§確定 I: ``schema`` フィールドに ``# type: ignore[override]`` を付与する。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SemVerCreate(BaseModel):
    """SemVer リクエスト用スキーマ（major / minor / patch）。"""

    model_config = ConfigDict(extra="forbid")

    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int = Field(ge=0)


class SemVerResponse(BaseModel):
    """SemVer レスポンス用スキーマ（major / minor / patch）。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    major: int
    minor: int
    patch: int


class AcceptanceCriterionCreate(BaseModel):
    """POST / PUT 受入基準リクエスト要素。

    ``id`` は省略時に uuid4() を自動生成する（§確定 H）。
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    description: str = Field(min_length=1, max_length=500)
    required: bool = True


class AcceptanceCriterionResponse(BaseModel):
    """受入基準レスポンス要素。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    description: str
    required: bool

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``AcceptanceCriterion.id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value


class DeliverableTemplateRefCreate(BaseModel):
    """DeliverableTemplateRef リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    template_id: UUID
    minimum_version: SemVerCreate


class DeliverableTemplateRefResponse(BaseModel):
    """DeliverableTemplateRef レスポンス要素。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    template_id: str
    minimum_version: SemVerResponse

    @field_validator("template_id", mode="before")
    @classmethod
    def _coerce_template_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``DeliverableTemplateRef.template_id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value


class DeliverableTemplateCreate(BaseModel):
    """POST /api/deliverable-templates リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", min_length=0, max_length=500)
    type: str
    schema: dict[str, object] | str  # type: ignore[override]
    acceptance_criteria: list[AcceptanceCriterionCreate] = Field(  # pyright: ignore[reportUnknownVariableType]
        default_factory=list
    )
    version: SemVerCreate = Field(default_factory=lambda: SemVerCreate(major=0, minor=1, patch=0))
    composition: list[DeliverableTemplateRefCreate] = Field(  # pyright: ignore[reportUnknownVariableType]
        default_factory=list
    )


class DeliverableTemplateUpdate(BaseModel):
    """PUT /api/deliverable-templates/{template_id} リクエスト Body。

    全フィールド必須（§確定 B: version 省略不可）。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=0, max_length=500)
    type: str
    schema: dict[str, object] | str  # type: ignore[override]
    acceptance_criteria: list[AcceptanceCriterionCreate]
    version: SemVerCreate
    composition: list[DeliverableTemplateRefCreate]


class DeliverableTemplateResponse(BaseModel):
    """DeliverableTemplate 単件レスポンス（201 / 200）。

    ``from_attributes=True`` で domain ``DeliverableTemplate`` から
    ``model_validate(template, from_attributes=True)`` で直接変換する。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    description: str
    type: str
    schema: dict[str, object] | str  # type: ignore[override]
    acceptance_criteria: list[AcceptanceCriterionResponse]
    version: SemVerResponse
    composition: list[DeliverableTemplateRefResponse]

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``DeliverableTemplate.id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, value: object) -> object:
        """StrEnum → str 変換。domain の ``DeliverableTemplate.type`` は ``TemplateType``。"""
        if isinstance(value, str):
            return value
        return str(value)


class DeliverableTemplateListResponse(BaseModel):
    """GET /api/deliverable-templates レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[DeliverableTemplateResponse]
    total: int


__all__ = [
    "AcceptanceCriterionCreate",
    "AcceptanceCriterionResponse",
    "DeliverableTemplateCreate",
    "DeliverableTemplateListResponse",
    "DeliverableTemplateRefCreate",
    "DeliverableTemplateRefResponse",
    "DeliverableTemplateResponse",
    "DeliverableTemplateUpdate",
    "SemVerCreate",
    "SemVerResponse",
]
