"""Task ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type TaskViolationKind = Literal[
    "terminal_violation",
    "state_transition_invalid",
    "assigned_agents_unique",
    "assigned_agents_capacity",
    "last_error_consistency",
    "blocked_requires_last_error",
    "timestamp_order",
]
"""Task 詳細設計 §確定 J に対応する :class:`TaskInvariantViolation` の判別子。
7 種類の閉じた集合で、ターミナル違反・状態機械バイパス・
``model_validator(mode='after')`` で強制される 4 つの構造不変条件・
タイムスタンプ順序チェックを網羅する。型・必須フィールド違反は
``pydantic.ValidationError``（MSG-TS-008 / MSG-TS-009）として表面化し、
本判別子名前空間には漏れ出さない。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class TaskInvariantViolation(Exception):  # noqa: N818
    """:class:`Task` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`DirectiveInvariantViolation` / :class:`RoomInvariantViolation` /
    :class:`AgentInvariantViolation` / :class:`WorkflowInvariantViolation` と
    同一で、同じ Discord webhook シークレットマスクを適用する。
    ``Task.last_error`` は webhook URL を含む LLM-Adapter スタックトレースを
    保持する可能性があり（MVP は Discord 通知を行う）、
    ``Deliverable.body_markdown`` は CEO / Agent が書いたコンテンツである。
    両者は ``state_transition_invalid`` や ``last_error_consistency`` の経路を介して
    ``message`` / ``detail`` に流入し得るため、構築時に ``message`` /
    ``detail`` をマスクすれば、呼び出し側は例外をシリアライズしただけでトークンを
    漏洩できなくなる（多層防御。Task 詳細設計 §確定 I 参照）。
    """

    def __init__(
        self,
        *,
        kind: TaskViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: TaskViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


__all__ = ["TaskInvariantViolation", "TaskViolationKind"]
