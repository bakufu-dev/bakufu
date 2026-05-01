"""Room / RoomRoleOverride ドメイン例外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type RoomViolationKind = Literal[
    "name_range",
    "description_too_long",
    "member_duplicate",
    "capacity_exceeded",
    "member_not_found",
    "room_archived",
]
"""Room 詳細設計 §Exception（§確定 I 例外型統一規約）に対応する
:class:`RoomInvariantViolation` の判別子。

集合は **6 種類で閉じている**: ``prompt_kit_too_long`` は *意図的に省略* されている。
PromptKit VO は Room 不変条件チェックが走る前に自身の ``model_validator`` で
:class:`pydantic.ValidationError` を送出するためであり、ここに追加しても
``RoomInvariantViolation`` から構造上到達できないデッドコードになる
（Room 詳細設計 §確定 I の 2 段階 catch 参照）。
"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class RoomInvariantViolation(Exception):  # noqa: N818
    """:class:`Room` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`AgentInvariantViolation` / :class:`WorkflowInvariantViolation`
    と同一で、同じ Discord webhook シークレットマスクを適用する。
    ``Room.name`` / ``Room.description`` / ``PromptKit.prefix_markdown`` は
    いずれもユーザーが貼り付けた webhook URL を含む可能性があるため、
    構築時に ``message`` / ``detail`` をマスクすることで、呼び出し側が
    例外をシリアライズしただけでトークンを漏洩することはなくなる
    （多層防御。Room 詳細設計 §確定 H 参照）。
    """

    def __init__(
        self,
        *,
        kind: RoomViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: RoomViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type RoomRoleOverrideViolationKind = Literal["duplicate_template_id",]
"""RoomRoleOverride 詳細設計 §確定 に対応する
:class:`RoomRoleOverrideInvariantViolation` の判別子。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class RoomRoleOverrideInvariantViolation(Exception):  # noqa: N818
    """:class:`RoomRoleOverride` VO の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`RoleProfileInvariantViolation` と同一。
    RoomRoleOverride のフィールドには Discord webhook URL が含まれないため、
    本層ではシークレット マスキングを適用しない。

    Attributes:
        kind: :data:`RoomRoleOverrideViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: room-matching 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: RoomRoleOverrideViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: RoomRoleOverrideViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


__all__ = [
    "RoomInvariantViolation",
    "RoomRoleOverrideInvariantViolation",
    "RoomRoleOverrideViolationKind",
    "RoomViolationKind",
]
