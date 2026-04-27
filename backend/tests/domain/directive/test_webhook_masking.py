"""DirectiveInvariantViolation webhook auto-mask tests (TC-UT-DR-007).

Confirmation E: ``DirectiveInvariantViolation`` runs
``mask_discord_webhook`` over ``message`` and ``mask_discord_webhook_in``
over ``detail`` *before* :class:`Exception` ``__init__`` so the secret
``token`` segment of any embedded webhook URL never leaks through
serialization, logging, or HTTP error responses. CEO directives can
include user-pasted text that may carry a webhook URL; the aggregate
boundary is the last layer where masking can still happen before
persistence.
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import make_directive

# A valid-shape Discord webhook URL. The numeric ``id`` segment must
# stay visible (audit traceability) while the token segment must be
# redacted to ``<REDACTED:DISCORD_WEBHOOK>``.
_WEBHOOK_ID = "1234567890123456789"
_WEBHOOK_TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWX"
_WEBHOOK_URL = f"https://discord.com/api/webhooks/{_WEBHOOK_ID}/{_WEBHOOK_TOKEN}"
_REDACTED = "<REDACTED:DISCORD_WEBHOOK>"


class TestWebhookMaskingOnTextRangeViolation:
    """TC-UT-DR-007: webhook URL inside oversize text is redacted in exception text."""

    def test_token_does_not_appear_in_message(self) -> None:
        """TC-UT-DR-007: exception.message contains the redacted marker only."""
        # Build a 10001-char text that *contains* the webhook URL.
        text = _WEBHOOK_URL + ("a" * 10_001)
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text=text)
        assert _WEBHOOK_TOKEN not in excinfo.value.message

    def test_token_does_not_leak_into_str_exc(self) -> None:
        """TC-UT-DR-007: str(exc) (default logging path) is also redacted."""
        text = _WEBHOOK_URL + ("a" * 10_001)
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text=text)
        assert _WEBHOOK_TOKEN not in str(excinfo.value)


class TestWebhookMaskingOnDetail:
    """TC-UT-DR-007: detail dict values are recursively masked too."""

    def test_detail_values_carry_no_token(self) -> None:
        """TC-UT-DR-007: every str-valued detail item passes through mask_discord_webhook_in."""
        text = _WEBHOOK_URL + ("a" * 10_001)
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text=text)
        for value in excinfo.value.detail.values():
            assert _WEBHOOK_TOKEN not in str(value)


class TestWebhookMaskingIdempotent:
    """Confirmation E supplemental: masking is idempotent."""

    def test_re_application_does_not_double_substitute(self) -> None:
        """``mask_discord_webhook`` applied twice yields the same string."""
        from bakufu.domain.value_objects import mask_discord_webhook

        once = mask_discord_webhook(_WEBHOOK_URL)
        twice = mask_discord_webhook(once)
        assert once == twice
        assert _REDACTED in once
