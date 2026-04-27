"""``BAKUFU_DATA_DIR`` resolution with absolute-path enforcement.

The data directory is the ground truth for every persistent artefact
bakufu manages: SQLite DB file, WAL / SHM, structured logs,
``attachments/`` storage, and ``bakufu_pid_registry`` related files.

Resolution policy
-----------------
1. If ``BAKUFU_DATA_DIR`` is set in the environment, use that.
   - Reject relative paths, NUL bytes, and ``..`` segments — these
     are the classic path-traversal vectors and the M1 ``SkillRef``
     defense pattern (H1〜H10) is reapplied at this layer.
2. If unset, default to the OS-conventional location:
   - Linux/macOS: ``${XDG_DATA_HOME:-$HOME/.local/share}/bakufu``
   - Windows: ``%LOCALAPPDATA%\\bakufu``
3. Resolve symlinks (``Path.resolve``) so downstream code never has
   to second-guess what the absolute path means.

The resolved path is cached at module level so subsequent ``resolve()``
calls are O(1) — every Bootstrap stage can ask the resolver without
worrying about repeating the I/O.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

from bakufu.infrastructure.exceptions import BakufuConfigError

ENV_VAR_NAME: str = "BAKUFU_DATA_DIR"

_resolved: Path | None = None


def resolve() -> Path:
    """Return the absolute, symlink-resolved data directory.

    Cached: first call validates the environment / OS default, all
    subsequent calls return the same :class:`Path`. Use :func:`reset`
    in test setups to force a re-resolve.

    Raises:
        BakufuConfigError: ``msg_id='MSG-PF-001'`` for invalid env
            values (relative path, NUL byte, ``..`` segment, or
            unreadable HOME). Bootstrap exits non-zero.
    """
    global _resolved
    if _resolved is not None:
        return _resolved

    raw = os.environ.get(ENV_VAR_NAME)
    path = _default_for_os() if raw is None or raw == "" else _validate_absolute(raw)

    # Resolve symlinks once so callers get a canonical path. ``strict=False``
    # because the directory may not exist yet — Bootstrap creates it later.
    _resolved = path.resolve(strict=False)
    return _resolved


def reset() -> None:
    """Clear the singleton cache. Test-only helper."""
    global _resolved
    _resolved = None


def _validate_absolute(value: str) -> Path:
    """Reject relative paths, NUL bytes, and traversal sequences."""
    home_safe_value = value.replace(str(Path("~").expanduser()), "<HOME>", 1)
    if "\x00" in value:
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(
                f"[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                f"(got: {home_safe_value!r}; contains NUL byte)"
            ),
        )
    if ".." in Path(value).parts:
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(
                f"[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                f"(got: {home_safe_value}; contains '..' segment)"
            ),
        )
    path = Path(value)
    if not path.is_absolute():
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(f"[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: {home_safe_value})"),
        )
    return path


def _default_for_os() -> Path:
    """OS-conventional default location for ``BAKUFU_DATA_DIR``."""
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise BakufuConfigError(
                msg_id="MSG-PF-001",
                message=(
                    "[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                    "(LOCALAPPDATA not set on Windows)"
                ),
            )
        return Path(local_app_data) / "bakufu"

    # POSIX path: respect XDG_DATA_HOME if present, otherwise
    # `$HOME/.local/share`.
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "bakufu"
    home = os.environ.get("HOME")
    if not home:
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(
                "[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                "(HOME not set; cannot derive default)"
            ),
        )
    return Path(home) / ".local" / "share" / "bakufu"


__all__ = [
    "ENV_VAR_NAME",
    "reset",
    "resolve",
]
