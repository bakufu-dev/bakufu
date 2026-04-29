"""Task Aggregate Root パッケージ。

``docs/features/task`` に従って ``REQ-TS-001``〜``REQ-TS-009`` を実装する。
M1 6 兄弟目（empire / workflow / agent / room / directive の後）。設計が指摘する
責務境界に沿ってパッケージを分割する:

* :mod:`bakufu.domain.task.state_machine` — decision-table state machine
  （``Final[Mapping]`` + :class:`types.MappingProxyType`、§確定 B）。
  §確定 A-2 ディスパッチ表と 1:1 で対応する 13 エントリ。
* :mod:`bakufu.domain.task.aggregate_validators` — 構造的不変条件
  （§確定 J kinds 3〜7）のためのモジュール レベル ``_validate_*`` ヘルパ 5 つ。
* :mod:`bakufu.domain.task.task` — state machine アクション名と 1:1 対応する
  10 個の振る舞いメソッドを公開する :class:`Task` Aggregate Root（§確定 A-2 Steve
  R2 凍結 — 内部ディスパッチ無し、``advance(...)`` umbrella メソッド無し）。

この ``__init__`` はパブリック表面に加え、テストが直接呼ぶ必要のあるアンダー
スコア プレフィックス バリデータも再 export する（Norman が agent / room /
directive パッケージで承認したのと同じパターン）。
"""

from __future__ import annotations

from bakufu.domain.task.aggregate_validators import (
    MAX_ASSIGNED_AGENTS,
    MAX_LAST_ERROR_LENGTH,
    MIN_LAST_ERROR_LENGTH,
    _validate_assigned_agents_capacity,
    _validate_assigned_agents_unique,
    _validate_blocked_has_last_error,
    _validate_last_error_consistency,
    _validate_timestamp_order,
)
from bakufu.domain.task.state_machine import (
    TRANSITIONS,
    TaskAction,
    allowed_actions_from,
    lookup,
)
from bakufu.domain.task.task import Task

__all__ = [
    "MAX_ASSIGNED_AGENTS",
    "MAX_LAST_ERROR_LENGTH",
    "MIN_LAST_ERROR_LENGTH",
    "TRANSITIONS",
    "Task",
    "TaskAction",
    "_validate_assigned_agents_capacity",
    "_validate_assigned_agents_unique",
    "_validate_blocked_has_last_error",
    "_validate_last_error_consistency",
    "_validate_timestamp_order",
    "allowed_actions_from",
    "lookup",
]
