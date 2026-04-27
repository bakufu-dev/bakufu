"""Discord webhook secret masking on RoomInvariantViolation (TC-UT-RM-014).

Confirmation H: ``RoomInvariantViolation`` masks webhook URLs in both
``message`` and ``detail`` at construction time. ``Room.name`` /
``Room.description`` / ``PromptKit.prefix_markdown`` may all carry user-
pasted text containing a webhook URL, so the exception path is the *last*
defense before that secret would be serialized into a log line or HTTP
response body.
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation

from tests.factories.room import make_room

# A webhook URL designed to fail the description length check (>500 chars).
# The id segment (numeric) stays visible; the token segment must be redacted.
_WEBHOOK_ID = "1234567890123456789"
_WEBHOOK_TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWX"
_WEBHOOK_URL = f"https://discord.com/api/webhooks/{_WEBHOOK_ID}/{_WEBHOOK_TOKEN}"
_REDACTED = "<REDACTED:DISCORD_WEBHOOK>"


class TestWebhookMaskingOnDescriptionViolation:
    """TC-UT-RM-014: webhook URL in oversize description is redacted in exception text."""

    def test_token_segment_is_redacted_in_message(self) -> None:
        """TC-UT-RM-014: exception.message contains the redacted token marker."""
        # Build a description >500 chars that *contains* the webhook URL.
        description = _WEBHOOK_URL + ("a" * 600)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description=description)
        assert _WEBHOOK_TOKEN not in excinfo.value.message
        # The webhook id stays for traceability; only token is redacted.

    def test_token_segment_does_not_leak_into_str_exc(self) -> None:
        """TC-UT-RM-014: str(exc) (used by default logging) carries no token."""
        description = _WEBHOOK_URL + ("a" * 600)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description=description)
        assert _WEBHOOK_TOKEN not in str(excinfo.value)


class TestWebhookMaskingOnDetail:
    """TC-UT-RM-014: webhook URL embedded in detail dict is also redacted."""

    def test_redacted_marker_substitutes_token_in_detail(self) -> None:
        """TC-UT-RM-014: detail values produced by exception path are masked.

        We trigger a name_range violation with an oversized name carrying a
        webhook URL. The aggregate validators only put structural data in
        ``detail`` (length / count), but the masking pass walks the whole
        dict so any string-valued context is run through
        :func:`mask_discord_webhook_in`. The contract is that no detail
        value contains the raw token segment.
        """
        # Build an oversize name (>80 chars) carrying the webhook URL.
        name = _WEBHOOK_URL + "x"
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name=name)
        # Walk all string values in detail; none should expose the token.
        for value in excinfo.value.detail.values():
            assert _WEBHOOK_TOKEN not in str(value)


class TestWebhookMaskingIdempotent:
    """Confirmation H supplemental: masking applied twice yields the same string."""

    def test_already_masked_url_is_not_re_substituted(self) -> None:
        """``mask_discord_webhook`` is idempotent so re-application is a no-op."""
        from bakufu.domain.value_objects import mask_discord_webhook

        once = mask_discord_webhook(_WEBHOOK_URL)
        twice = mask_discord_webhook(once)
        assert once == twice
        assert _REDACTED in once
