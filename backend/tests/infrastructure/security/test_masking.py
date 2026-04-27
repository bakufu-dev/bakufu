"""MaskingGateway unit tests (TC-UT-PF-006 / 016 / 017 / 018 / 019 / 041 / 042).

Covers REQ-PF-005 (single masking gateway) + Confirmation A's nine regex
patterns + Confirmation F's Fail-Secure contract. The gateway must
**never raise** — internal failures fall back to ``<REDACTED:*>``
sentinels rather than letting raw bytes escape.
"""

from __future__ import annotations

import pytest
from bakufu.infrastructure.security import masking


@pytest.fixture(autouse=True)
def _initialize_masking(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-init masking with a known HOME so home-path tests are deterministic."""
    monkeypatch.setenv("HOME", "/home/myuser")
    # Strip any provider env vars from the host so tests assert against a
    # clean Layer-1 list.
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
    """TC-UT-PF-006 / 042: each of the nine secret formats is redacted."""

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
        """TC-UT-PF-042: parametrized over all nine regex families."""
        masked = masking.mask(payload)
        assert expected_redaction in masked


class TestApplicationOrder:
    """TC-UT-PF-016: Anthropic regex applies before OpenAI regex."""

    def test_anthropic_key_does_not_become_openai_redaction(self) -> None:
        """TC-UT-PF-016: 'sk-ant-...' is redacted as ANTHROPIC, never OPENAI."""
        ant_key = "sk-ant-api03-" + "A" * 60
        masked = masking.mask(f"key={ant_key}")
        assert "<REDACTED:ANTHROPIC_KEY>" in masked
        assert "<REDACTED:OPENAI_KEY>" not in masked

    def test_openai_key_does_not_match_anthropic(self) -> None:
        """TC-UT-PF-016: plain 'sk-...' redacts as OPENAI, not ANTHROPIC."""
        oai_key = "sk-" + "B" * 40
        masked = masking.mask(f"key={oai_key}")
        assert "<REDACTED:OPENAI_KEY>" in masked
        assert "<REDACTED:ANTHROPIC_KEY>" not in masked


class TestEnvLengthFloor:
    """TC-UT-PF-017: env values shorter than 8 chars are not patternized."""

    def test_short_env_value_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-PF-017: 5-char ANTHROPIC_API_KEY is ignored."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "short")
        masking.init()
        # 'short' must not be redacted — only the 9 regex / home pass should fire.
        masked = masking.mask("plain text containing short value")
        assert "short" in masked
        assert "<REDACTED:ENV:ANTHROPIC_API_KEY>" not in masked

    def test_eight_char_env_value_is_patternized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-PF-017: 8-char value lands in the env layer."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "12345678")
        masking.init()
        masked = masking.mask("contains 12345678 secret")
        assert "<REDACTED:ENV:ANTHROPIC_API_KEY>" in masked
        assert "12345678" not in masked


class TestFailSecureFallback:
    """TC-UT-PF-018 / 006-A / 006-B: confirmation F sentinels for failure paths."""

    def test_non_str_input_is_coerced_or_redacted(self) -> None:
        """TC-UT-PF-018: bytes payload is coerced via str() before masking."""
        masked = masking.mask(b"raw bytes data")
        assert isinstance(masked, str)

    def test_oversized_value_returns_overflow_sentinel(self) -> None:
        """TC-UT-PF-006-B: an individual value above MAX_BYTES_FOR_RECURSION → MASK_OVERFLOW.

        The overflow guard runs per recursion frame: the dict overhead
        is tiny, so the dict itself stays a dict, but the giant string
        value inside gets replaced with the overflow sentinel. Either
        path is Fail-Secure — raw bytes never escape.
        """
        huge = "x" * (masking.MAX_BYTES_FOR_RECURSION + 1)
        wrapped = {"k": huge}
        result = masking.mask_in(wrapped)
        # Either the dict or its value gets replaced; both flavors
        # satisfy the Fail-Secure contract (raw bytes do not leak).
        if isinstance(result, dict):
            assert result["k"] == masking.REDACT_MASK_OVERFLOW
        else:
            assert result == masking.REDACT_MASK_OVERFLOW

    def test_oversized_string_directly_returns_overflow_sentinel(self) -> None:
        """TC-UT-PF-006-B (direct): a giant top-level string also Fail-Secures."""
        huge = "x" * (masking.MAX_BYTES_FOR_RECURSION + 1)
        result = masking.mask_in(huge)
        assert result == masking.REDACT_MASK_OVERFLOW

    def test_recursive_structure_walks_all_levels(self) -> None:
        """TC-UT-PF-019: dict / list nesting recurses and masks every str."""
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
    """TC-UT-PF-041: $HOME absolute path → '<HOME>'."""

    def test_home_path_substitution(self) -> None:
        """TC-UT-PF-041: 'error at /home/myuser/...' gets replaced."""
        masked = masking.mask("error at /home/myuser/.local/share/bakufu/db.sqlite")
        assert "/home/myuser" not in masked
        assert "<HOME>" in masked


class TestFailSecureListenerErrorSentinel:
    """TC-UT-PF-006-C: Listener-error sentinel exists and is publicly importable.

    The actual listener-failure path is exercised in the integration
    tests because it requires a live SQLAlchemy listener that we can
    force into the catch arm. Here we just freeze the sentinel value
    contract for masking-listener consumers.
    """

    def test_listener_error_sentinel_value(self) -> None:
        """TC-UT-PF-006-C: REDACT_LISTENER_ERROR is the documented sentinel."""
        assert masking.REDACT_LISTENER_ERROR == "<REDACTED:LISTENER_ERROR>"

    def test_mask_error_sentinel_value(self) -> None:
        """TC-UT-PF-006-A: REDACT_MASK_ERROR matches the design wording."""
        assert masking.REDACT_MASK_ERROR == "<REDACTED:MASK_ERROR>"

    def test_mask_overflow_sentinel_value(self) -> None:
        """TC-UT-PF-006-B: REDACT_MASK_OVERFLOW matches the design wording."""
        assert masking.REDACT_MASK_OVERFLOW == "<REDACTED:MASK_OVERFLOW>"
