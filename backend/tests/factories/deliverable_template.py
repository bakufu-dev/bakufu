"""DeliverableTemplate / RoleProfile 集約と VO のファクトリ群。

``docs/features/deliverable-template/domain/test-design.md`` §外部 I/O 依存マップ 準拠。
external-review-gate domain の factory パターンを継承:
- WeakValueDictionary による _meta.synthetic レジストリ
- 本番コンストラクタ経由での構築（model_validate 使用禁止）
- キーワード引数による任意上書き対応

本モジュールは本番コードから import してはならない。
"""

from __future__ import annotations

from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate
from bakufu.domain.deliverable_template.role_profile import RoleProfile
from bakufu.domain.ports.json_schema_validator import AbstractJSONSchemaValidator
from bakufu.domain.value_objects.enums import Role, TemplateType
from bakufu.domain.value_objects.identifiers import (
    DeliverableTemplateId,
    EmpireId,
    RoleProfileId,
)
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)
from pydantic import BaseModel

# モジュールスコープのレジストリ（WeakValueDictionary で GC 圧中立）
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` がファクトリ由来なら ``True`` を返す（ID ベース判定）。"""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# VO ファクトリ
# ---------------------------------------------------------------------------
def make_semver(
    *,
    major: int = 1,
    minor: int = 0,
    patch: int = 0,
) -> SemVer:
    """妥当な :class:`SemVer` を構築する（デフォルト: 1.0.0）。"""
    sv = SemVer(major=major, minor=minor, patch=patch)
    _register(sv)
    return sv


def make_acceptance_criterion(
    *,
    criterion_id: UUID | None = None,
    description: str = "満たすべき条件",
    required: bool = True,
) -> AcceptanceCriterion:
    """妥当な :class:`AcceptanceCriterion` を構築する。"""
    ac = AcceptanceCriterion(
        id=criterion_id or uuid4(),
        description=description,
        required=required,
    )
    _register(ac)
    return ac


def make_deliverable_template_ref(
    *,
    template_id: DeliverableTemplateId | None = None,
    minimum_version: SemVer | None = None,
) -> DeliverableTemplateRef:
    """妥当な :class:`DeliverableTemplateRef` を構築する。"""
    ref = DeliverableTemplateRef(
        template_id=template_id or uuid4(),
        minimum_version=minimum_version or make_semver(),
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# DeliverableTemplate ファクトリ
# ---------------------------------------------------------------------------
def make_deliverable_template(
    *,
    template_id: DeliverableTemplateId | None = None,
    name: str = "テストテンプレート",
    description: str = "",
    type_: TemplateType = TemplateType.MARKDOWN,
    schema: dict[str, object] | str = "",
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = (),
    version: SemVer | None = None,
    composition: tuple[DeliverableTemplateRef, ...] = (),
) -> DeliverableTemplate:
    """妥当な :class:`DeliverableTemplate` を構築する（デフォルト: MARKDOWN 型）。

    JSON_SCHEMA / OPENAPI 型でテストする場合は呼び出し前に
    ``DeliverableTemplate._validator`` を設定すること（§確定 C）。
    """
    dt = DeliverableTemplate(
        id=template_id or uuid4(),
        name=name,
        description=description,
        type=type_,
        schema=schema,
        acceptance_criteria=acceptance_criteria,
        version=version or make_semver(),
        composition=composition,
    )
    _register(dt)
    return dt


# ---------------------------------------------------------------------------
# RoleProfile ファクトリ
# ---------------------------------------------------------------------------
def make_role_profile(
    *,
    profile_id: RoleProfileId | None = None,
    empire_id: EmpireId | None = None,
    role: Role = Role.DEVELOPER,
    deliverable_template_refs: tuple[DeliverableTemplateRef, ...] = (),
) -> RoleProfile:
    """妥当な :class:`RoleProfile` を構築する（デフォルト: DEVELOPER ロール）。"""
    rp = RoleProfile(
        id=profile_id or uuid4(),
        empire_id=empire_id or uuid4(),
        role=role,
        deliverable_template_refs=deliverable_template_refs,
    )
    _register(rp)
    return rp


# ---------------------------------------------------------------------------
# AbstractJSONSchemaValidator スタブ
# ---------------------------------------------------------------------------
class ValidStubValidator(AbstractJSONSchemaValidator):
    """テスト用スタブ: 常に検証成功（何も raise しない）。"""

    def validate(self, schema: dict[str, object]) -> None:
        pass  # Succeed always


class InvalidStubValidator(AbstractJSONSchemaValidator):
    """テスト用スタブ: 常に検証失敗（ValueError を raise）。"""

    def validate(self, schema: dict[str, object]) -> None:
        raise ValueError("stub: invalid schema")


__all__ = [
    "InvalidStubValidator",
    "ValidStubValidator",
    "is_synthetic",
    "make_acceptance_criterion",
    "make_deliverable_template",
    "make_deliverable_template_ref",
    "make_role_profile",
    "make_semver",
]
