"""DeliverableTemplate / RoleProfile ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

type DeliverableTemplateViolationKind = Literal[
    "schema_format_invalid",
    "composition_self_ref",
    "version_not_greater",
    "version_non_negative",
    "acceptance_criteria_empty_description",
    "acceptance_criteria_duplicate_id",
]
"""DeliverableTemplate 詳細設計 §Exception に対応する
:class:`DeliverableTemplateInvariantViolation` の判別子。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class DeliverableTemplateInvariantViolation(Exception):  # noqa: N818
    """:class:`DeliverableTemplate` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`EmpireInvariantViolation` / :class:`InternalReviewGateInvariantViolation`
    と同一。DeliverableTemplate のフィールドには Discord webhook URL が含まれないため、
    本層ではシークレット マスキングを適用しない。

    Attributes:
        kind: :data:`DeliverableTemplateViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: deliverable-template 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: DeliverableTemplateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: DeliverableTemplateViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type RoleProfileViolationKind = Literal[
    "duplicate_template_ref",
    "template_ref_not_found",
]
"""RoleProfile 詳細設計 §Exception に対応する
:class:`RoleProfileInvariantViolation` の判別子。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class RoleProfileInvariantViolation(Exception):  # noqa: N818
    """:class:`RoleProfile` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`DeliverableTemplateInvariantViolation` と同一。

    Attributes:
        kind: :data:`RoleProfileViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: role-profile 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: RoleProfileViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: RoleProfileViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type DeliverableRecordViolationKind = Literal["invalid_validation_state",]
"""DeliverableRecord 不変条件違反の判別子。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class DeliverableRecordInvariantViolation(Exception):  # noqa: N818
    """DeliverableRecord 集約の不変条件違反時に送出される。

    Attributes:
        kind: 違反判別子。
        message: ユーザー向けエラー文言。
    """

    def __init__(
        self,
        *,
        kind: DeliverableRecordViolationKind,
        message: str,
    ) -> None:
        super().__init__(message)
        self.kind: DeliverableRecordViolationKind = kind
        self.message: str = message


class LLMValidationError(Exception):
    """LLM 検証失敗例外。

    ValidationService が LLMProviderError または JSON パース失敗を検出した際に raise される。
    typed フィールドのみ保持し、機密情報（APIキー・トークン）は含めない（T2 セキュリティ設計）。

    Attributes:
        message: 人間可読エラーメッセージ（MSG-AIVM-001 / MSG-AIVM-002）。
        kind: "llm_call_failed" または "parse_failed"。
        llm_error_kind: LLMProviderError サブクラス識別。parse_failed 時は ""。
        provider: プロバイダ識別子（"claude-code" / "codex"）。
    """

    def __init__(
        self,
        *,
        message: str,
        kind: Literal["llm_call_failed", "parse_failed"],
        llm_error_kind: str,
        provider: str,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.kind: Literal["llm_call_failed", "parse_failed"] = kind
        self.llm_error_kind: str = llm_error_kind
        self.provider: str = provider


__all__ = [
    "DeliverableRecordInvariantViolation",
    "DeliverableRecordViolationKind",
    "DeliverableTemplateInvariantViolation",
    "DeliverableTemplateViolationKind",
    "LLMValidationError",
    "RoleProfileInvariantViolation",
    "RoleProfileViolationKind",
]
