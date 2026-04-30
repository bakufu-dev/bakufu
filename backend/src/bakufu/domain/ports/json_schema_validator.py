"""JSON Schema バリデータの抽象ポート。

このモジュールは Domain 層が依存する抽象インターフェースを定義する。
具体的な実装（jsonschema ライブラリ使用）は
:mod:`bakufu.infrastructure.validation.json_schema_validator` にある。
"""

from __future__ import annotations

import abc


class AbstractJSONSchemaValidator(abc.ABC):
    """JSON Schema オブジェクトの妥当性を検証する抽象インターフェース。

    Domain 層はこのポートのみに依存し、具体的なライブラリには依存しない
    （Ports & Adapters パターン）。
    """

    @abc.abstractmethod
    def validate(self, schema: dict[str, object]) -> None:
        """``schema`` が有効な JSON Schema オブジェクトであることを検証する。

        Raises:
            Exception: ``schema`` が有効な JSON Schema でない場合。
                呼び出し元の ``_validate_schema_format`` がこの例外を
                :class:`~bakufu.domain.exceptions.DeliverableTemplateInvariantViolation`
                にラップする。
        """
        ...


__all__ = ["AbstractJSONSchemaValidator"]
