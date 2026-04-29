"""Room Aggregate Root パッケージ。

``docs/features/room`` に従って ``REQ-RM-001``〜``REQ-RM-006`` を実装する。
設計の責務境界に沿って 3 つの兄弟モジュールに分割し、各ファイルが 270 行の
可読性予算を十分に下回るようにし、ファイル レベル境界が agent / workflow の
先例を踏襲するようにする:

* :mod:`bakufu.domain.room.value_objects` — :class:`AgentMembership` と
  :class:`PromptKit` の Pydantic VO（自己チェック付き）。
* :mod:`bakufu.domain.room.aggregate_validators` — name range / description
  length / member 一意性 / member 容量を網羅するモジュール レベルの不変条件
  ヘルパ 4 つ。
* :mod:`bakufu.domain.room.room` — ヘルパを決定的順序でディスパッチする
  :class:`Room` Aggregate Root。

この ``__init__`` はパブリック表面に加え、テストが直接呼ぶ必要のある
アンダースコア プレフィックス ヘルパも再 export する（Norman が agent
パッケージで承認したのと同じパターン）。
"""

from __future__ import annotations

from bakufu.domain.room.aggregate_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_MEMBERS,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    _validate_description_length,
    _validate_member_capacity,
    _validate_member_unique,
    _validate_name_range,
)
from bakufu.domain.room.room import Room
from bakufu.domain.room.value_objects import (
    PROMPT_KIT_PREFIX_MAX,
    AgentMembership,
    PromptKit,
)

__all__ = [
    "MAX_DESCRIPTION_LENGTH",
    "MAX_MEMBERS",
    "MAX_NAME_LENGTH",
    "MIN_NAME_LENGTH",
    "PROMPT_KIT_PREFIX_MAX",
    "AgentMembership",
    "PromptKit",
    "Room",
    "_validate_description_length",
    "_validate_member_capacity",
    "_validate_member_unique",
    "_validate_name_range",
]
