"""DeliverableTemplate / RoleProfile 集約の不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import`` して
直接呼べる — Room / Agent の ``aggregate_validators.py`` と同じテスタビリティ パターン。

ヘルパ一覧:

1. :func:`_validate_schema_format` — type に応じた schema 型チェック + JSON Schema 検証
2. :func:`_validate_composition_no_self_ref` — 自己参照コンポジションを拒否
3. :func:`_validate_version_non_negative` — バージョン非負チェック（SemVer ge=0 で既保証）
4. :func:`_validate_acceptance_criteria_non_empty_descriptions` — 受け入れ基準の空説明を拒否
5. :func:`_validate_acceptance_criteria_no_duplicate_ids` — 受け入れ基準 UUID 重複を拒否
6. :func:`_validate_no_duplicate_refs` — DeliverableTemplateRef の重複を拒否（RoleProfile 用）
"""

from __future__ import annotations

from uuid import UUID

from bakufu.domain.exceptions import (
    DeliverableTemplateInvariantViolation,
    RoleProfileInvariantViolation,
)
from bakufu.domain.ports.json_schema_validator import AbstractJSONSchemaValidator
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.identifiers import DeliverableTemplateId
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)

# ---------------------------------------------------------------------------
# メッセージ定数（詳細設計 §MSG）
# ---------------------------------------------------------------------------
_MSG_DT_001 = (
    "[FAIL] Template schema is not valid JSON Schema.\n"
    "Next: Provide a valid JSON Schema object (https://json-schema.org/)."
)
_MSG_DT_002 = (
    "[FAIL] Template cannot include itself in composition.\n"
    "Next: Remove self-referential template_id from composition list."
)
_MSG_DT_004_TMPL = (
    "[FAIL] Template reference {template_id} already exists in this RoleProfile.\n"
    "Next: Remove the duplicate before adding a new reference."
)
_MSG_DT_005_TMPL = (
    "[FAIL] Template reference {template_id} not found in this RoleProfile.\n"
    "Next: Verify the template_id and retry."
)


def _validate_schema_format(
    type_: TemplateType,
    schema: dict[str, object] | str,
    validator: AbstractJSONSchemaValidator | None,
) -> None:
    """``type_`` に応じた schema フォーマットを検証する（MSG-DT-001）。

    * MARKDOWN / CODE_SKELETON / PROMPT: schema は str でなければならない。
    * JSON_SCHEMA / OPENAPI: schema は dict でなければならず、
      validator が None の場合は Fail Secure で拒否する。
      validator が存在する場合はそれに委譲し、例外をラップする。

    Raises:
        DeliverableTemplateInvariantViolation: フォーマット不正 / validator なし /
            validator が例外を送出した場合。
    """
    str_types = {TemplateType.MARKDOWN, TemplateType.CODE_SKELETON, TemplateType.PROMPT}
    dict_types = {TemplateType.JSON_SCHEMA, TemplateType.OPENAPI}

    if type_ in str_types:
        if not isinstance(schema, str):
            raise DeliverableTemplateInvariantViolation(
                kind="schema_format_invalid",
                message=_MSG_DT_001,
                detail={"schema_type": type(schema).__name__},
            )
    elif type_ in dict_types:
        if not isinstance(schema, dict):
            raise DeliverableTemplateInvariantViolation(
                kind="schema_format_invalid",
                message=_MSG_DT_001,
                detail={"schema_type": type(schema).__name__},
            )
        # Fail Secure: validator が None の場合は検証できないため拒否する
        if validator is None:
            raise DeliverableTemplateInvariantViolation(
                kind="schema_format_invalid",
                message=_MSG_DT_001,
                detail={"schema_type": type(schema).__name__},
            )
        try:
            validator.validate(schema)
        except DeliverableTemplateInvariantViolation:
            raise
        except Exception as exc:
            raise DeliverableTemplateInvariantViolation(
                kind="schema_format_invalid",
                message=_MSG_DT_001,
                detail={"schema_type": type(schema).__name__},
            ) from exc


