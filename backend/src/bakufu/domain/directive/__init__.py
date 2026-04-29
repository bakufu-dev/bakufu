"""Directive Aggregate Root パッケージ。

``docs/features/directive`` に従って ``REQ-DR-001``〜``REQ-DR-003`` を実装する。
M1 5 兄弟目（empire / workflow / agent / room の後）— 設計上スリム: 5 属性、
2 構造的不変条件、1 振る舞い。すべて 1 ファイルに快適に収まるが、過去の M1
パッケージとの整合性のために 2 つの兄弟モジュールに分割する:

* :mod:`bakufu.domain.directive.aggregate_validators` — モジュール レベルの
  不変条件ヘルパ 2 つ（``_validate_text_range`` /
  ``_validate_task_link_immutable``）。
* :mod:`bakufu.domain.directive.directive` — :class:`Directive` Aggregate Root。

この ``__init__`` はパブリック表面に加え、テストが直接呼ぶ必要のある
アンダースコア プレフィックス ヘルパも再 export する（Norman が agent / room
パッケージで承認したのと同じパターン）。
"""

from __future__ import annotations

from bakufu.domain.directive.aggregate_validators import (
    MAX_TEXT_LENGTH,
    MIN_TEXT_LENGTH,
    _validate_task_link_immutable,
    _validate_text_range,
)
from bakufu.domain.directive.directive import Directive

__all__ = [
    "MAX_TEXT_LENGTH",
    "MIN_TEXT_LENGTH",
    "Directive",
    "_validate_task_link_immutable",
    "_validate_text_range",
]
