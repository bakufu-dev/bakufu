"""NotifyChannel SSRF allow list G1〜G10 (Confirmation G)。

TC-UT-WF-034〜036, 048〜054 をカバー。各 ``Test*`` parametrize は
10 の G ルール 1 つをヒット、``NotifyChannel._validate_target`` への
将来の変更が monolithic test モジュール全体に SSRF 契約を
散乱させるのではなく、このファイルで焦点 diff を生成することを保証。
"""

from __future__ import annotations

import pytest
from bakufu.domain.value_objects import NotifyChannel
from pydantic import ValidationError


class TestNotifyChannelSSRF:
    """TC-UT-WF-034〜036, 048〜054 — 完全 G1〜G10 拒否カバレッジ。"""

    @pytest.mark.parametrize(
        "bad_target",
        [
            # G3: HTTPS 強制
            "http://discord.com/api/webhooks/123/abc-DEF_xyz",
        ],
    )
    def test_034_https_only(self, bad_target: str) -> None:
        """TC-UT-WF-034 / G3: scheme は 'https' 必須。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com.evil.example/api/webhooks/123/abc",
            "https://evil-discord.com/api/webhooks/123/abc",
            "https://api.discord.com/api/webhooks/123/abc",
        ],
    )
    def test_035_hostname_exact_match(self, bad_target: str) -> None:
        """TC-UT-WF-035 / G4: hostname は 'discord.com' に正確に一致必須。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com/",
            "https://discord.com/api/webhooks/",
        ],
    )
    def test_036_path_must_be_present(self, bad_target: str) -> None:
        """TC-UT-WF-036 / G7: path は /api/webhooks/<id>/<token> に一致必須。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    def test_048_token_at_g7_cap_succeeds_overflow_rejected(self) -> None:
        """TC-UT-WF-048 / G1+G7: 100 文字トークン (G7 キャップ) は機能、101+ は拒否。

        **有効な** Discord webhook URL に対するリアルな上限は G7 経由
        (トークン ≤ 100 文字) で到達。最大許可形は正常に構築、
        あらゆる G7 オーバーフロー トリップ、過大サイズ URL が
        G1 をヒットすることを独立で検証。
        """
        base = "https://discord.com/api/webhooks/123456789/"
        valid = base + "a" * 100  # G7 キャップでトークン
        channel = NotifyChannel(kind="discord", target=valid)
        assert channel.target == valid
        # 101 文字トークンは G7 違反。
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=base + "a" * 101)
        # 500+ 文字 URL も G1 を違反。
        oversized = "https://discord.com/api/webhooks/1/" + "a" * 500
        assert len(oversized) > 500
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=oversized)

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com:80/api/webhooks/123/abc-DEF_xyz",
            "https://discord.com:8443/api/webhooks/123/abc-DEF_xyz",
            "https://discord.com:8080/api/webhooks/123/abc-DEF_xyz",
        ],
    )
    def test_049_port_must_be_none_or_443(self, bad_target: str) -> None:
        """TC-UT-WF-049 / G5: port は {None, 443} に制限。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://attacker@discord.com/api/webhooks/123/abc-DEF_xyz",
            "https://user:pass@discord.com/api/webhooks/123/abc-DEF_xyz",
        ],
    )
    def test_050_userinfo_rejected(self, bad_target: str) -> None:
        """TC-UT-WF-050 / G6: userinfo (ユーザー/パスワード) は拒否。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com/api/webhooks/abc/def",  # id 非数値
            "https://discord.com/api/webhooks/123/!@#",  # トークン不良文字
            "https://discord.com/api/webhooks/" + ("0" * 31) + "/abc",  # id 31 桁
            "https://discord.com/api/webhooks/123/" + ("a" * 101),  # トークン 101 文字
            "https://discord.com/api/webhooks/123/abc/extra",  # 余分パスセグメント
        ],
    )
    def test_051_path_regex_fullmatch(self, bad_target: str) -> None:
        """TC-UT-WF-051 / G7: path regex は /api/webhooks/<id>/<token> に fullmatch 必須。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    def test_052_query_rejected(self) -> None:
        """TC-UT-WF-052 / G8: クエリ文字列は拒否。"""
        with pytest.raises(ValidationError):
            NotifyChannel(
                kind="discord",
                target="https://discord.com/api/webhooks/123/abc?override=x",
            )

    def test_053_fragment_rejected(self) -> None:
        """TC-UT-WF-053 / G9: フラグメントは拒否。"""
        with pytest.raises(ValidationError):
            NotifyChannel(
                kind="discord",
                target="https://discord.com/api/webhooks/123/abc#frag",
            )

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com/API/WEBHOOKS/123/abc",  # 大文字 API/WEBHOOKS
            "https://discord.com/Api/Webhooks/123/abc",  # 混合ケース
        ],
    )
    def test_054_path_case_sensitive(self, bad_target: str) -> None:
        """TC-UT-WF-054 / G10: path は大文字小文字を区別 (小文字 /api/webhooks/ のみ)。"""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)
