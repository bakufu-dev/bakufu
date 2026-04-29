""":class:`Room` のための Aggregate レベル不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import`` して
直接呼べる — Norman / Steve が agent の ``aggregate_validators.py`` と workflow の
``dag_validators.py`` で承認したのと同じテスタビリティ パターン。
:mod:`bakufu.domain.room.room` の Aggregate Root はそれらの薄いディスパッチに留まり、
ルール変更はヘルパのみに触れ、オーケストレーション コードは触らない。

ヘルパ（:class:`Room.model_validator` ではこの順で実行）:

1. :func:`_validate_name_range` — ``1 ≤ NFC+strip(name) ≤ 80``
2. :func:`_validate_description_length` — ``0 ≤ NFC+strip(description) ≤ 500``
3. :func:`_validate_member_unique` — ``(agent_id, role)`` 対の重複なし
4. :func:`_validate_member_capacity` — ``len(members) ≤ 50``

命名は agent / workflow の先例（コレクション一意性チェックには
``_validate_*_unique``）に従う。Boy Scout: 「(a, b) 対の重複なし」を謳うすべての
コレクション コントラクトに専用ヘルパを設けることで、将来のリファクタにルールが
生き残る（Steve の PR #16 twin-defense 対称性ルール）。
"""

from __future__ import annotations

from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room.value_objects import AgentMembership

# Confirmation B: 名前長境界（NFC + strip 後で 1〜80）。
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80

# Confirmation B: description 長境界（NFC + strip 後で 0〜500）。
MAX_DESCRIPTION_LENGTH: int = 500

# Confirmation C: メンバ容量（≤ 50）。
MAX_MEMBERS: int = 50


def _validate_name_range(name: str) -> None:
    """``Room.name`` は NFC + strip 後で 1〜80 文字でなければならない（MSG-RM-001）。

    長さは *正規化済み* 文字列に対して判定される（フィールド バリデータが本ヘルパ
    呼び出し前にパイプラインを走らせる）ため、カウントは監査ログや UI ラベルで
    ユーザが目にする文字数を反映する。
    """
    length = len(name)
    if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
        raise RoomInvariantViolation(
            kind="name_range",
            message=(
                f"[FAIL] Room name must be "
                f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters (got {length})\n"
                f"Next: Provide a name with {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} "
                f"NFC-normalized characters; trim leading/trailing whitespace."
            ),
            detail={"length": length},
        )


def _validate_description_length(description: str) -> None:
    """``Room.description`` は NFC + strip 後で 0〜500 文字でなければならない（MSG-RM-002）。"""
    length = len(description)
    if length > MAX_DESCRIPTION_LENGTH:
        raise RoomInvariantViolation(
            kind="description_too_long",
            message=(
                f"[FAIL] Room description must be 0-{MAX_DESCRIPTION_LENGTH} "
                f"characters (got {length})\n"
                f"Next: Shorten the description to <={MAX_DESCRIPTION_LENGTH} "
                f"characters; move long content to PromptKit.prefix_markdown "
                f"(10000 char limit)."
            ),
            detail={"length": length},
        )


def _validate_member_unique(members: list[AgentMembership]) -> None:
    """2 つのメンバーシップが同じ ``(agent_id, role)`` 対を共有してはならない（MSG-RM-003）。

    同じエージェントが複数ロール（LEADER + REVIEWER 等）を持つことを許すのは
    Room §確定 F の設計選択 — 一意キーは ``agent_id`` 単独ではなく **対**。
    ``joined_at`` は VO の等価性には関与するが、ここでの一意性キーには意図的に
    **含めない** ため、同じ対を異なるタイムスタンプで再追加しても重複として拒否される。
    """
    seen: set[tuple[object, str]] = set()
    for membership in members:
        key = (membership.agent_id, membership.role.value)
        if key in seen:
            raise RoomInvariantViolation(
                kind="member_duplicate",
                message=(
                    f"[FAIL] Duplicate member: "
                    f"agent_id={membership.agent_id}, role={membership.role.value}\n"
                    f"Next: Either skip this add (already a member) or use a "
                    f"different role to add the same agent in another capacity "
                    f"(e.g. leader + reviewer)."
                ),
                detail={
                    "agent_id": str(membership.agent_id),
                    "role": membership.role.value,
                },
            )
        seen.add(key)


def _validate_member_capacity(members: list[AgentMembership]) -> None:
    """メンバ数を :data:`MAX_MEMBERS` で頭打ちにする（MSG-RM-004 / Room §確定 C）。"""
    count = len(members)
    if count > MAX_MEMBERS:
        raise RoomInvariantViolation(
            kind="capacity_exceeded",
            message=(
                f"[FAIL] Room members capacity exceeded "
                f"(got {count}, max {MAX_MEMBERS})\n"
                f"Next: Remove unused members (e.g. archived agents) before "
                f"adding more, or split the work across multiple Rooms."
            ),
            detail={"members_count": count, "max_members": MAX_MEMBERS},
        )


__all__ = [
    "MAX_DESCRIPTION_LENGTH",
    "MAX_MEMBERS",
    "MAX_NAME_LENGTH",
    "MIN_NAME_LENGTH",
    "_validate_description_length",
    "_validate_member_capacity",
    "_validate_member_unique",
    "_validate_name_range",
]
