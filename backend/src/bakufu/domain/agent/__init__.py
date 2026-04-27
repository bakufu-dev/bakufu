"""Agent Aggregate Root package.

Implements ``REQ-AG-001``〜``REQ-AG-006`` per ``docs/features/agent``.
Split into four sibling modules along the design's responsibility lines so
each file stays under the 500-line readability budget and the file-level
boundary mirrors the design's twin-defense pattern (Stage's self-check vs
the aggregate's collection check):

* :mod:`bakufu.domain.agent.value_objects` — :class:`Persona` /
  :class:`ProviderConfig` / :class:`SkillRef` Pydantic VOs with self-checks.
* :mod:`bakufu.domain.agent.path_validators` — H1〜H10 path traversal
  defense for ``SkillRef.path`` (Confirmation H), each rule a pure function.
* :mod:`bakufu.domain.agent.aggregate_validators` — five module-level
  invariant helpers covering provider capacity / uniqueness / default count
  and skill capacity / uniqueness.
* :mod:`bakufu.domain.agent.agent` — :class:`Agent` Aggregate Root that
  dispatches over the helpers in deterministic order.

This ``__init__`` re-exports the public surface plus the underscore-prefixed
helpers tests need to invoke directly.
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
    validate_skill_path,
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
    "validate_skill_path",
]
