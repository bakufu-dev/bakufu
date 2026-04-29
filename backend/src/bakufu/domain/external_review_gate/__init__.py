"""ExternalReviewGate Aggregate Root パッケージ。

``docs/features/external-review-gate`` に従って ``REQ-GT-001``〜``REQ-GT-007`` を
実装する。M1 7 兄弟目 — **最後** の M1 Aggregate であり、ドメイン スケルトン
を完成させる（empire / workflow / agent / room / directive / task の後）。
設計が指摘する責務境界に沿ってパッケージを分割する:

* :mod:`bakufu.domain.external_review_gate.state_machine` — decision-table
  state machine（``Final[Mapping]`` + :class:`types.MappingProxyType`、§確定 B）。
  §確定 A の 4 x 4 ディスパッチ表と 1:1 で対応する 7 エントリ。
* :mod:`bakufu.domain.external_review_gate.aggregate_validators` — 構造的
  不変条件（§確定 J kinds 2〜5、``decision_already_decided`` は state machine
  ルックアップ自体で強制される）のためのモジュール レベル ``_validate_*``
  ヘルパ 4 つ。
* :mod:`bakufu.domain.external_review_gate.gate` — state machine アクション名と
  1:1 対応する 4 個の振る舞いメソッドを公開する :class:`ExternalReviewGate`
  Aggregate Root（§確定 A — task #42 §確定 A-2 パターン継承）。

この ``__init__`` はパブリック表面に加え、テストが直接呼ぶ必要のあるアンダー
スコア プレフィックス バリデータも再 export する（Norman が agent / room /
directive / task パッケージで承認したのと同じパターン）。
"""

from __future__ import annotations

from bakufu.domain.external_review_gate.aggregate_validators import (
    MAX_FEEDBACK_LENGTH,
    MIN_FEEDBACK_LENGTH,
    _validate_audit_trail_append_only,
    _validate_decided_at_consistency,
    _validate_feedback_text_range,
    _validate_snapshot_immutable,
)
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.external_review_gate.state_machine import (
    TRANSITIONS,
    GateAction,
    allowed_actions_from,
    lookup,
)

__all__ = [
    "MAX_FEEDBACK_LENGTH",
    "MIN_FEEDBACK_LENGTH",
    "TRANSITIONS",
    "ExternalReviewGate",
    "GateAction",
    "_validate_audit_trail_append_only",
    "_validate_decided_at_consistency",
    "_validate_feedback_text_range",
    "_validate_snapshot_immutable",
    "allowed_actions_from",
    "lookup",
]
