"""SkillRef.path traversal defense (Agent feature §確定 H, H1〜H10).

Each Hx check is a **module-level pure function** so:

1. Tests can ``import`` them and invoke directly to prove each rule works
   independently — same testability pattern as Workflow's
   :mod:`bakufu.domain.workflow.dag_validators` (Confirmation F).
2. :func:`_validate_skill_path` stays a thin sequencer over the ten checks,
   with order locked by the design document.
3. Future ``feature/skill-loader`` Phase-2 work that adds a runtime I/O
   recheck can re-use the exact same helpers — single source of truth for
   path policy, no rule drift.

The functions raise :class:`AgentInvariantViolation` directly so callers
(``SkillRef`` field validator) get the structured ``kind='skill_path_invalid'``
discriminator without going through Pydantic's ``ValidationError`` wrapping.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path, PurePosixPath

from bakufu.domain.exceptions import AgentInvariantViolation

# H2: 1〜500 chars (NFC-normalized form).
MIN_PATH_LENGTH: int = 1
MAX_PATH_LENGTH: int = 500

# H7: required prefix segments. Anything not under bakufu-data/skills/* is
# rejected at the VO boundary, regardless of what the file system says.
REQUIRED_PARTS_PREFIX: tuple[str, str] = ("bakufu-data", "skills")
SKILLS_SUBDIR: str = "skills"

# H4: leading-character rejections.
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")

# H9: Windows reserved device names. Compared case-insensitive on the part
# stem (without extension) so "CON.md" is rejected too.
_WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# H3: forbidden characters — NUL, ASCII C0/C1 control, backslash.
_ASCII_CONTROL_RANGE = frozenset(chr(c) for c in range(0x00, 0x20)) | {chr(0x7F)}
_FORBIDDEN_CHARS: frozenset[str] = _ASCII_CONTROL_RANGE | {"\\"}


def _violation(check_id: str, detail_extra: dict[str, object]) -> AgentInvariantViolation:
    """Centralize the ``AgentInvariantViolation`` shape used by every Hx helper.

    Keeps the message format and ``kind`` consistent so callers can switch on
    ``detail['check']`` to attribute the failure without parsing strings.
    """
    detail = {"check": check_id, **detail_extra}
    return AgentInvariantViolation(
        kind="skill_path_invalid",
        message=f"[FAIL] SkillRef.path validation failed (check {check_id}): {detail}",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# H1: NFC normalization
# ---------------------------------------------------------------------------
def _h1_nfc_normalize(raw_path: str) -> str:
    """Apply NFC. Returned string is what every subsequent helper inspects."""
    return unicodedata.normalize("NFC", raw_path)


# ---------------------------------------------------------------------------
# H2: length 1〜500
# ---------------------------------------------------------------------------
def _h2_check_length(path: str) -> None:
    length = len(path)
    if not (MIN_PATH_LENGTH <= length <= MAX_PATH_LENGTH):
        raise _violation(
            "H2",
            {
                "length": length,
                "min": MIN_PATH_LENGTH,
                "max": MAX_PATH_LENGTH,
            },
        )


# ---------------------------------------------------------------------------
# H3: forbidden chars (NUL / control / backslash)
# ---------------------------------------------------------------------------
def _h3_check_forbidden_chars(path: str) -> None:
    for ch in path:
        if ch in _FORBIDDEN_CHARS:
            raise _violation("H3", {"forbidden_char_codepoint": ord(ch)})


# ---------------------------------------------------------------------------
# H4: leading-character rejection (POSIX abs / Windows abs / home tilde)
# ---------------------------------------------------------------------------
def _h4_check_leading(path: str) -> None:
    if path.startswith("/"):
        raise _violation("H4", {"reason": "leading slash (POSIX absolute)"})
    if path.startswith("~"):
        raise _violation("H4", {"reason": "leading tilde (home expansion)"})
    if _WINDOWS_ABSOLUTE_RE.match(path):
        raise _violation("H4", {"reason": "Windows absolute path"})


# ---------------------------------------------------------------------------
# H5: traversal sequences and surrounding whitespace
# ---------------------------------------------------------------------------
def _h5_check_traversal_sequences(path: str) -> None:
    if path != path.strip():
        raise _violation("H5", {"reason": "leading or trailing whitespace"})
    # ``path == '.'`` / ``path == '..'`` / leading ``./`` or ``../`` are
    # current-dir or parent-dir aliases that round-trip through
    # PurePosixPath silently — reject them at this layer.
    if path in {".", ".."} or path.startswith(("./", "../")):
        raise _violation("H5", {"reason": "path starts with '.' or '..'"})
    if path.endswith(("/.", "/..", "/")):
        raise _violation("H5", {"reason": "path ends with '.' or '..' or trailing slash"})
    # Two-dot traversal anywhere — most common attack form.
    if ".." in path.split("/"):
        raise _violation("H5", {"reason": "'..' parent-dir traversal in path"})


# ---------------------------------------------------------------------------
# H6: parse via PurePosixPath, return parts
# ---------------------------------------------------------------------------
def _h6_parse_parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


# ---------------------------------------------------------------------------
# H7: prefix must be ('bakufu-data', 'skills', <rest>)
# ---------------------------------------------------------------------------
def _h7_check_prefix(parts: tuple[str, ...]) -> None:
    if len(parts) < 3:
        raise _violation(
            "H7",
            {"reason": "path needs at least 3 components", "parts_count": len(parts)},
        )
    if parts[0] != REQUIRED_PARTS_PREFIX[0] or parts[1] != REQUIRED_PARTS_PREFIX[1]:
        raise _violation(
            "H7",
            {
                "reason": "prefix must be 'bakufu-data/skills/'",
                "actual_prefix": list(parts[:2]),
            },
        )


# ---------------------------------------------------------------------------
# H8: re-check every part for forbidden chars (defense in depth post-parse)
# ---------------------------------------------------------------------------
def _h8_recheck_parts(parts: tuple[str, ...]) -> None:
    for index, part in enumerate(parts):
        for ch in part:
            if ch in _FORBIDDEN_CHARS:
                raise _violation(
                    "H8",
                    {"part_index": index, "forbidden_char_codepoint": ord(ch)},
                )


# ---------------------------------------------------------------------------
# H9: Windows reserved names
# ---------------------------------------------------------------------------
def _h9_check_windows_reserved(parts: tuple[str, ...]) -> None:
    for index, part in enumerate(parts):
        # Strip extension for the comparison: "CON.md" → "CON".
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise _violation(
                "H9",
                {
                    "part_index": index,
                    "reserved_name": stem,
                },
            )


# ---------------------------------------------------------------------------
# H10: filesystem-grounded base-escape verification
# ---------------------------------------------------------------------------
def _h10_check_base_escape(path: str) -> None:
    """Resolve ``BAKUFU_DATA_DIR / path`` and require it to live under
    ``BAKUFU_DATA_DIR / 'bakufu-data' / 'skills'`` (the canonical skills root).

    The relative path ``bakufu-data/skills/<rest>`` is resolved against
    ``BAKUFU_DATA_DIR``; the joined absolute path must stay under the
    skills root. ``Path.resolve()`` follows symlinks, so symlink-via-skills-subdir
    escape is detected here — the final defensive line. If
    ``BAKUFU_DATA_DIR`` is unset we raise a structured failure rather than
    silently skipping (defense in depth).
    """
    base_dir_str = os.environ.get("BAKUFU_DATA_DIR")
    if not base_dir_str:
        raise _violation(
            "H10",
            {"reason": "BAKUFU_DATA_DIR not set"},
        )
    base_dir = Path(base_dir_str)
    # ``REQUIRED_PARTS_PREFIX`` is ``('bakufu-data', 'skills')``, so the
    # canonical skills root is exactly that prefix joined under the env var.
    skills_root = base_dir.joinpath(*REQUIRED_PARTS_PREFIX).resolve()
    candidate = (base_dir / path).resolve()
    if not candidate.is_relative_to(skills_root):
        raise _violation(
            "H10",
            {
                "reason": "resolved path escapes BAKUFU_DATA_DIR/bakufu-data/skills/",
                "skills_root": str(skills_root),
            },
        )


# ---------------------------------------------------------------------------
# Orchestrator (used by SkillRef.field_validator)
# ---------------------------------------------------------------------------
def _validate_skill_path(raw_path: str) -> str:
    """Run H1〜H10 in the design's locked order and return the NFC-normalized form.

    The returned value is what :class:`SkillRef` stores as ``path`` — callers
    must always replace their input with the function's output so downstream
    consumers never see un-normalized strings.

    Raises:
        AgentInvariantViolation: with ``kind='skill_path_invalid'`` on any
            failure. ``detail['check']`` carries the Hx identifier (``'H1'``
            ... ``'H10'``) so HTTP/API layers can localize without parsing
            the message string.
    """
    normalized = _h1_nfc_normalize(raw_path)
    _h2_check_length(normalized)
    _h3_check_forbidden_chars(normalized)
    _h4_check_leading(normalized)
    _h5_check_traversal_sequences(normalized)
    parts = _h6_parse_parts(normalized)
    _h7_check_prefix(parts)
    _h8_recheck_parts(parts)
    _h9_check_windows_reserved(parts)
    _h10_check_base_escape(normalized)
    return normalized


__all__ = [
    "MAX_PATH_LENGTH",
    "MIN_PATH_LENGTH",
    "REQUIRED_PARTS_PREFIX",
    "SKILLS_SUBDIR",
    "_h1_nfc_normalize",
    "_h2_check_length",
    "_h3_check_forbidden_chars",
    "_h4_check_leading",
    "_h5_check_traversal_sequences",
    "_h6_parse_parts",
    "_h7_check_prefix",
    "_h8_recheck_parts",
    "_h9_check_windows_reserved",
    "_h10_check_base_escape",
    "_validate_skill_path",
]
