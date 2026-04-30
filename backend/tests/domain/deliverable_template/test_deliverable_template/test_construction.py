"""DeliverableTemplate 構築テスト。

TC-UT-DT-001〜007, TC-UT-DT-017:
- TemplateType 5 値全種の正常構築
- frozen 不変性
- extra='forbid'
- 型違反（pydantic.ValidationError）

Issue #115 / docs/features/deliverable-template/domain/test-design.md §UT-DT 構築
"""

from __future__ import annotations

import pytest
from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate
from bakufu.domain.value_objects.enums import TemplateType
from pydantic import ValidationError

from tests.factories.deliverable_template import (
    ValidStubValidator,
    is_synthetic,
    make_deliverable_template,
)


# ---------------------------------------------------------------------------
# TC-UT-DT-001: MARKDOWN + str schema
# ---------------------------------------------------------------------------
class TestMarkdownTemplate:
    """TC-UT-DT-001: type=MARKDOWN, schema=str で構築成功。"""

    def test_markdown_str_schema_succeeds(self) -> None:
        dt = make_deliverable_template(type_=TemplateType.MARKDOWN, schema="# テンプレート")
        assert dt.type == TemplateType.MARKDOWN
        assert dt.schema == "# テンプレート"
        assert dt.acceptance_criteria == ()
        assert dt.composition == ()

    def test_factory_marks_synthetic(self) -> None:
        dt = make_deliverable_template()
        assert is_synthetic(dt)


# ---------------------------------------------------------------------------
# TC-UT-DT-002: JSON_SCHEMA + valid dict
# ---------------------------------------------------------------------------
class TestJsonSchemaTemplate:
    """TC-UT-DT-002: type=JSON_SCHEMA, valid dict schema で構築成功（§確定 C）。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = ValidStubValidator()  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_json_schema_valid_dict_succeeds(self) -> None:
        dt = make_deliverable_template(
            type_=TemplateType.JSON_SCHEMA,
            schema={"type": "object", "properties": {}},
        )
        assert dt.type == TemplateType.JSON_SCHEMA
        assert isinstance(dt.schema, dict)


# ---------------------------------------------------------------------------
# TC-UT-DT-003: OPENAPI + valid dict
# ---------------------------------------------------------------------------
class TestOpenApiTemplate:
    """TC-UT-DT-003: type=OPENAPI, valid dict schema で構築成功。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = ValidStubValidator()  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_openapi_valid_dict_succeeds(self) -> None:
        dt = make_deliverable_template(
            type_=TemplateType.OPENAPI,
            schema={"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}},
        )
        assert dt.type == TemplateType.OPENAPI
        assert isinstance(dt.schema, dict)


# ---------------------------------------------------------------------------
# TC-UT-DT-004: CODE_SKELETON + str schema
# ---------------------------------------------------------------------------
class TestCodeSkeletonTemplate:
    """TC-UT-DT-004: type=CODE_SKELETON, schema=str で構築成功。"""

    def test_code_skeleton_str_schema_succeeds(self) -> None:
        dt = make_deliverable_template(
            type_=TemplateType.CODE_SKELETON,
            schema="def main(): ...",
        )
        assert dt.type == TemplateType.CODE_SKELETON
        assert dt.schema == "def main(): ..."


# ---------------------------------------------------------------------------
# TC-UT-DT-005: PROMPT + str schema
# ---------------------------------------------------------------------------
class TestPromptTemplate:
    """TC-UT-DT-005: type=PROMPT, schema=str で構築成功。"""

    def test_prompt_str_schema_succeeds(self) -> None:
        dt = make_deliverable_template(
            type_=TemplateType.PROMPT,
            schema="あなたは優秀なエンジニアです。",
        )
        assert dt.type == TemplateType.PROMPT


# ---------------------------------------------------------------------------
# TC-UT-DT-006: frozen 不変性
# ---------------------------------------------------------------------------
class TestFrozenImmutability:
    """TC-UT-DT-006: frozen モデルへの直接代入は pydantic.ValidationError。"""

    def test_direct_assignment_raises_validation_error(self) -> None:
        dt = make_deliverable_template()
        with pytest.raises((ValidationError, TypeError)):
            dt.name = "変更不可"  # type: ignore[misc]

    def test_direct_assignment_to_type_raises(self) -> None:
        dt = make_deliverable_template()
        with pytest.raises((ValidationError, TypeError)):
            dt.type = TemplateType.PROMPT  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-UT-DT-007: extra='forbid'
# ---------------------------------------------------------------------------
class TestExtraForbid:
    """TC-UT-DT-007: 未知フィールドは pydantic.ValidationError。"""

    def test_unknown_field_raises_validation_error(self) -> None:
        base = make_deliverable_template()
        data = base.model_dump(mode="python")
        data["unknown_field"] = "forbidden"
        with pytest.raises(ValidationError):
            DeliverableTemplate.model_validate(data)


# ---------------------------------------------------------------------------
# TC-UT-DT-017: 型違反
# ---------------------------------------------------------------------------
class TestTypeMismatch:
    """TC-UT-DT-017: 型違反は pydantic.ValidationError。"""

    def test_invalid_type_enum_raises(self) -> None:
        base = make_deliverable_template()
        data = base.model_dump(mode="python")
        data["type"] = "UNKNOWN_TYPE"
        with pytest.raises(ValidationError):
            DeliverableTemplate.model_validate(data)

    def test_invalid_id_format_raises(self) -> None:
        base = make_deliverable_template()
        data = base.model_dump(mode="python")
        data["id"] = "not-a-uuid"
        with pytest.raises(ValidationError):
            DeliverableTemplate.model_validate(data)

    def test_invalid_version_type_raises(self) -> None:
        base = make_deliverable_template()
        data = base.model_dump(mode="python")
        data["version"] = "not-semver-type"
        with pytest.raises(ValidationError):
            DeliverableTemplate.model_validate(data)
