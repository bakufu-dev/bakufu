"""InternalReviewGate / ExternalReviewGate ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type InternalReviewGateViolationKind = Literal[
    "role_already_submitted",
    "gate_already_decided",
    "comment_too_long",
    "invalid_role",
    "required_gate_roles_empty",
    "verdict_role_invalid",
    "duplicate_role_verdict",
    "gate_decision_inconsistent",
]
"""internal-review-gate 詳細設計に対応する :class:`InternalReviewGateInvariantViolation`
の判別子。8 種類で閉じた集合で、submit-verdict のガード条件と
``model_validator(mode='after')`` で強制される 4 つの構造的不変条件を網羅する。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class InternalReviewGateInvariantViolation(Exception):  # noqa: N818
    """:class:`InternalReviewGate` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`ExternalReviewGateInvariantViolation` と同一。内部レビュー コンテンツ
    （コメント、ロール名）はエージェント著作で Discord webhook URL を埋め込まない
    ため、本層ではシークレット マスキングを適用しない — 標準の ``kind`` /
    ``message`` / ``detail`` 三つ組で十分。

    Attributes:
        kind: :data:`InternalReviewGateViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: internal-review-gate 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト（ロール名、長さ、件数等）。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピー
            として格納する。
    """

    def __init__(
        self,
        *,
        kind: InternalReviewGateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: InternalReviewGateViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type ExternalReviewGateViolationKind = Literal[
    "decision_already_decided",
    "decided_at_inconsistent",
    "snapshot_immutable",
    "feedback_text_range",
    "audit_trail_append_only",
    "criteria_immutable",
]
"""external-review-gate 詳細設計 §確定 I に対応する
:class:`ExternalReviewGateInvariantViolation` の判別子。6 種類で閉じた集合で、
state-machine バイパス（PENDING 限定の decision 遷移）、5 つの
``model_validator(mode='after')`` 構造的不変条件（§確定 D' ``criteria_immutable``
を含む）、そして audit-trail 追記専用コントラクトを網羅する。型・必須フィールド違反は
:class:`pydantic.ValidationError`（MSG-GT-006）として表面化するため、本判別子
名前空間には漏れ出さない。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class ExternalReviewGateInvariantViolation(Exception):  # noqa: N818
    """:class:`ExternalReviewGate` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`TaskInvariantViolation` / :class:`DirectiveInvariantViolation` /
    :class:`RoomInvariantViolation` / :class:`AgentInvariantViolation` /
    :class:`WorkflowInvariantViolation` と同一で、同じ Discord webhook
    シークレット マスキングを適用する。Gate の ``feedback_text`` と
    ``audit_trail.comment`` は CEO 著作のフィールドで、Discord チャンネルから
    貼り付けられた webhook URL を埋め込まれる可能性があるため、構築時に
    ``message`` / ``detail`` をマスクすれば、呼び出し側は例外をシリアライズした
    だけでトークンを漏洩できなくなる（多層防御。external-review-gate 詳細設計
    §確定 H 参照）。
    """

    def __init__(
        self,
        *,
        kind: ExternalReviewGateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: ExternalReviewGateViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


__all__ = [
    "ExternalReviewGateInvariantViolation",
    "ExternalReviewGateViolationKind",
    "InternalReviewGateInvariantViolation",
    "InternalReviewGateViolationKind",
]
