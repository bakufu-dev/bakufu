"""集約内ライフサイクル統合（TC-IT-AG-001 / 002）。

``empire`` / ``workflow`` の統合スイートと同じパターン: ドメイン層は
公開エントリポイントを持たないため、集約の mutator チェーン
（set_default_provider → add_skill → remove_skill → archive）を通したラウンド
トリップ動作と、チェーン途中の失敗が元の集約を無傷で残す耐性シナリオを検証する。
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)


class TestAgentLifecycleIntegration:
    """TC-IT-AG-001 / 002 — 全ライフサイクル + 耐性。"""

    def test_full_lifecycle_round_trip(self) -> None:
        """TC-IT-AG-001: hire → add_skill → switch default → remove_skill → archive。

        前提状態: 2 プロバイダの Agent（CLAUDE_CODE がデフォルト + CODEX が非デフォルト）、
        スキル 1 件。mutator チェーンを全部通し、最終形を検証する。
        """
        providers = [
            make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            make_provider_config(provider_kind=ProviderKind.CODEX, is_default=False),
        ]
        skill = make_skill_ref()
        agent = make_agent(providers=providers, skills=[skill])

        # 1) デフォルトを CODEX に切替
        switched = agent.set_default_provider(ProviderKind.CODEX)
        codex = next(p for p in switched.providers if p.provider_kind is ProviderKind.CODEX)
        assert codex.is_default is True

        # 2) スキルを 1 件追加
        new_skill = make_skill_ref(name="planner", path="bakufu-data/skills/planner.md")
        with_two_skills = switched.add_skill(new_skill)
        assert len(with_two_skills.skills) == 2

        # 3) 元のスキルを削除
        with_one_skill = with_two_skills.remove_skill(skill.skill_id)
        assert len(with_one_skill.skills) == 1
        assert with_one_skill.skills[0].skill_id == new_skill.skill_id

        # 4) Agent をアーカイブ — Confirmation D により *新しい* インスタンスを返す
        archived = with_one_skill.archive()
        assert archived.archived is True and archived is not with_one_skill

    def test_failed_set_default_does_not_block_subsequent_operations(self) -> None:
        """TC-IT-AG-002: set_default_provider が失敗しても、後続の変更は可能。"""
        agent = make_agent()

        # 1) 未登録 kind への切替は失敗し、元は変更されない
        with pytest.raises(AgentInvariantViolation):
            agent.set_default_provider(ProviderKind.GEMINI)
        assert len(agent.providers) == 1

        # 2) その後の add_skill は変更されていない集約に対して成功する
        new_skill = make_skill_ref()
        with_skill = agent.add_skill(new_skill)
        assert len(with_skill.skills) == 1

        # 3) さらに変更された集約に対する archive() も成功する
        archived = with_skill.archive()
        assert archived.archived is True
