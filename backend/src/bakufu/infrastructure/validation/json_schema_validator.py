"""具体的な JSON Schema バリデータ実装。

``jsonschema`` ライブラリが利用可能な場合はそれを使用し、
利用できない場合は dict 型チェックのみを行う（フォールバック）。

§確定 C（detailed-design.md）: domain 層の ``AbstractJSONSchemaValidator``
インターフェースを実装し、依存方向を保つ。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bakufu.domain.ports.json_schema_validator import AbstractJSONSchemaValidator

if TYPE_CHECKING:
    pass


def _try_check_schema(schema: dict[str, object]) -> None:  # pragma: no cover
    """``jsonschema.Draft7Validator.check_schema`` が利用可能であれば検証する。

    ``jsonschema`` がインストールされていない環境ではノーオペレーション。
    ImportError を無言で飲み込まず、呼び出し元（``JsonSchemaValidator.validate``）
    が利用可否を制御する。
    """
    import jsonschema  # type: ignore[import-untyped]
    import jsonschema.exceptions  # type: ignore[import-untyped]

    try:
        jsonschema.Draft7Validator.check_schema(schema)  # type: ignore[no-untyped-call]
    except jsonschema.exceptions.SchemaError as exc:  # type: ignore[attr-defined]
        raise ValueError(f"Invalid JSON Schema: {exc.message}") from exc


def _jsonschema_available() -> bool:
    """``jsonschema`` パッケージがインストールされているか確認する。"""
    try:
        import jsonschema  # type: ignore[import-untyped]  # noqa: F401

        return True
    except ImportError:
        return False


class JsonSchemaValidator(AbstractJSONSchemaValidator):
    """``jsonschema`` ライブラリを使用した JSON Schema バリデータ。

    ``jsonschema`` がインストールされていない場合は、
    ``schema`` が dict であることの確認のみを行うフォールバック動作をする。
    """

    def validate(self, schema: dict[str, object]) -> None:
        """``schema`` が有効な JSON Schema オブジェクトであることを検証する。

        ``jsonschema`` 利用可能時は ``jsonschema.Draft7Validator.check_schema``
        で検証する。利用不可時は dict 型チェックのみ（フォールバック）。

        Raises:
            ValueError: ``jsonschema`` 利用可能時に schema が無効な場合。
        """
        if _jsonschema_available():
            _try_check_schema(schema)


__all__ = ["JsonSchemaValidator"]
