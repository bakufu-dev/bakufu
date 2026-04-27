"""Pytest fixtures shared across agent aggregate tests.

The ``BAKUFU_DATA_DIR`` env var is mandatory for ``SkillRef.path`` H10
(:func:`bakufu.domain.agent.path_validators._h10_check_base_escape`). In
production the launcher sets it; in unit tests we autouse-fixture a stable
fake directory string so every SkillRef construction can complete H10
without relying on the actual filesystem (``Path.resolve(strict=False)``
on a non-existent path simply returns the lexically-resolved form).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _bakufu_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """Set ``BAKUFU_DATA_DIR`` for the duration of every agent test.

    Autouse fixture — pytest invokes it via dependency injection, so the
    function appears unused to pyright. The pragma below silences that.
    """
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-test-root")
