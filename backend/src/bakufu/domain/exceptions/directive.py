"""Directive ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type DirectiveViolationKind = Literal[
    "text_range",
    "task_already_linked",
]
"""Directive 詳細設計 §確定 F に対応する :class:`DirectiveInvariantViolation` の
判別子。

集合は **2 種類で閉じている**。型・必須フィールド違反は
:class:`pydantic.ValidationError`（MSG-DR-003）として表面化し、``$``
プレフィックス正規化はアプリケーション層の責務（``DirectiveService.issue()``）
であるため、いずれも集約の判別子名前空間には漏れ出さない。
"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class DirectiveInvariantViolation(Exception):  # noqa: N818
    """:class:`Directive` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`RoomInvariantViolation` / :class:`AgentInvariantViolation` と
    同一で、同じ Discord webhook シークレットマスクを適用する。
    ``Directive.text`` はユーザーが貼り付ける CEO 指示の本文であり、
    webhook URL を埋め込まれる可能性があるため、構築時に ``message`` /
    ``detail`` をマスクすれば、呼び出し側は例外をシリアライズしただけで
    トークンを漏洩できなくなる（多層防御。Directive 詳細設計 §確定 E 参照）。
    """

    def __init__(
        self,
        *,
        kind: DirectiveViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: DirectiveViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


__all__ = ["DirectiveInvariantViolation", "DirectiveViolationKind"]
