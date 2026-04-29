"""アプリケーション層責務のロック（TC-UT-AG-029 / REQ-AG R1-B）。

要求分析の Confirmation R1-B では、**Empire 内での名前の一意性は
アプリケーションサービスの責務**であり、集約の責務ではない、と定めている。
名前が同じで id が異なる 2 つの Agent はドメイン層で問題なく構築できなければ
ならず、重複チェックは ``AgentService.hire`` に属する。

これらのテストはその契約を固定し、将来のリファクタリングでチェックが
こっそり集約側に移動されることを防ぐ（移動されると「名前一意性が複数層で
防御された」ように見える一方で、層構造の設計を壊してしまうため）。
"""

from __future__ import annotations

from tests.factories.agent import make_agent


class TestNameUniquenessLeftToApplicationLayer:
    """TC-UT-AG-029 — Agent 集約は Empire 内での名前一意性を強制しない。"""

    def test_two_agents_with_same_name_but_different_ids_construct(self) -> None:
        """REQ-AG R1-B: 集約は名前重複を受理する — 一意性は AgentService にある。"""
        a1 = make_agent(name="ダリオ")
        a2 = make_agent(name="ダリオ")
        # 両 Agent ともに構築に成功し、異なる id を持つ
        assert a1.name == a2.name and a1.id != a2.id
