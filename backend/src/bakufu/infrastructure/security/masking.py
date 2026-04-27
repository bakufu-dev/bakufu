"""Masking gateway with Fail-Secure fallback (§確定 A + §確定 F).

Layered redaction (order is **fixed**, see Confirmation A):

1. **Environment-variable values** — known secret env vars are
   redacted to ``<REDACTED:ENV:{NAME}>``.
2. **Regex patterns** — nine well-known secret-string formats
   (Anthropic / OpenAI / GitHub PAT / GitHub fine-grained PAT / AWS
   access key / AWS secret / Slack token / Discord bot token / Bearer
   token).
3. **Home path** — the running user's ``$HOME`` absolute path is
   replaced with ``<HOME>`` so log output does not leak the FS layout.

Fail-Secure contract (§確定 F)
-------------------------------
``mask`` and ``mask_in`` **never raise**. Any internal failure is
caught and the offending payload is replaced with a sentinel
(``<REDACTED:MASK_ERROR>`` / ``<REDACTED:MASK_OVERFLOW>`` /
``<REDACTED:LISTENER_ERROR>``). The raw value is **never** allowed to
propagate downstream — operations continuity is sacrificed before
secret leakage.

The ``Bootstrap`` initializes this module by calling
:func:`init` once at startup. Subsequent ``mask`` / ``mask_in`` calls
read from the module-level state.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Final, cast

from bakufu.infrastructure.security.masked_env import load_env_patterns

logger = logging.getLogger(__name__)

# Sentinel constants for Fail-Secure replacement (§確定 F).
REDACT_MASK_ERROR: Final = "<REDACTED:MASK_ERROR>"
REDACT_MASK_OVERFLOW: Final = "<REDACTED:MASK_OVERFLOW>"
REDACT_LISTENER_ERROR: Final = "<REDACTED:LISTENER_ERROR>"

# Confirmation F: cap dict / list traversal to keep accidental 10-MB
# payloads from spinning the masker. Anything larger than this is
# replaced wholesale.
MAX_BYTES_FOR_RECURSION: Final = 1_048_576  # 1 MiB

# Confirmation A: nine regex patterns (order matters — Anthropic is
# applied before OpenAI because the OpenAI pattern would otherwise
# match `sk-ant-...` prefixes; we keep the explicit Anthropic pattern
# in front to make the precedence visible to readers).
_REGEX_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (
        re.compile(r"sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}"),
        "<REDACTED:ANTHROPIC_KEY>",
    ),
    # OpenAI uses a `sk-` prefix that overlaps with Anthropic's. Use a
    # negative lookahead so we don't double-mask Anthropic keys with the
    # OpenAI replacement string.
    (
        re.compile(r"sk-(?!ant-)[A-Za-z0-9]{20,}"),
        "<REDACTED:OPENAI_KEY>",
    ),
    (
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}"),
        "<REDACTED:GITHUB_PAT>",
    ),
    (
        re.compile(r"github_pat_[A-Za-z0-9_]{82,}"),
        "<REDACTED:GITHUB_PAT>",
    ),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED:AWS_ACCESS_KEY>"),
    (
        re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}"),
        "<REDACTED:AWS_SECRET>",
    ),
    (
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        "<REDACTED:SLACK_TOKEN>",
    ),
    (
        re.compile(r"[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}"),
        "<REDACTED:DISCORD_TOKEN>",
    ),
    # Bearer tokens (HTTP Authorization header). Preserve the
    # `Authorization: Bearer ` prefix for readability and only redact
    # the token portion.
    (
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+"),
        r"\1<REDACTED:BEARER>",
    ),
]

# Module-level state populated by `init`.
_env_patterns: list[tuple[str, re.Pattern[str]]] = []
_home_pattern: re.Pattern[str] | None = None
_initialized: bool = False


def init() -> None:
    """Compile env-var patterns + home path. Call once from Bootstrap.

    Idempotent: subsequent calls reload the env patterns. This lets
    test setups bracket their assertions with new env values without
    needing to reach into module internals.

    Raises:
        BakufuConfigError: when env-var snapshot fails (Fail-Fast,
            MSG-PF-008). Bubbled up unchanged from
            :func:`load_env_patterns`.
    """
    global _env_patterns, _home_pattern, _initialized
    _env_patterns = load_env_patterns()
    home = os.environ.get("HOME")
    _home_pattern = re.compile(re.escape(home)) if home else None
    _initialized = True


def mask(value: object) -> str:
    """Redact known secrets from ``value``. Never raises (§確定 F).

    Accepts ``object`` (not just ``str``) so the Fail-Secure listener
    outer-catch can funnel arbitrary payloads through the gateway
    without first having to validate the type. Internal failures are
    caught and the *entire* string is replaced with
    :data:`REDACT_MASK_ERROR` so a partial / unredacted leak is
    impossible. A WARN is logged so operators can investigate.
    """
    if not isinstance(value, str):
        # Defensive: callers should pass strings, but the listener
        # outer-catch may funnel weird payloads here. Fail-Secure
        # converts to a string and proceeds.
        try:
            value = str(value)
        except Exception:
            logger.warning(
                "[WARN] Masking gateway fallback applied: kind=mask_error "
                "(non-str input could not be coerced)"
            )
            return REDACT_MASK_ERROR
    try:
        out: str = value
        # Layer 1: env vars first (most specific).
        for env_name, pattern in _env_patterns:
            out = pattern.sub(f"<REDACTED:ENV:{env_name}>", out)
        # Layer 2: regex patterns (Anthropic before OpenAI).
        for pattern, replacement in _REGEX_PATTERNS:
            out = pattern.sub(replacement, out)
        # Layer 3: home path.
        if _home_pattern is not None:
            out = _home_pattern.sub("<HOME>", out)
        return out
    except Exception as exc:  # pragma: no cover — defensive fallback
        logger.warning(
            "[WARN] Masking gateway fallback applied: kind=mask_error (%r)",
            exc,
        )
        return REDACT_MASK_ERROR


def mask_in(value: object) -> object:
    """Recursively walk ``value`` and apply :func:`mask` to every string.

    Supports ``str`` / ``list`` / ``tuple`` / ``dict`` / scalar
    pass-throughs (``int`` / ``float`` / ``bool`` / ``None``). Any
    other object is coerced via ``str()`` first then masked.

    Confirmation F overflow guard: if the structure is so large that
    walking it would exceed :data:`MAX_BYTES_FOR_RECURSION` (estimated
    via ``sys.getsizeof``), the *entire* structure is replaced with
    :data:`REDACT_MASK_OVERFLOW`.
    """
    try:
        if sys.getsizeof(value) > MAX_BYTES_FOR_RECURSION:
            logger.warning(
                "[WARN] Masking gateway fallback applied: kind=mask_overflow "
                "(payload exceeds %d bytes)",
                MAX_BYTES_FOR_RECURSION,
            )
            return REDACT_MASK_OVERFLOW
    except (TypeError, OSError):  # pragma: no cover — defensive
        # Some custom objects don't implement getsizeof correctly.
        # Treat as small and proceed.
        pass

    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, list):
        items_list = cast("list[object]", value)
        return [mask_in(item) for item in items_list]
    if isinstance(value, tuple):
        items_tuple = cast("tuple[object, ...]", value)
        return tuple(mask_in(item) for item in items_tuple)
    if isinstance(value, dict):
        items_dict = cast("dict[object, object]", value)
        return {key: mask_in(val) for key, val in items_dict.items()}
    # Fallback: stringify unknown types so masking still applies. This
    # is the §確定 F "datetime / bytes" path.
    try:
        return mask(str(value))
    except Exception:
        logger.warning(
            "[WARN] Masking gateway fallback applied: kind=mask_error (stringification failed)"
        )
        return REDACT_MASK_ERROR


def is_initialized() -> bool:
    """``True`` once :func:`init` has been called.

    Listeners check this so they can short-circuit the test setups that
    forget to call :func:`init` and would otherwise leak raw values
    into the test DB.
    """
    return _initialized


__all__ = [
    "MAX_BYTES_FOR_RECURSION",
    "REDACT_LISTENER_ERROR",
    "REDACT_MASK_ERROR",
    "REDACT_MASK_OVERFLOW",
    "init",
    "is_initialized",
    "mask",
    "mask_in",
]
