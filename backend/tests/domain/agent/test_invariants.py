"""集約レベルの不変条件（REQ-AG-001 / 005 / 006）。

TC-UT-AG-003 / 004 / 013〜015 / 018 / 021 をカバーする。各不変条件は専用の
``Test*`` クラスに置かれ、どのコレクション契約が破られたかで失敗がクラスタ化
されるようにしている。容量超過の経路は、既に構築されたコレクションをヘルパに
渡したいときに Agent コンストラクタの即時 Pydantic 検証を回避するため
``model_construct`` を用いる。
"""

from __future__ import annotations

import pytest
from bakufu.domain.agent.aggregate_validators import MAX_PROVIDERS, MAX_SKILLS
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)


class TestProvidersRequired:
    """TC-UT-AG-013 — providers は少なくとも 1 件含まなければならない。"""

    def test_empty_providers_raises_no_provider(self) -> None:
        """TC-UT-AG-013: providers=[] は no_provider を送出する。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=[])
        assert excinfo.value.kind == "no_provider"


class TestProviderCapacity:
    """TC-UT-AG-014 — providers ≤ MAX_PROVIDERS（Confirmation C）。"""

    def test_overflow_raises_provider_capacity_exceeded(self) -> None:
        """TC-UT-AG-014: 11 providers で provider_capacity_exceeded を送出する。"""
        # is_default=False を 10 件 + is_default=True を 1 件にして、
        # デフォルト数ヘルパが（容量チェックの後に走るので）通るようにする
        providers = [
            make_provider_config(provider_kind=kind, is_default=False)
            for kind in list(ProviderKind)[:6]
        ]
        # model 文字列を変えて MAX_PROVIDERS を超える重複を追加
        # （MAX_PROVIDERS 超のエントリ数が必要なだけ。provider_kind の一意性チェックでも
        # 検知されるが、capacity の方が先に走る）
        providers.extend(
            make_provider_config(
                provider_kind=ProviderKind.CLAUDE_CODE,
                model=f"sonnet-{i}",
                is_default=False,
            )
            for i in range(MAX_PROVIDERS - 5)  # MAX を超えるまで埋める
        )
        # デフォルトが少なくとも 1 件必要 — 追加する
        providers.append(make_provider_config(is_default=True))
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "provider_capacity_exceeded"


class TestProviderKindUnique:
    """TC-UT-AG-015 — provider_kind は providers 全体で一意でなければならない。"""

    def test_duplicate_provider_kind_raises_provider_duplicate(self) -> None:
        """TC-UT-AG-015: 同一 provider_kind の ProviderConfig 2 件は例外を送出する。"""
        p1 = make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True)
        p2 = make_provider_config(
            provider_kind=ProviderKind.CLAUDE_CODE, model="opus", is_default=False
        )
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=[p1, p2])
        assert excinfo.value.kind == "provider_duplicate"


class TestDefaultProviderCount:
    """TC-UT-AG-003 / 004 / 021 — is_default=True はちょうど 1 件。"""

    def test_zero_defaults_raises_default_not_unique(self) -> None:
        """TC-UT-AG-003: 全て is_default=False のとき count=0 で default_not_unique。"""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=False),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "default_not_unique"
        assert excinfo.value.detail.get("default_count") == 0

    def test_two_defaults_raises_default_not_unique(self) -> None:
        """TC-UT-AG-004: is_default=True が 2 件のとき count=2 で default_not_unique。"""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=True),
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "default_not_unique"
        assert excinfo.value.detail.get("default_count") == 2

    @pytest.mark.parametrize(
        ("default_flags", "expected_count"),
        [
            ([False, False, False], 0),
            ([True, True, False], 2),
            ([True, True, True], 3),
        ],
    )
    def test_count_outside_one_raises(self, default_flags: list[bool], expected_count: int) -> None:
        """TC-UT-AG-021: デフォルト数 0 / 2 / 3 は全て例外（境界の総当たり）。"""
        kinds = [ProviderKind.CLAUDE_CODE, ProviderKind.CODEX, ProviderKind.GEMINI]
        providers = [
            make_provider_config(provider_kind=kind, is_default=flag)
            for kind, flag in zip(kinds, default_flags, strict=True)
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(providers=providers)
        assert excinfo.value.kind == "default_not_unique"
        assert excinfo.value.detail.get("default_count") == expected_count

    def test_exactly_one_default_succeeds(self) -> None:
        """TC-UT-AG-021: is_default=True がちょうど 1 件の境界成功ケース。"""
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
            make_provider_config(provider_kind=ProviderKind.GEMINI, is_default=False),
        ]
        agent = make_agent(providers=providers)
        defaults = [p for p in agent.providers if p.is_default]
        assert len(defaults) == 1


class TestSkillCapacity:
    """TC-UT-AG-018 — skills ≤ MAX_SKILLS（Confirmation C）。"""

    def test_overflow_raises_skill_capacity_exceeded(self) -> None:
        """TC-UT-AG-018: MAX_SKILLS+1 件で skill_capacity_exceeded を送出する。"""
        skills = [
            make_skill_ref(name=f"skill-{i:02d}", path=f"bakufu-data/skills/s{i:02d}.md")
            for i in range(MAX_SKILLS + 1)
        ]
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(skills=skills)
        assert excinfo.value.kind == "skill_capacity_exceeded"


class TestSkillIdUnique:
    """TC-UT-AG-008 — skill_id は一意でなければならない（stage / transition と同様）。

    Steve PR #16 の対称性: 「id 重複なし」のコレクション契約には全て専用ヘルパを
    用意する。Agent の ``_validate_skill_id_unique`` もそれを踏襲している。
    """

    def test_duplicate_skill_id_raises_skill_duplicate(self) -> None:
        """TC-UT-AG-008: skill_id を共有する 2 件の SkillRef で skill_duplicate。"""
        s1 = make_skill_ref()
        s2 = make_skill_ref(skill_id=s1.skill_id, name="another")
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(skills=[s1, s2])
        assert excinfo.value.kind == "skill_duplicate"
