"""Workflow / Stage ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type WorkflowViolationKind = Literal[
    "name_range",
    "entry_not_in_stages",
    "transition_ref_invalid",
    "transition_duplicate",
    "transition_id_duplicate",
    "unreachable_stage",
    "no_sink_stage",
    "capacity_exceeded",
    "stage_duplicate",
    "cannot_remove_entry",
    "stage_not_found",
    "missing_notify_aggregate",
    "empty_required_role_aggregate",
    "from_dict_invalid",
    "masked_notify_channel",
]
"""workflow 詳細設計 §Exception に対応する :class:`WorkflowInvariantViolation`
の判別子。設計上の正式 11 種類に加え、MSG-WF-001 / MSG-WF-008 で表面化する
3 つの運用判別子（``name_range`` / ``stage_duplicate`` 等）と、Transition
コレクション契約に対する ``stage_duplicate`` の対となる
``transition_id_duplicate`` を追加している（詳細設計 §Aggregate Root: Workflow
の ``transitions: 0〜60 件、transition_id の重複なし`` 行参照）。"""


type StageViolationKind = Literal[
    "duplicate_required_deliverable",
    "empty_required_role",
    "missing_notify",
]
""":class:`StageInvariantViolation` の判別子（Workflow 詳細設計 / Issue #117）。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class WorkflowInvariantViolation(Exception):  # noqa: N818
    """:class:`Workflow` 集約の不変条件違反時に送出される。

    すべての ``message`` / ``detail`` 文字列は構築時に
    :func:`mask_discord_webhook_in` を通すため、埋め込まれた Discord
    webhook URL のシークレット ``token`` 部分は
    ``<REDACTED:DISCORD_WEBHOOK>`` に置換される。これにより、例外を
    シリアライズしただけで下流のログ・監査利用側が webhook 資格情報を
    漏洩することは不可能になる（Workflow 詳細設計 §確定 G
    「target のシークレット扱い」の「例外 message / detail」行）。
    """

    def __init__(
        self,
        *,
        kind: WorkflowViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: WorkflowViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


# ``except WorkflowInvariantViolation`` で Stage レベル違反も捕捉できるよう
# サブクラス化する（集約パスは Stage 自身のバリデータに委譲する場合があり、
# 呼び出し側は両者を一様に扱うべき）。
class StageInvariantViolation(WorkflowInvariantViolation):
    """:class:`Stage` の自己検証（集約とは独立）から送出される。

    ``kind`` は :data:`StageViolationKind` に絞られるが、周囲の
    ``WorkflowInvariantViolation` 型契約（``message`` / ``detail`` への
    シークレットマスク含む）は維持される。
    """

    def __init__(
        self,
        *,
        kind: StageViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        # 親へ転送し、マスクと判別子フィールドを同一に設定させる。
        # 静的型のため self.kind を再度狭める。
        super().__init__(
            kind=kind,  # type: ignore[arg-type]
            message=message,
            detail=detail,
        )
        self.kind: StageViolationKind = kind  # type: ignore[assignment]


__all__ = [
    "StageInvariantViolation",
    "StageViolationKind",
    "WorkflowInvariantViolation",
    "WorkflowViolationKind",
]
