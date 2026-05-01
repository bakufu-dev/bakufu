"""Empire ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

type EmpireViolationKind = Literal[
    "name_range",
    "agent_duplicate",
    "room_duplicate",
    "room_not_found",
    "capacity_exceeded",
]
"""詳細設計 §Exception に対応する ``EmpireInvariantViolation`` の判別子。"""


# ドメイン命名規約は DDD に従う: "Violation" は不変条件違反を表現するもので、
# プログラミングエラーではない。そのため N818 "Error suffix" ルールは適用しない。
class EmpireInvariantViolation(Exception):  # noqa: N818
    """:class:`Empire` 集約の不変条件違反時に送出される。

    Pydantic v2 の ``model_validator(mode='after')`` は ``ValueError`` /
    ``AssertionError`` 以外の例外を ``ValidationError`` でラップせずに
    再送出するため、呼び出し側は完全な ``kind`` / ``detail`` 構造を保ったまま
    本例外を直接受け取る。

    Attributes:
        kind: :data:`EmpireViolationKind` の正式な違反判別子のいずれか。
            テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: 詳細設計 §MSG の ``MSG-EM-001``〜``MSG-EM-005`` に対応する
            ``[FAIL] ...`` 形式のユーザー向け完全文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト（UUID, 長さ, 件数等）。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: EmpireViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: EmpireViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


__all__ = ["EmpireInvariantViolation", "EmpireViolationKind"]