def _validate_composition_no_self_ref(
    self_id: DeliverableTemplateId,
    composition: tuple[DeliverableTemplateRef, ...],
) -> None:
    """コンポジションに自己参照が含まれていないことを検証する（MSG-DT-002）。

    Raises:
        DeliverableTemplateInvariantViolation: ``kind='composition_self_ref'``
    """
    for ref in composition:
        if ref.template_id == self_id:
            raise DeliverableTemplateInvariantViolation(
                kind="composition_self_ref",
                message=_MSG_DT_002,
                detail={"template_id": str(self_id)},
            )


def _validate_version_non_negative(version: SemVer) -> None:
    """バージョンの各部分が非負であることを検証する。

    SemVer フィールドの ``ge=0`` 制約で既に保証されているが、
    ドメイン不変条件として明示的にチェックする。

    Raises:
        DeliverableTemplateInvariantViolation: ``kind='version_non_negative'``
    """
    if version.major < 0 or version.minor < 0 or version.patch < 0:
        raise DeliverableTemplateInvariantViolation(
            kind="version_non_negative",
            message=(
                "[FAIL] Version components must be non-negative integers.\n"
                "Next: Use non-negative integers for MAJOR.MINOR.PATCH."
            ),
            detail={
                "major": version.major,
                "minor": version.minor,
                "patch": version.patch,
            },
        )


def _validate_acceptance_criteria_non_empty_descriptions(
    criteria: tuple[AcceptanceCriterion, ...],
) -> None:
    """受け入れ基準の各 description が空でないことを検証する。

    AcceptanceCriterion の ``min_length=1`` で既に保証されているが、
    ドメイン不変条件として明示的にチェックする。

    Raises:
        DeliverableTemplateInvariantViolation: ``kind='acceptance_criteria_empty_description'``
    """
    for c in criteria:
        if len(c.description) == 0:
            raise DeliverableTemplateInvariantViolation(
                kind="acceptance_criteria_empty_description",
                message=(
                    "[FAIL] Acceptance criterion description must not be empty.\n"
                    "Next: Provide a non-empty description for each acceptance criterion."
                ),
                detail={"criterion_id": str(c.id), "description_length": 0},
            )


def _validate_acceptance_criteria_no_duplicate_ids(
    criteria: tuple[AcceptanceCriterion, ...],
) -> None:
    """受け入れ基準の UUID が重複していないことを検証する。

    Raises:
        DeliverableTemplateInvariantViolation: ``kind='acceptance_criteria_duplicate_id'``
    """
    seen: set[UUID] = set()
    for c in criteria:
        if c.id in seen:
            raise DeliverableTemplateInvariantViolation(
                kind="acceptance_criteria_duplicate_id",
                message=(
                    "[FAIL] Acceptance criterion IDs must be unique.\n"
                    "Next: Remove the duplicate acceptance criterion or assign a new UUID."
                ),
                detail={"criterion_id": str(c.id)},
            )
        seen.add(c.id)


def _validate_no_duplicate_refs(
    refs: tuple[DeliverableTemplateRef, ...],
) -> None:
    """DeliverableTemplateRef の template_id が重複していないことを検証する（RoleProfile 用）。

    Raises:
        RoleProfileInvariantViolation: ``kind='duplicate_template_ref'``
    """
    seen: set[DeliverableTemplateId] = set()
    for ref in refs:
        if ref.template_id in seen:
            dup_id = ref.template_id
            raise RoleProfileInvariantViolation(
                kind="duplicate_template_ref",
                message=_MSG_DT_004_TMPL.format(template_id=dup_id),
                detail={"template_id": str(dup_id)},
            )
        seen.add(ref.template_id)


__all__ = [
    "_MSG_DT_004_TMPL",
    "_MSG_DT_005_TMPL",
    "_validate_acceptance_criteria_no_duplicate_ids",
    "_validate_acceptance_criteria_non_empty_descriptions",
    "_validate_composition_no_self_ref",
    "_validate_no_duplicate_refs",
    "_validate_schema_format",
    "_validate_version_non_negative",
]
