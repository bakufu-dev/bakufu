"""MaskingGateway 単体テスト（TC-UT-PF-006 / 016 / 017 / 018 / 019 / 041 / 042）。

REQ-PF-005（masking ゲートウェイの単一化）+ Confirmation A の 9 種の正規表現
+ Confirmation F の Fail-Secure 契約をカバーする。ゲートウェイは
**決して例外を投げてはならない** — 内部失敗時は生バイトを漏らす代わりに
``<REDACTED:*>`` センチネルへフォールバックする。
"""

from __future__ import annotations

import pytest
from bakufu.infrastructure.security import masking


@pytest.fixture(autouse=True)
def _initialize_masking(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ホームパステストを決定的にするため、HOME を既知値に固定して masking を再初期化する。"""
    monkeypatch.setenv("HOME", "/home/myuser")
    # ホスト由来の provider 環境変数をすべて剥がし、テストはクリーンな
    # Layer-1 リストに対してのみアサートする。
    for env_key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(env_key, raising=False)
    masking.init()


class TestNineRegexPatterns:
    """TC-UT-PF-006 / 042: 9 種類のシークレットフォーマットそれぞれが redact される。"""

    @pytest.mark.parametrize(
        ("payload", "expected_redaction"),
        [
            ("sk-ant-api03-" + "A" * 50, "<REDACTED:ANTHROPIC_KEY>"),
            ("sk-" + "A" * 30, "<REDACTED:OPENAI_KEY>"),
            ("ghp_" + "X" * 36, "<REDACTED:GITHUB_PAT>"),
            ("github_pat_" + "y" * 82, "<REDACTED:GITHUB_PAT>"),
            ("AKIA1234567890ABCDEF", "<REDACTED:AWS_ACCESS_KEY>"),
            (
                "aws_secret_access_key=" + "k" * 40,
                "<REDACTED:AWS_SECRET>",
            ),
            ("xoxb-1234567890-token-data", "<REDACTED:SLACK_TOKEN>"),
            (
                "M" + "z" * 23 + "." + "abcdef" + "." + "u" * 27,
                "<REDACTED:DISCORD_TOKEN>",
            ),
            (
                "Authorization: Bearer eyJ.tokenpart.signature",
                "<REDACTED:BEARER>",
            ),
        ],
    )
    def test_each_regex_pattern_redacts(self, payload: str, expected_redaction: str) -> None:
        """TC-UT-PF-042: 9 種すべての regex ファミリに対するパラメタライズ。"""
        masked = masking.mask(payload)
        assert expected_redaction in masked


class TestApplicationOrder:
    """TC-UT-PF-016: Anthropic regex は OpenAI regex より先に適用される。"""

    def test_anthropic_key_does_not_become_openai_redaction(self) -> None:
        """TC-UT-PF-016: 'sk-ant-...' は ANTHROPIC として redact され、OPENAI にはならない。"""
        ant_key = "sk-ant-api03-" + "A" * 60
        masked = masking.mask(f"key={ant_key}")
        assert "<REDACTED:ANTHROPIC_KEY>" in masked
        assert "<REDACTED:OPENAI_KEY>" not in masked

    def test_openai_key_does_not_match_anthropic(self) -> None:
        """TC-UT-PF-016: 素の 'sk-...' は OPENAI として redact される（ANTHROPIC ではない）。"""
        oai_key = "sk-" + "B" * 40
        masked = masking.mask(f"key={oai_key}")
        assert "<REDACTED:OPENAI_KEY>" in masked
        assert "<REDACTED:ANTHROPIC_KEY>" not in masked


class TestEnvLengthFloor:
    """TC-UT-PF-017: 8 文字未満の env 値はパターン化されない。"""

    def test_short_env_value_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-PF-017: 5 文字の ANTHROPIC_API_KEY は無視される。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "short")
        masking.init()
        # 'short' は redact されてはならない。9 種の regex / home パスのみが発火する。
        masked = masking.mask("plain text containing short value")
        assert "short" in masked
        assert "<REDACTED:ENV:ANTHROPIC_API_KEY>" not in masked

    def test_eight_char_env_value_is_patternized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-PF-017: 8 文字の値は env レイヤに到達する。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "12345678")
        masking.init()
        masked = masking.mask("contains 12345678 secret")
        assert "<REDACTED:ENV:ANTHROPIC_API_KEY>" in masked
        assert "12345678" not in masked


class TestFailSecureFallback:
    """TC-UT-PF-018 / 006-A / 006-B: Confirmation F の失敗パス向けセンチネル。"""

    def test_non_str_input_is_coerced_or_redacted(self) -> None:
        """TC-UT-PF-018: bytes ペイロードは masking 前に str() で変換される。"""
        masked = masking.mask(b"raw bytes data")
        assert isinstance(masked, str)

    def test_oversized_value_returns_overflow_sentinel(self) -> None:
        """TC-UT-PF-006-B: MAX_BYTES_FOR_RECURSION を超える個別値は MASK_OVERFLOW へ。

        オーバーフローガードは再帰フレームごとに走る。dict のオーバーヘッドは
        小さいので dict 自体は dict のまま残るが、中の巨大文字列値はオー
        バーフローセンチネルに置換される。どちらの経路も Fail-Secure であり、
        生バイトは漏れない。
        """
        huge = "x" * (masking.MAX_BYTES_FOR_RECURSION + 1)
        wrapped = {"k": huge}
        result = masking.mask_in(wrapped)
        # dict またはその値が置換される。どちらの形でも Fail-Secure 契約を
        # 満たす（生バイトは漏れない）。
        if isinstance(result, dict):
            assert result["k"] == masking.REDACT_MASK_OVERFLOW
        else:
            assert result == masking.REDACT_MASK_OVERFLOW

    def test_oversized_string_directly_returns_overflow_sentinel(self) -> None:
        """TC-UT-PF-006-B（直接版）: 巨大なトップレベル文字列も Fail-Secure に倒れる。"""
        huge = "x" * (masking.MAX_BYTES_FOR_RECURSION + 1)
        result = masking.mask_in(huge)
        assert result == masking.REDACT_MASK_OVERFLOW

    def test_recursive_structure_walks_all_levels(self) -> None:
        """TC-UT-PF-019: dict / list のネストを再帰的に走査し、全 str を mask する。"""
        payload = {
            "key": "sk-ant-api03-" + "A" * 50,
            "nested": {"pat": "ghp_" + "X" * 36, "list": ["plain"]},
        }
        masked = masking.mask_in(payload)
        assert isinstance(masked, dict)
        assert "<REDACTED:ANTHROPIC_KEY>" in masked["key"]
        assert "<REDACTED:GITHUB_PAT>" in masked["nested"]["pat"]
        assert masked["nested"]["list"] == ["plain"]


class TestHomePathLayer:
    """TC-UT-PF-041: $HOME 配下の絶対パス → '<HOME>'。"""

    def test_home_path_substitution(self) -> None:
        """TC-UT-PF-041: 'error at /home/myuser/...' が置換される。"""
        masked = masking.mask("error at /home/myuser/.local/share/bakufu/db.sqlite")
        assert "/home/myuser" not in masked
        assert "<HOME>" in masked


class TestFailSecureListenerErrorSentinel:
    """TC-UT-PF-006-C: Listener エラーセンチネルが存在し、公開 import 可能であること。

    実際の listener 失敗パスは統合テスト側でカバーする。catch アームへ
    強制的に倒すには本物の SQLAlchemy listener が必要なため。ここでは
    masking-listener 利用者のためにセンチネル値の契約を凍結するに留める。
    """

    def test_listener_error_sentinel_value(self) -> None:
        """TC-UT-PF-006-C: REDACT_LISTENER_ERROR は文書化されたセンチネル値である。"""
        assert masking.REDACT_LISTENER_ERROR == "<REDACTED:LISTENER_ERROR>"

    def test_mask_error_sentinel_value(self) -> None:
        """TC-UT-PF-006-A: REDACT_MASK_ERROR は設計文言と一致する。"""
        assert masking.REDACT_MASK_ERROR == "<REDACTED:MASK_ERROR>"

    def test_mask_overflow_sentinel_value(self) -> None:
        """TC-UT-PF-006-B: REDACT_MASK_OVERFLOW は設計文言と一致する。"""
        assert masking.REDACT_MASK_OVERFLOW == "<REDACTED:MASK_OVERFLOW>"
