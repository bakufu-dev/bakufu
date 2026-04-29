"""アーカイブ冪等性（REQ-AG-005 / Confirmation D）。

TC-UT-AG-010 / 020 / 025 をカバーする。``archive()`` が常に *新しい* インスタンス
を返すという契約は ``is`` 比較で明示的に検証され、将来の「アーカイブ済みなら
スキップ」のような最適化で identity ベースのキャッシュが密かに入り込むことを
防ぐ。
"""

from __future__ import annotations

from tests.factories.agent import make_agent, make_archived_agent


class TestArchiveBasic:
    """TC-UT-AG-010 — archive で archived=True に切り替わる。"""

    def test_archive_returns_archived_true(self) -> None:
        """TC-UT-AG-010: archive() は返す Agent の archived を True に切り替える。"""
        agent = make_agent()
        archived = agent.archive()
        assert archived.archived is True

    def test_archive_does_not_mutate_original(self) -> None:
        """TC-UT-AG-010: 元の Agent は archived=False のまま維持される。"""
        agent = make_agent()
        agent.archive()
        assert agent.archived is False


class TestArchiveIdempotency:
    """TC-UT-AG-020 / 025 — 冪等性 = 状態の等価性。オブジェクト同一性ではない。"""

    def test_archive_on_already_archived_does_not_raise(self) -> None:
        """TC-UT-AG-020: archived=True の Agent への archive() は成功（例外なし）。"""
        agent = make_archived_agent()
        result = agent.archive()  # 例外を送出してはならない
        assert result.archived is True

    def test_archive_on_already_archived_returns_new_instance(self) -> None:
        """TC-UT-AG-020 / Confirmation D: archive() は常に新しいインスタンスを返す。

        ``a1 is a2`` は False でなければならない — Confirmation D は
        オブジェクト同一性キャッシュを禁じている。冪等性は「結果の状態が一致する」
        ことで定義され、次のテストの構造的等価アサーションで証明される。
        """
        agent = make_archived_agent()
        result = agent.archive()
        assert result is not agent

    def test_archive_on_already_archived_is_structurally_equal(self) -> None:
        """TC-UT-AG-020: 冗長な archive() の結果は元のアーカイブ済み Agent と == である。"""
        agent = make_archived_agent()
        result = agent.archive()
        assert result == agent  # フィールドは同一、identity は異なる

    def test_three_consecutive_archive_calls_yield_archived_true(self) -> None:
        """TC-UT-AG-025: archive().archive().archive() 全てで archived=True を維持。"""
        agent = make_agent()
        a1 = agent.archive()
        a2 = a1.archive()
        a3 = a2.archive()
        assert a1.archived is True and a2.archived is True and a3.archived is True

    def test_three_consecutive_archive_calls_each_yield_distinct_instance(self) -> None:
        """TC-UT-AG-025: 各 archive() 呼び出しは別個のオブジェクト identity を返す。"""
        agent = make_agent()
        a1 = agent.archive()
        a2 = a1.archive()
        a3 = a2.archive()
        assert a1 is not a2 and a2 is not a3 and a1 is not a3
