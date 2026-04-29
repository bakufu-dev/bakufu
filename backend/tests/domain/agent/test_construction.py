"""構築と名前の正規化（TC-UT-AG-001 / 002 / 012 / 030）。

REQ-AG-001 の最小契約と、empire / workflow と共通の NFC + strip パイプラインを
カバーする。
"""

from __future__ import annotations

import unicodedata

import pytest
from bakufu.domain.exceptions import AgentInvariantViolation

from tests.factories.agent import make_agent


class TestAgentConstruction:
    """REQ-AG-001 / TC-UT-AG-001 — Agent の最小契約。"""

    def test_default_factory_yields_one_provider_no_skills(self) -> None:
        """TC-UT-AG-001: ファクトリで生成した Agent は provider=1、skill=0、archived=False。"""
        agent = make_agent()
        assert len(agent.providers) == 1 and len(agent.skills) == 0 and agent.archived is False


class TestAgentNameBoundaries:
    """REQ-AG-001 / TC-UT-AG-002 — name の長さ 1〜40。"""

    @pytest.mark.parametrize("valid_length", [1, 40])
    def test_accepts_lower_and_upper_boundary(self, valid_length: int) -> None:
        """TC-UT-AG-002: 1 文字・40 文字の name は構築に成功する。"""
        agent = make_agent(name="a" * valid_length)
        assert len(agent.name) == valid_length

    @pytest.mark.parametrize("invalid_name", ["", "a" * 41, "   "])
    def test_rejects_zero_fortyone_or_whitespace_only(self, invalid_name: str) -> None:
        """TC-UT-AG-002: 0 文字 / 41 文字 / 空白のみの name は例外を送出する。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            make_agent(name=invalid_name)
        assert excinfo.value.kind == "name_range"


class TestAgentNameNormalization:
    """TC-UT-AG-012 — empire / workflow と共通の NFC + strip パイプライン。"""

    def test_decomposed_kana_normalized_to_nfc(self) -> None:
        """TC-UT-AG-012: 濁点付き分解形カナ（例 'がが'）が正規化される。"""
        composed = "がが"
        decomposed = unicodedata.normalize("NFD", composed)
        assert decomposed != composed  # sanity チェック
        agent = make_agent(name=decomposed)
        assert agent.name == composed

    def test_surrounding_whitespace_stripped(self) -> None:
        """TC-UT-AG-012: 先頭・末尾の空白は除去される。"""
        agent = make_agent(name="  ダリオ  ")
        assert agent.name == "ダリオ"
