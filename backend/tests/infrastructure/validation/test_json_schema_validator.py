"""JsonSchemaValidator concrete実装テスト。

TC-INFRA-JSV-001〜005:
- 有効 JSON Schema → エラーなし
- 無効 JSON Schema → ValueError (# pragma: no cover パス物理カバー)
- 空 dict → エラーなし（valid minimal schema）
- properties 含む複合 schema → エラーなし
- required が type ではない無効 schema → ValueError

Issue #115 / ヘルスバーグ・タブリーズレビュー指摘: _try_check_schema に
pragma: no cover が除去されたため、実際の jsonschema ライブラリ呼び出しを
物理カバーして Fail Secure を担保する。

§確定 C（Validation Port）: JsonSchemaValidator は AbstractJSONSchemaValidator
を実装し、domain 層は具象クラスを知らない。
"""

from __future__ import annotations

import pytest
from bakufu.infrastructure.validation.json_schema_validator import JsonSchemaValidator


# ---------------------------------------------------------------------------
# TC-INFRA-JSV-001: 有効な JSON Schema（最小形式）→ エラーなし
# ---------------------------------------------------------------------------
class TestJsonSchemaValidatorValidSchema:
    """TC-INFRA-JSV-001: 有効な JSON Schema dict → ValueError を raise しない。"""

    def test_valid_empty_schema_does_not_raise(self) -> None:
        """空 dict {} は有効な JSON Schema（任意の値を許容）。"""
        validator = JsonSchemaValidator()
        validator.validate({})  # no raise

    def test_valid_type_object_schema_does_not_raise(self) -> None:
        """type: object の基本 schema → エラーなし。"""
        validator = JsonSchemaValidator()
        validator.validate({"type": "object", "properties": {}})

    def test_valid_complex_schema_does_not_raise(self) -> None:
        """properties + required + additionalProperties を含む schema → エラーなし。"""
        validator = JsonSchemaValidator()
        validator.validate(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 0},
                },
                "required": ["name"],
                "additionalProperties": False,
            }
        )

    def test_valid_array_schema_does_not_raise(self) -> None:
        """type: array の schema → エラーなし。"""
        validator = JsonSchemaValidator()
        validator.validate({"type": "array", "items": {"type": "string"}})


# ---------------------------------------------------------------------------
# TC-INFRA-JSV-002: 無効な JSON Schema → ValueError (_try_check_schema パス物理カバー)
# ---------------------------------------------------------------------------
class TestJsonSchemaValidatorInvalidSchema:
    """TC-INFRA-JSV-002: 無効な JSON Schema dict → ValueError。

    このテストクラスが _try_check_schema の本体コードパスを物理的にカバーする。
    pragma: no cover は除去済み。
    """

    def test_invalid_type_value_raises_value_error(self) -> None:
        """type フィールドに不正値 → ValueError。

        jsonschema.Draft7Validator.check_schema が SchemaError を raise し、
        _try_check_schema が ValueError に変換する。
        """
        validator = JsonSchemaValidator()
        with pytest.raises(ValueError):
            validator.validate({"type": "not_a_valid_type"})

    def test_invalid_minimum_type_raises_value_error(self) -> None:
        """minimum に非数値 → jsonschema SchemaError → ValueError。"""
        validator = JsonSchemaValidator()
        with pytest.raises(ValueError):
            validator.validate({"type": "integer", "minimum": "not_a_number"})

    def test_error_message_contains_schema_info(self) -> None:
        """ValueError のメッセージに 'Invalid JSON Schema' が含まれる。"""
        validator = JsonSchemaValidator()
        with pytest.raises(ValueError) as exc_info:
            validator.validate({"type": "not_a_valid_type"})
        assert "Invalid JSON Schema" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-INFRA-JSV-003: jsonschema が必須依存であることの確認
# ---------------------------------------------------------------------------
class TestJsonSchemaValidatorModuleLevel:
    """TC-INFRA-JSV-003: jsonschema がモジュールレベル import されていること。

    Fail Secure 規約: jsonschema 未インストール時は import 時点で
    ImportError が伝播する（起動時エラー）。
    """

    def test_jsonschema_is_importable(self) -> None:
        """jsonschema が環境にインストール済みであること。"""
        try:
            import jsonschema as _jschema  # type: ignore[import-untyped]

            assert _jschema is not None
        except ImportError:
            pytest.fail("jsonschema must be installed as a runtime dependency")

    def test_validator_is_concrete_implementation(self) -> None:
        """JsonSchemaValidator が AbstractJSONSchemaValidator を実装していること。"""
        from bakufu.domain.ports.json_schema_validator import AbstractJSONSchemaValidator

        validator = JsonSchemaValidator()
        assert isinstance(validator, AbstractJSONSchemaValidator)
