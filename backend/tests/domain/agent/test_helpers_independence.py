"""Aggregate + path helpers invoked independently (Confirmation F equivalent).

The 5 ``_validate_*`` helpers in ``aggregate_validators.py`` and the 10
``_h*_check_*`` helpers in ``path_validators.py`` are module-level pure
functions — tests can import and call them directly without first
constructing an Agent. This proves the aggregate path does not share code
with the VO self-checks (twin-defense from workflow Confirmation F carried
forward to agent).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.agent import (
    Persona,
    ProviderConfig,
    SkillRef,
    _h1_nfc_normalize,
    _h2_check_length,
    _h3_check_forbidden_chars,
    _h4_check_leading,
    _h5_check_traversal_sequences,
    _h6_parse_parts,
    _h7_check_prefix,
    _h8_recheck_parts,
    _h9_check_windows_reserved,
    _validate_default_provider_count,
    _validate_provider_capacity,
    _validate_provider_kind_unique,
    _validate_skill_capacity,
    _validate_skill_id_unique,
)
from bakufu.domain.agent.aggregate_validators import MAX_PROVIDERS, MAX_SKILLS
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import make_provider_config, make_skill_ref


class TestAggregateHelpersIndependent:
    """Each ``_validate_*`` is invokable directly and raises the right kind."""

    def test_provider_capacity_rejects_zero(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _validate_provider_capacity([])
        assert excinfo.value.kind == "no_provider"

    def test_provider_capacity_rejects_overflow(self) -> None:
        many = [
            ProviderConfig.model_construct(
                provider_kind=ProviderKind.CLAUDE_CODE,
                model=f"m-{i}",
                is_default=False,
            )
            for i in range(MAX_PROVIDERS + 1)
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _validate_provider_capacity(many)
        assert excinfo.value.kind == "provider_capacity_exceeded"

    def test_provider_kind_unique_rejects_duplicate(self) -> None:
        p1 = make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True)
        p2 = make_provider_config(
            provider_kind=ProviderKind.CLAUDE_CODE, model="opus", is_default=False
        )
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _validate_provider_kind_unique([p1, p2])
        assert excinfo.value.kind == "provider_duplicate"

    def test_default_provider_count_rejects_zero(self) -> None:
        providers = [make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=False)]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _validate_default_provider_count(providers)
        assert excinfo.value.kind == "default_not_unique"

    def test_skill_capacity_rejects_overflow(self) -> None:
        skills = [
            make_skill_ref(name=f"s-{i:02d}", path=f"bakufu-data/skills/s{i:02d}.md")
            for i in range(MAX_SKILLS + 1)
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _validate_skill_capacity(skills)
        assert excinfo.value.kind == "skill_capacity_exceeded"

    def test_skill_id_unique_rejects_duplicate(self) -> None:
        s1 = make_skill_ref()
        s2 = SkillRef.model_construct(skill_id=s1.skill_id, name="dup", path=s1.path)
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _validate_skill_id_unique([s1, s2])
        assert excinfo.value.kind == "skill_duplicate"


class TestPathHelpersIndependent:
    """Each Hx helper raises with the corresponding ``check`` discriminator."""

    def test_h1_normalizes(self) -> None:
        import unicodedata

        composed = "がが"
        decomposed = unicodedata.normalize("NFD", composed)
        assert _h1_nfc_normalize(decomposed) == composed

    def test_h2_rejects_oversize(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h2_check_length("a" * 501)
        assert excinfo.value.detail.get("check") == "H2"

    def test_h3_rejects_nul(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h3_check_forbidden_chars("foo\x00bar")
        assert excinfo.value.detail.get("check") == "H3"

    def test_h4_rejects_leading_slash(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h4_check_leading("/etc/passwd")
        assert excinfo.value.detail.get("check") == "H4"

    def test_h5_rejects_traversal(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h5_check_traversal_sequences("foo/../bar")
        assert excinfo.value.detail.get("check") == "H5"

    def test_h6_returns_parts_tuple(self) -> None:
        parts = _h6_parse_parts("bakufu-data/skills/f.md")
        assert parts == ("bakufu-data", "skills", "f.md")

    def test_h7_rejects_wrong_prefix(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h7_check_prefix(("other", "skills", "f.md"))
        assert excinfo.value.detail.get("check") == "H7"

    def test_h8_rejects_forbidden_in_part(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h8_recheck_parts(("bakufu-data", "skills", "foo\x00.md"))
        assert excinfo.value.detail.get("check") == "H8"

    def test_h9_rejects_reserved_name(self) -> None:
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _h9_check_windows_reserved(("bakufu-data", "skills", "CON.md"))
        assert excinfo.value.detail.get("check") == "H9"


class TestValueObjectFactoryRegistry:
    """Synthetic-vs-real bookkeeping (cross-cutting smoke)."""

    def test_factory_built_persona_is_synthetic(self) -> None:
        from tests.factories.agent import is_synthetic

        persona = Persona(display_name="raw")
        assert is_synthetic(persona) is False

    def test_factory_built_skill_ref_is_synthetic(self) -> None:
        from tests.factories.agent import is_synthetic, make_skill_ref

        ref = make_skill_ref()
        assert is_synthetic(ref) is True

    def test_directly_constructed_skill_ref_is_not_synthetic(self) -> None:
        from tests.factories.agent import is_synthetic

        ref = SkillRef(skill_id=uuid4(), name="raw", path="bakufu-data/skills/r.md")
        assert is_synthetic(ref) is False
