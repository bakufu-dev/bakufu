"""MSG-AG-001〜012 の文言一致テスト（TC-UT-AG-030〜037 / 045）。

各違反 kind は detailed-design.md §MSG の静的文字列テンプレートに対応している。
テストではメッセージを **完全一致** で検証し、将来の i18n / リファクタリングで
運用者向けの文言がこっそりずれないようにする。
"""

from __future__ import annotations

import pytest
from bakufu.domain.agent import Persona
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)


class TestMessageWording:
    """MSG-AG の文言一致（TC-UT-AG-030〜037 / 045）。"""

    def test_msg_ag_001_for_oversized_name(self) -> None:
        """TC-UT-AG-030: MSG-AG-001 の文言が '[FAIL] Agent name ...' と一致する。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(name="a" * 41)
        assert excinfo.value.message == "[FAIL] Agent name must be 1-40 characters (got 41)"

    def test_msg_ag_002_for_no_provider(self) -> None:
        """TC-UT-AG-031: MSG-AG-002 'Agent must have at least one provider' の確認。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=[])
        assert excinfo.value.message == "[FAIL] Agent must have at least one provider"

    def test_msg_ag_003_for_zero_defaults(self) -> None:
        """TC-UT-AG-032（count=0）: MSG-AG-003 の文言が got 0 を含む。"""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=False),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert (
            excinfo.value.message == "[FAIL] Exactly one provider must have is_default=True (got 0)"
        )

    def test_msg_ag_003_for_two_defaults(self) -> None:
        """TC-UT-AG-032（count=2）: MSG-AG-003 の文言が got 2 を含む。"""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=True),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert (
            excinfo.value.message == "[FAIL] Exactly one provider must have is_default=True (got 2)"
        )

    def test_msg_ag_004_for_duplicate_provider_kind(self) -> None:
        """TC-UT-AG-033: MSG-AG-004 の文言に重複した provider_kind が含まれる。"""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(
                provider_kind=ProviderKind.CLAUDE_CODE, model="opus", is_default=False
            ),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert "Duplicate provider_kind" in excinfo.value.message
        assert "CLAUDE_CODE" in excinfo.value.message

    def test_msg_ag_005_for_oversized_prompt_body(self) -> None:
        """TC-UT-AG-034: MSG-AG-005 の文言が 10001 文字の prompt_body を報告する。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            Persona(display_name="p", prompt_body="a" * 10_001)
        assert (
            excinfo.value.message
            == "[FAIL] Persona.prompt_body must be 0-10000 characters (got 10001)"
        )

    def test_msg_ag_006_for_unknown_provider_in_set_default(self) -> None:
        """TC-UT-AG-035: MSG-AG-006 の文言に未登録 provider_kind が含まれる。"""
        agent = make_agent()
        with pytest.raises(AgentInvariantViolation) as excinfo:
            agent.set_default_provider(ProviderKind.GEMINI)
        assert excinfo.value.message == "[FAIL] provider_kind not registered: GEMINI"

    def test_msg_ag_007_for_duplicate_skill_id(self) -> None:
        """TC-UT-AG-036: MSG-AG-007 の文言に重複した skill_id が含まれる。"""
        skill = make_skill_ref()
        agent = make_agent(skills=[skill])
        with pytest.raises(AgentInvariantViolation) as excinfo:
            agent.add_skill(make_skill_ref(skill_id=skill.skill_id, name="dup"))
        assert excinfo.value.message == f"[FAIL] Skill already added: skill_id={skill.skill_id}"

    def test_msg_ag_008_for_remove_unknown_skill(self) -> None:
        """TC-UT-AG-037: MSG-AG-008 の文言に存在しない skill_id が含まれる。"""
        from uuid import uuid4

        agent = make_agent()
        unknown = uuid4()
        with pytest.raises(AgentInvariantViolation) as excinfo:
            agent.remove_skill(unknown)
        assert excinfo.value.message == f"[FAIL] Skill not found in agent: skill_id={unknown}"

    def test_msg_ag_skill_path_invalid_prefix(self) -> None:
        """TC-UT-AG-045: skill_path_invalid のメッセージが共通のプレフィックスで始まる。"""
        from uuid import uuid4

        from bakufu.domain.agent import SkillRef

        with pytest.raises(AgentInvariantViolation) as excinfo:
            SkillRef(skill_id=uuid4(), name="x", path="/etc/passwd")
        assert excinfo.value.message.startswith("[FAIL] SkillRef.path validation failed")
        assert excinfo.value.kind == "skill_path_invalid"
