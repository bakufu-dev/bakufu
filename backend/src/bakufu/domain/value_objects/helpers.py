"""Cross-cutting helper functions and annotated string types for the bakufu domain.

Two helpers are shared by every Aggregate (Empire / Workflow / Agent / ...):

* :func:`nfc_strip` — name normalization pipeline (NFC → strip → length),
  fulfilling Empire detailed-design §Confirmation B and Workflow §Confirmation B.
* :func:`mask_discord_webhook` — replaces the secret ``token`` segment of a
  Discord webhook URL with ``<REDACTED:DISCORD_WEBHOOK>`` while preserving the
  ``id`` segment for audit traceability. Required by Workflow detailed-design
  §Confirmation G "target のシークレット扱い".
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, cast

from pydantic import BeforeValidator, Field

# ---------------------------------------------------------------------------
# Name normalization (Confirmation B)
# ---------------------------------------------------------------------------


def nfc_strip(value: object) -> object:
    """Apply NFC normalization and ``strip`` per detailed-design §Confirmation B.

    Public so sibling Aggregates (Empire / Workflow / Agent / ...) can share
    the **single** implementation of the normalization pipeline. Operates only
    on ``str`` inputs; non-string values are passed through unchanged so
    Pydantic's downstream type validation reports them with its standard error
    shape rather than silently coercing.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).strip()
    return value


# Public alias used by sibling VOs/Aggregates that adopt the same pipeline.
type NormalizedShortName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=80),
]
"""``str`` annotated with NFC+strip BeforeValidator and 1〜80-char Field bounds.

Used by :class:`RoomRef` and any future VO with the 80-char short-name contract.
"""

type NormalizedAgentName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=40),
]
"""1〜40-char variant for :class:`AgentRef` (Agent.name regulation)."""


# ---------------------------------------------------------------------------
# Discord webhook secret masking (Workflow §Confirmation G)
# ---------------------------------------------------------------------------
# Capture id (numeric) separately so it stays visible in audit/log output
# while only the token segment is redacted. Anchored loosely (no ^/$) so the
# pattern matches when the URL is embedded inside larger strings (exception
# detail dicts, JSON payloads, log lines).
_DISCORD_WEBHOOK_PATTERN = re.compile(
    r"https://discord\.com/api/webhooks/([0-9]+)/([A-Za-z0-9_\-]+)"
)
_DISCORD_WEBHOOK_REDACTED_TOKEN = "<REDACTED:DISCORD_WEBHOOK>"


def mask_discord_webhook(text: str) -> str:
    """Replace the secret ``token`` segment of every Discord webhook URL.

    Retains the snowflake ``id`` for traceability (audit_log can identify
    *which* webhook was involved) while redacting the credential segment.
    Idempotent: applying it twice yields the same result.
    """
    return _DISCORD_WEBHOOK_PATTERN.sub(
        rf"https://discord.com/api/webhooks/\1/{_DISCORD_WEBHOOK_REDACTED_TOKEN}",
        text,
    )


def mask_discord_webhook_in(value: object) -> object:
    """Recursively apply :func:`mask_discord_webhook` to strings within a value.

    Walks ``str`` / ``list`` / ``tuple`` / ``dict`` structures so nested
    diagnostic payloads (used in exception ``detail``) cannot leak a token
    via a list element or dict value. ``cast`` calls give pyright strict the
    element typing it cannot infer from a bare ``isinstance`` narrowing.
    """
    if isinstance(value, str):
        return mask_discord_webhook(value)
    if isinstance(value, list):
        items_list = cast("list[object]", value)
        return [mask_discord_webhook_in(item) for item in items_list]
    if isinstance(value, tuple):
        items_tuple = cast("tuple[object, ...]", value)
        return tuple(mask_discord_webhook_in(item) for item in items_tuple)
    if isinstance(value, dict):
        items_dict = cast("dict[object, object]", value)
        return {key: mask_discord_webhook_in(val) for key, val in items_dict.items()}
    return value


__all__ = [
    "NormalizedAgentName",
    "NormalizedShortName",
    "mask_discord_webhook",
    "mask_discord_webhook_in",
    "nfc_strip",
]
