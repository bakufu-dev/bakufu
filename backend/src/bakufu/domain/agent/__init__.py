"""Agent Aggregate Root パッケージ。

``docs/features/agent`` に従って ``REQ-AG-001``〜``REQ-AG-006`` を実装する。
設計の責務境界に沿って 4 つの兄弟モジュールに分割し、各ファイルが 500 行の
可読性予算を下回るようにし、ファイル レベル境界が設計の twin-defense パターン
（Stage の自己チェック vs Aggregate のコレクション チェック）を踏襲する:

* :mod:`bakufu.domain.agent.value_objects` — :class:`Persona` /
  :class:`ProviderConfig` / :class:`SkillRef` の Pydantic VO（自己チェック付き）。
* :mod:`bakufu.domain.agent.path_validators` — ``SkillRef.path`` の H1〜H10
  パス トラバーサル防御（Confirmation H）。各ルールは純粋関数。
* :mod:`bakufu.domain.agent.aggregate_validators` — provider 容量 / 一意性 /
  default 個数、および skill 容量 / 一意性を網羅するモジュール レベルの不変
  条件ヘルパ 5 つ。
* :mod:`bakufu.domain.agent.agent` — ヘルパを決定的順序でディスパッチする
  :class:`Agent` Aggregate Root。

この ``__init__`` はパブリック表面に加え、テストが直接呼ぶ必要のある
アンダースコア プレフィックス ヘルパも再 export する。
"""

from __future__ import annotations

from bakufu.domain.agent.agent import (
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    Agent,
)
from bakufu.domain.agent.aggregate_validators import (
    MAX_PROVIDERS,
    MAX_SKILLS,
    MIN_PROVIDERS,
    _validate_default_provider_count,
    _validate_provider_capacity,
    _validate_provider_kind_unique,
    _validate_skill_capacity,
    _validate_skill_id_unique,
)
from bakufu.domain.agent.path_validators import (
    MAX_PATH_LENGTH,
    MIN_PATH_LENGTH,
    REQUIRED_PARTS_PREFIX,
    SKILLS_SUBDIR,
    _h1_nfc_normalize,
    _h2_check_length,
    _h3_check_forbidden_chars,
    _h4_check_leading,
    _h5_check_traversal_sequences,
    _h6_parse_parts,
    _h7_check_prefix,
    _h8_recheck_parts,
    _h9_check_windows_reserved,
    _h10_check_base_escape,
    _validate_skill_path,
)
from bakufu.domain.agent.value_objects import (
    ARCHETYPE_MAX,
    DISPLAY_NAME_MAX,
    DISPLAY_NAME_MIN,
    PROMPT_BODY_MAX,
    PROVIDER_MODEL_MAX,
    PROVIDER_MODEL_MIN,
    SKILL_NAME_MAX,
    SKILL_NAME_MIN,
    Persona,
    ProviderConfig,
    SkillRef,
)

__all__ = [
    "ARCHETYPE_MAX",
    "DISPLAY_NAME_MAX",
    "DISPLAY_NAME_MIN",
    "MAX_NAME_LENGTH",
    "MAX_PATH_LENGTH",
    "MAX_PROVIDERS",
    "MAX_SKILLS",
    "MIN_NAME_LENGTH",
    "MIN_PATH_LENGTH",
    "MIN_PROVIDERS",
    "PROMPT_BODY_MAX",
    "PROVIDER_MODEL_MAX",
    "PROVIDER_MODEL_MIN",
    "REQUIRED_PARTS_PREFIX",
    "SKILLS_SUBDIR",
    "SKILL_NAME_MAX",
    "SKILL_NAME_MIN",
    "Agent",
    "Persona",
    "ProviderConfig",
    "SkillRef",
    "_h1_nfc_normalize",
    "_h2_check_length",
    "_h3_check_forbidden_chars",
    "_h4_check_leading",
    "_h5_check_traversal_sequences",
    "_h6_parse_parts",
    "_h7_check_prefix",
    "_h8_recheck_parts",
    "_h9_check_windows_reserved",
    "_h10_check_base_escape",
    "_validate_default_provider_count",
    "_validate_provider_capacity",
    "_validate_provider_kind_unique",
    "_validate_skill_capacity",
    "_validate_skill_id_unique",
    "_validate_skill_path",
]
