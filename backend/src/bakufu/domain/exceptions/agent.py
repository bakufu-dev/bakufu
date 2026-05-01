"""Agent ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type AgentViolationKind = Literal[
    "name_range",
    "no_provider",
    "default_not_unique",
    "provider_duplicate",
    "persona_too_long",
    "provider_not_found",
    "skill_duplicate",
    "skill_not_found",
    "skill_path_invalid",
    "archetype_too_long",
    "display_name_range",
    "provider_not_implemented",
    "skill_capacity_exceeded",
    "provider_capacity_exceeded",
]
"""Agent 詳細設計 §Exception に対応する :class:`AgentInvariantViolation` の
判別子。設計上の 12 種類に加え、§確定 C の境界値（providers ≤ 10, skills ≤ 20）を
表面化する 2 つの ``*_capacity_exceeded`` 運用判別子を追加している。これらが
なければ既存 kind と MSG が重複し、HTTP API 層での判別ができなくなる。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class AgentInvariantViolation(Exception):  # noqa: N818
    """:class:`Agent` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`EmpireInvariantViolation` と同一で、:class:`WorkflowInvariantViolation`
    と同じ Discord webhook シークレットマスクを適用する。SkillRef.path や
    Persona.prompt_body に Discord webhook URL の断片が含まれた場合でも、
    例外テキスト経由で漏洩することはない。
    """

    def __init__(
        self,
        *,
        kind: AgentViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: AgentViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


__all__ = ["AgentInvariantViolation", "AgentViolationKind"]
