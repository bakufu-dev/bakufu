"""frozen=True / extra='forbid' の不変条件（TC-UT-AG-026 / 027 / 011）。

Pydantic v2 の frozen 契約が、全集約 / VO 面で構築後の変更を物理的に阻止する
こと、およびペイロードの未知フィールドが集約バリデーション実行前に拒否される
ことを検証する。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.agent import Agent, ProviderConfig, SkillRef
from bakufu.domain.value_objects import ProviderKind, Role
from pydantic import ValidationError

from tests.factories.agent import (
    make_agent,
    make_persona,
    make_provider_config,
    make_skill_ref,
)


class TestFrozenContract:
    """TC-UT-AG-026 — Agent / Persona / ProviderConfig / SkillRef の frozen 性。"""

    def test_agent_rejects_attribute_assignment(self) -> None:
        agent = make_agent()
        with pytest.raises(ValidationError):
            agent.name = "改竄"  # type: ignore[misc]

    def test_persona_rejects_attribute_assignment(self) -> None:
        persona = make_persona()
        with pytest.raises(ValidationError):
            persona.archetype = "違う"  # type: ignore[misc]

    def test_provider_config_rejects_attribute_assignment(self) -> None:
        config = make_provider_config()
        with pytest.raises(ValidationError):
            config.is_default = False  # type: ignore[misc]

    def test_skill_ref_rejects_attribute_assignment(self) -> None:
        skill = make_skill_ref()
        with pytest.raises(ValidationError):
            skill.name = "改竄"  # type: ignore[misc]


class TestStructuralEquality:
    """TC-UT-AG-011 — VO は構造的等価性とハッシュを用いる。"""

    def test_two_personas_with_identical_fields_compare_equal(self) -> None:
        a = make_persona(display_name="reviewer", archetype="r", prompt_body="p")
        b = make_persona(display_name="reviewer", archetype="r", prompt_body="p")
        assert a == b

    def test_two_provider_configs_with_identical_fields_compare_equal(self) -> None:
        a = make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, model="x", is_default=True)
        b = make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, model="x", is_default=True)
        assert a == b


class TestExtraForbid:
    """TC-UT-AG-027 — extra='forbid' は未知フィールドを拒否する。"""

    def test_agent_model_validate_rejects_unknown_field(self) -> None:
        """Agent.model_validate は未知キーを含むペイロードを拒否する。"""
        payload: dict[str, object] = {
            "id": str(uuid4()),
            "name": "ok",
            "persona": {
                "display_name": "p",
                "archetype": "",
                "prompt_body": "",
            },
            "role": Role.DEVELOPER.value,
            "providers": [
                {
                    "provider_kind": ProviderKind.CLAUDE_CODE.value,
                    "model": "sonnet",
                    "is_default": True,
                }
            ],
            "skills": [],
            "archived": False,
            "unknown_field": "should-be-rejected",
        }
        with pytest.raises(ValidationError):
            Agent.model_validate(payload)

    def test_provider_config_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            ProviderConfig.model_validate(
                {
                    "provider_kind": ProviderKind.CLAUDE_CODE.value,
                    "model": "x",
                    "is_default": True,
                    "unknown": "x",
                }
            )

    def test_skill_ref_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            SkillRef.model_validate(
                {
                    "skill_id": str(uuid4()),
                    "name": "x",
                    "path": "bakufu-data/skills/x.md",
                    "unknown": "x",
                }
            )
