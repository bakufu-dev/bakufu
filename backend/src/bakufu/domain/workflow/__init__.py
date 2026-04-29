"""Workflow Aggregate Root パッケージ。

``docs/features/workflow`` に従って ``REQ-WF-001``〜``REQ-WF-007`` を実装する。
設計の責務境界に沿って 3 つの兄弟モジュールに分割し、各ファイルが 500 行の
可読性予算を下回るようにし、ファイル レベル境界が Confirmation F の twin-defense
を踏襲する:

* :mod:`bakufu.domain.workflow.entities` — :class:`Stage` / :class:`Transition`
  の Pydantic モデル（**自己** 不変条件のみ）。
* :mod:`bakufu.domain.workflow.dag_validators` — **コレクション** 不変条件
  （DAG、一意性、容量）を強制するモジュール レベルの純粋ヘルパ関数 10 個。
* :mod:`bakufu.domain.workflow.workflow` — ヘルパを決定的順序でディスパッチする
  :class:`Workflow` Aggregate Root。

この ``__init__`` はパブリック表面に加え、テスト（TC-UT-WF-060）が直接呼ぶ
必要のある ``_validate_*`` ヘルパも再 export する。先頭アンダースコアは技術的に
import 可能だが「Aggregate に対してプライベート」の意図を明確に保つために維持
する。
"""

from __future__ import annotations

from bakufu.domain.workflow.dag_validators import (
    MAX_NAME_LENGTH,
    MAX_STAGES,
    MAX_TRANSITIONS,
    MIN_NAME_LENGTH,
    _validate_capacity,
    _validate_dag_reachability,
    _validate_dag_sink_exists,
    _validate_entry_in_stages,
    _validate_external_review_notify,
    _validate_required_role_non_empty,
    _validate_stage_id_unique,
    _validate_transition_determinism,
    _validate_transition_id_unique,
    _validate_transition_refs,
)
from bakufu.domain.workflow.entities import Stage, Transition
from bakufu.domain.workflow.workflow import Workflow

__all__ = [
    "MAX_NAME_LENGTH",
    "MAX_STAGES",
    "MAX_TRANSITIONS",
    "MIN_NAME_LENGTH",
    "Stage",
    "Transition",
    "Workflow",
    "_validate_capacity",
    "_validate_dag_reachability",
    "_validate_dag_sink_exists",
    "_validate_entry_in_stages",
    "_validate_external_review_notify",
    "_validate_required_role_non_empty",
    "_validate_stage_id_unique",
    "_validate_transition_determinism",
    "_validate_transition_id_unique",
    "_validate_transition_refs",
]
