"""NotifyChannel SSRF allow list G1〜G10 (Confirmation G).

Covers TC-UT-WF-034〜036, 048〜054. Each ``Test*`` parametrize hits one of the
ten G-rules, ensuring any future change to ``NotifyChannel._validate_target``
produces a focused diff in this file rather than scattering the SSRF contract
across a monolithic test module.
"""

from __future__ import annotations

import pytest
from bakufu.domain.value_objects import NotifyChannel
from pydantic import ValidationError


class TestNotifyChannelSSRF:
    """TC-UT-WF-034〜036, 048〜054 — full G1〜G10 rejection coverage."""

    @pytest.mark.parametrize(
        "bad_target",
        [
            # G3: HTTPS強制
            "http://discord.com/api/webhooks/123/abc-DEF_xyz",
        ],
    )
    def test_034_https_only(self, bad_target: str) -> None:
        """TC-UT-WF-034 / G3: scheme must be 'https'."""
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
        """TC-UT-WF-035 / G4: hostname must equal 'discord.com' exactly."""
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
        """TC-UT-WF-036 / G7: path must match /api/webhooks/<id>/<token>."""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    def test_048_token_at_g7_cap_succeeds_overflow_rejected(self) -> None:
        """TC-UT-WF-048 / G1+G7: 100-char token (G7 cap) works, 101+ rejected.

        Realistic upper bound on a *valid* Discord webhook URL is reached via
        G7 (token ≤ 100 chars). We verify that the maximum-permitted shape
        constructs successfully, that any G7 overflow trips, and that an
        oversized URL hits G1 independently.
        """
        base = "https://discord.com/api/webhooks/123456789/"
        valid = base + "a" * 100  # token at G7 cap
        channel = NotifyChannel(kind="discord", target=valid)
        assert channel.target == valid
        # 101-char token violates G7.
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=base + "a" * 101)
        # 500+ char URL violates G1 too.
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
        """TC-UT-WF-049 / G5: port restricted to {None, 443}."""
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
        """TC-UT-WF-050 / G6: userinfo (user/password) rejected."""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com/api/webhooks/abc/def",  # id non-numeric
            "https://discord.com/api/webhooks/123/!@#",  # token bad chars
            "https://discord.com/api/webhooks/" + ("0" * 31) + "/abc",  # id 31 digits
            "https://discord.com/api/webhooks/123/" + ("a" * 101),  # token 101 chars
            "https://discord.com/api/webhooks/123/abc/extra",  # extra path segment
        ],
    )
    def test_051_path_regex_fullmatch(self, bad_target: str) -> None:
        """TC-UT-WF-051 / G7: path regex must fullmatch /api/webhooks/<id>/<token>."""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)

    def test_052_query_rejected(self) -> None:
        """TC-UT-WF-052 / G8: query string rejected."""
        with pytest.raises(ValidationError):
            NotifyChannel(
                kind="discord",
                target="https://discord.com/api/webhooks/123/abc?override=x",
            )

    def test_053_fragment_rejected(self) -> None:
        """TC-UT-WF-053 / G9: fragment rejected."""
        with pytest.raises(ValidationError):
            NotifyChannel(
                kind="discord",
                target="https://discord.com/api/webhooks/123/abc#frag",
            )

    @pytest.mark.parametrize(
        "bad_target",
        [
            "https://discord.com/API/WEBHOOKS/123/abc",  # uppercase API/WEBHOOKS
            "https://discord.com/Api/Webhooks/123/abc",  # mixed case
        ],
    )
    def test_054_path_case_sensitive(self, bad_target: str) -> None:
        """TC-UT-WF-054 / G10: path case-sensitive (only lowercase /api/webhooks/)."""
        with pytest.raises(ValidationError):
            NotifyChannel(kind="discord", target=bad_target)
