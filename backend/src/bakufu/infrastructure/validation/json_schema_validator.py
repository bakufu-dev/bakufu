"""具体的な JSON Schema バリデータ実装。

``jsonschema`` ライブラリを使用して JSON Schema の構造的妥当性を検証する。
``jsonschema`` は runtime 必須依存であり、未インストール時は ImportError が伝播する。

§確定 C（detailed-design.md）: domain 層の ``AbstractJSONSchemaValidator``
インターフェースを実装し、依存方向を保つ。
"""

from __future__ import annotations

import jsonschema  # type: ignore[import-untyped]
import jsonschema.exceptions  # type: ignore[import-untyped]

from bakufu.domain.ports.json_schema_validator import AbstractJSONSchemaValidator


def _try_check_schema(schema: dict[str, object]) -> None:
    """``jsonschema.Draft7Validator.check_schema`` で schema を検証する。

    Raises:
        ValueError: schema が無効な JSON Schema である場合。
    """
    try:
        jsonschema.Draft7Validator.check_schema(schema)  # type: ignore[no-untyped-call]
    except jsonschema.exceptions.SchemaError as exc:  # type: ignore[attr-defined]
        raise ValueError(f"Invalid JSON Schema: {exc.message}") from exc


class JsonSchemaValidator(AbstractJSONSchemaValidator):
    """``jsonschema`` ライブラリを使用した JSON Schema バリデータ。"""

    def validate(self, schema: dict[str, object]) -> None:
        """``schema`` が有効な JSON Schema オブジェクトであることを検証する。

        ``jsonschema.Draft7Validator.check_schema`` で検証する。

        Raises:
            ValueError: schema が無効な JSON Schema である場合。
        """
        _try_check_schema(schema)


__all__ = ["JsonSchemaValidator"]
