"""Workflow HTTP API Pydantic スキーマ。

Q-3: domain / infrastructure への import はゼロ。
duck typing で domain オブジェクトを変換する。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# 有効値定数 (domain import なし — Q-3 interfaces→domain 直接依存禁止)
# ---------------------------------------------------------------------------
_VALID_STAGE_KINDS: frozenset[str] = frozenset({"WORK", "INTERNAL_REVIEW", "EXTERNAL_REVIEW"})
_VALID_TRANSITION_CONDITIONS: frozenset[str] = frozenset(
    {"APPROVED", "REJECTED", "CONDITIONAL", "TIMEOUT"}
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


class StageCreate(BaseModel):
    """Stage 作成リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str = Field(min_length=1, max_length=80)
    kind: str
    required_role: list[str] = Field(min_length=1)
    completion_policy: dict | None = None
    notify_channels: list[str] = []
    deliverable_template: str = ""

    @field_validator("kind", mode="before")
    @classmethod
    def _validate_kind(cls, value: object) -> object:
        if isinstance(value, str) and value not in _VALID_STAGE_KINDS:
            raise ValueError(
                f"kind must be one of {sorted(_VALID_STAGE_KINDS)!r}, got {value!r}"
            )
        return value

    @field_validator("required_role", mode="before")
    @classmethod
    def _validate_roles(cls, value: object) -> object:
        if isinstance(value, list):
            for role in value:
                if isinstance(role, str) and role not in _VALID_ROLES:
                    raise ValueError(
                        f"required_role element must be one of {sorted(_VALID_ROLES)!r},"
                        f" got {role!r}"
                    )
        return value


class TransitionCreate(BaseModel):
    """Transition 作成リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    from_stage_id: UUID
    to_stage_id: UUID
    condition: str
    label: str = ""

    @field_validator("condition", mode="before")
    @classmethod
    def _validate_condition(cls, value: object) -> object:
        if isinstance(value, str) and value not in _VALID_TRANSITION_CONDITIONS:
            raise ValueError(
                f"condition must be one of {sorted(_VALID_TRANSITION_CONDITIONS)!r},"
                f" got {value!r}"
            )
        return value


class WorkflowCreate(BaseModel):
    """POST /api/rooms/{room_id}/workflows リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    stages: list[StageCreate] | None = None
    transitions: list[TransitionCreate] | None = None
    entry_stage_id: UUID | None = None
    preset_name: str | None = None

    @model_validator(mode="after")
    def _validate_create_mode(self) -> WorkflowCreate:
        """preset_name が指定された場合は stages/transitions/entry_stage_id は None。
        preset_name が None の場合は name/stages/transitions/entry_stage_id が全て非 None。
        """
        if self.preset_name is not None:
            if any(
                v is not None
                for v in (self.stages, self.transitions, self.entry_stage_id)
            ):
                raise ValueError(
                    "When preset_name is set, stages/transitions/entry_stage_id must be None."
                )
        else:
            missing = [
                field_name
                for field_name, val in [
                    ("name", self.name),
                    ("stages", self.stages),
                    ("transitions", self.transitions),
                    ("entry_stage_id", self.entry_stage_id),
                ]
                if val is None
            ]
            if missing:
                raise ValueError(
                    f"When preset_name is None, the following fields are required: {missing}"
                )
        return self


class WorkflowUpdate(BaseModel):
    """PATCH /api/workflows/{id} リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    stages: list[StageCreate] | None = None
    transitions: list[TransitionCreate] | None = None
    entry_stage_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_update_consistency(self) -> WorkflowUpdate:
        """stages/transitions/entry_stage_id は全て None か全て非 None でなければならない。"""
        topology_fields = [self.stages, self.transitions, self.entry_stage_id]
        none_count = sum(1 for v in topology_fields if v is None)
        if none_count not in (0, 3):
            raise ValueError(
                "stages, transitions, and entry_stage_id must all be None"
                " or all be non-None simultaneously."
            )
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StageResponse(BaseModel):
    """Stage レスポンス要素。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str
    required_role: list[str]
    completion_policy: dict | None
    notify_channels: list[str]
    deliverable_template: str

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain Stage → dict 変換 (duck typing, domain import なし)。"""
        if isinstance(data, dict):
            return data
        return {
            "id": str(data.id),
            "name": data.name,
            "kind": str(data.kind),
            "required_role": sorted(str(r) for r in data.required_role),
            "completion_policy": (
                data.completion_policy.model_dump(mode="json")
                if data.completion_policy
                else None
            ),
            "notify_channels": [
                c.model_dump(mode="json")["target"] for c in data.notify_channels
            ],
            "deliverable_template": data.deliverable_template,
        }


class TransitionResponse(BaseModel):
    """Transition レスポンス要素。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    from_stage_id: str
    to_stage_id: str
    condition: str

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain Transition → dict 変換 (duck typing, domain import なし)。"""
        if isinstance(data, dict):
            return data
        return {
            "id": str(data.id),
            "from_stage_id": str(data.from_stage_id),
            "to_stage_id": str(data.to_stage_id),
            "condition": str(data.condition),
        }


class WorkflowResponse(BaseModel):
    """Workflow 単件レスポンス。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    stages: list[StageResponse]
    transitions: list[TransitionResponse]
    entry_stage_id: str
    archived: bool

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        """domain Workflow → dict 変換 (duck typing, domain import なし)。"""
        if hasattr(data, "stages"):
            return {
                "id": str(data.id),
                "name": data.name,
                "stages": list(data.stages),
                "transitions": list(data.transitions),
                "entry_stage_id": str(data.entry_stage_id),
                "archived": data.archived,
            }
        return data


class WorkflowListResponse(BaseModel):
    """Workflow 一覧レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[WorkflowResponse]
    total: int


class StageListResponse(BaseModel):
    """GET /api/workflows/{id}/stages レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    stages: list[StageResponse]
    transitions: list[TransitionResponse]
    entry_stage_id: str


class WorkflowPresetResponse(BaseModel):
    """Workflow プリセット単件レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    preset_name: str
    display_name: str
    description: str
    stage_count: int
    transition_count: int


class WorkflowPresetListResponse(BaseModel):
    """GET /api/workflows/presets レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[WorkflowPresetResponse]
    total: int


__all__ = [
    "StageCreate",
    "StageListResponse",
    "StageResponse",
    "TransitionCreate",
    "TransitionResponse",
    "WorkflowCreate",
    "WorkflowListResponse",
    "WorkflowPresetListResponse",
    "WorkflowPresetResponse",
    "WorkflowResponse",
    "WorkflowUpdate",
]
