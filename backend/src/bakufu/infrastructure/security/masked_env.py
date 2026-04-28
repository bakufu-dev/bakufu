"""Layer 1 of the masking gateway: known-environment-variable redaction.

Bootstrap collects values from a fixed allow-list of environment
variables at startup time and compiles them into a regex-replacement
table. The table is queried for every ``mask()`` call and every entry
matched is replaced with ``<REDACTED:ENV:{NAME}>``.

Why an allow-list (vs. "every env var")?
----------------------------------------
Some environment variables hold benign data (``PATH``, ``HOME``,
``LANG``). Including them all would over-redact CLI output / audit
text and make troubleshooting impossible. The allow-list is the same
list ``docs/design/domain-model/storage.md`` froze, with one
substitution: ``BAKUFU_DB_KEY`` is removed (MVP doesn't ship SQLCipher;
see Confirmation in ``masking.md``) and ``BAKUFU_DISCORD_BOT_TOKEN`` is
added in its place because the Discord notifier path keeps it as a
high-confidentiality asset (threat-model §資産).

Length floor of 8 characters
----------------------------
A short value (e.g. an empty string or a 4-character marker) would
match almost anything by accident. We skip values shorter than 8 and
INFO-log the skip so operators can spot a misconfigured env var.

Fail-Fast contract (§確定 F)
---------------------------
``load_env_patterns`` raises :class:`bakufu.infrastructure.exceptions.BakufuConfigError`
with ``msg_id='MSG-PF-008'`` if the OS rejects ``os.environ`` access
itself or any individual value cannot be regex-compiled. Bootstrap
intercepts and exits non-zero — running with masking layer 1 disabled
would silently degrade the trust boundary the rest of the system
relies on.
"""

from __future__ import annotations

import logging
import os
import re

from bakufu.infrastructure.exceptions import BakufuConfigError

logger = logging.getLogger(__name__)

# Fixed allow-list per ``docs/features/persistence-foundation/detailed-design/modules.md``
# §Module masked_env.py. Changes go through a design doc PR first.
KNOWN_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "OAUTH_CLIENT_SECRET",
    "BAKUFU_DISCORD_BOT_TOKEN",
)

# Values shorter than this are skipped to avoid catastrophic over-matching.
MIN_ENV_VALUE_LENGTH: int = 8


def load_env_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """Compile the known-env-var redaction table.

    Returns:
        A list of ``(env_name, compiled_pattern)`` pairs. Empty when no
        known env var is set in the current process — that is a
        legitimate state in CI / fresh dev environments and produces an
        INFO log entry rather than a failure.

    Raises:
        BakufuConfigError: ``msg_id='MSG-PF-008'`` when ``os.environ``
            access itself raises or any value fails ``re.compile``.
            Bootstrap exits non-zero on this — running with layer 1
            disabled is not an acceptable degraded mode.
    """
    try:
        env_snapshot = dict(os.environ)
    except OSError as exc:
        # `os.environ` access can fail under exotic OS-level conditions
        # (chroot misconfig, broken FS). Fail Fast — masking layer 1 is
        # part of the trust boundary, not optional.
        raise BakufuConfigError(
            msg_id="MSG-PF-008",
            message=(
                f"[FAIL] Masking environment dictionary load failed: "
                f"{exc!r}\n"
                f"Next: Cannot start with partial masking layer. "
                f"Investigate env access permissions and OS-level "
                f"masking config; restart bakufu after fix."
            ),
        ) from exc

    patterns: list[tuple[str, re.Pattern[str]]] = []
    skipped_short: list[str] = []
    for env_name in KNOWN_ENV_KEYS:
        raw = env_snapshot.get(env_name)
        if raw is None:
            continue
        if len(raw) < MIN_ENV_VALUE_LENGTH:
            skipped_short.append(env_name)
            continue
        try:
            patterns.append((env_name, re.compile(re.escape(raw))))
        except re.error as exc:
            # Theoretically unreachable since `re.escape` produces a
            # safe pattern, but Fail Fast preserves the trust boundary.
            raise BakufuConfigError(
                msg_id="MSG-PF-008",
                message=(
                    f"[FAIL] Masking environment dictionary load "
                    f"failed: regex compile error for {env_name}: "
                    f"{exc!r}\n"
                    f"Next: Cannot start with partial masking layer. "
                    f"Investigate env access permissions and OS-level "
                    f"masking config; restart bakufu after fix."
                ),
            ) from exc

    if not patterns:
        logger.info(
            "[INFO] Masking layer 1 (env): 0 patterns loaded "
            "(no known env vars set or all below length floor)."
        )
    if skipped_short:
        logger.info(
            "[INFO] Masking layer 1 (env): skipped %d env vars below length floor %d: %s",
            len(skipped_short),
            MIN_ENV_VALUE_LENGTH,
            ", ".join(sorted(skipped_short)),
        )
    return patterns


__all__ = [
    "KNOWN_ENV_KEYS",
    "MIN_ENV_VALUE_LENGTH",
    "load_env_patterns",
]
