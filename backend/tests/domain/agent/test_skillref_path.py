"""SkillRef.path traversal defense H1〜H10 (Confirmation H / TC-UT-AG-038〜044).

Each ``Test*`` class targets one Hx rule. Failures cluster by which rule was
violated, mirroring the workflow ``test_notify_channel_ssrf.py`` structure
that Norman / Schneier approved for SSRF G1〜G10.

The aggregate-side path goes through ``SkillRef.field_validator`` which
delegates to :func:`_validate_skill_path`. We exercise the public surface
(constructor + ``model_validate``) so future refactors of the orchestrator
internals do not silently drop coverage. The orchestrator function carries a
leading underscore (Steve PR #17 naming-symmetry rule): all path / aggregate
helpers are module-private until a real cross-feature consumer arrives.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.agent import SkillRef
from bakufu.domain.exceptions import AgentInvariantViolation


def _ref(path: str) -> SkillRef:
    """Build a SkillRef with arbitrary id/name and the given path."""
    return SkillRef(skill_id=uuid4(), name="test-skill", path=path)


class TestH1NFCNormalization:
    """H1 / TC-UT-AG-038 — NFC normalization of the path string."""

    def test_decomposed_kana_in_path_is_normalized(self) -> None:
        """H1: 'がが' decomposed in path is stored as the composed form."""
        import unicodedata

        composed_filename = "がが.md"
        decomposed_filename = unicodedata.normalize("NFD", composed_filename)
        path = f"bakufu-data/skills/{decomposed_filename}"
        ref = _ref(path)
        assert ref.path == f"bakufu-data/skills/{composed_filename}"


class TestH3ForbiddenChars:
    """H3 / TC-UT-AG-039 — NUL / control / backslash forbidden in path."""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "bakufu-data/skills/foo\\bar.md",  # backslash
            "bakufu-data/skills/foo\x00.md",  # NUL
            "bakufu-data/skills/foo\x01.md",  # ASCII control
            "bakufu-data/skills/foo\x7f.md",  # DEL
        ],
    )
    def test_forbidden_chars_rejected(self, bad_path: str) -> None:
        """H3: backslash / NUL / control / DEL all raise skill_path_invalid."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H3"


class TestH4LeadingChar:
    """H4 / TC-UT-AG-039 — POSIX abs / Windows abs / tilde rejected."""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/etc/passwd",  # POSIX absolute
            "~/secret",  # tilde home expansion
            "C:\\Windows\\system32",  # Windows absolute backslash
            "D:/foo/bar",  # Windows absolute forward slash
        ],
    )
    def test_leading_char_rejected(self, bad_path: str) -> None:
        """H4: leading slash / tilde / Windows-drive prefix raise."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        # Backslash inside the path also trips H3; we just verify rejection
        # against a stable check identifier from the H3+H4 pair.
        assert excinfo.value.detail.get("check") in {"H3", "H4"}


class TestH5TraversalSequences:
    """H5 / TC-UT-AG-040 — '..' traversal and surrounding whitespace rejected."""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "bakufu-data/skills/../../../etc/passwd",  # classic traversal
            "bakufu-data/skills/sub/../escape",  # mid-path traversal
            "bakufu-data/skills/legitimate/../../../escape",  # multi-up
            "..",  # bare parent
            "./relative",  # current-dir prefix
            "../escape",  # parent prefix
        ],
    )
    def test_traversal_or_dot_prefix_rejected(self, bad_path: str) -> None:
        """H5: any '..' segment in the path raises skill_path_invalid."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"

    @pytest.mark.parametrize(
        "bad_path",
        [
            " bakufu-data/skills/file.md",  # leading space
            "bakufu-data/skills/file.md ",  # trailing space
        ],
    )
    def test_surrounding_whitespace_rejected(self, bad_path: str) -> None:
        """H5: leading or trailing whitespace raises skill_path_invalid."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H5"


class TestH7PrefixEnforcement:
    """H7 / TC-UT-AG-041 — path must start with 'bakufu-data/skills/<rest>'."""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "other/path/file.md",  # wrong root
            "bakufu-data/other/file.md",  # second segment wrong
            "skills/file.md",  # missing 'bakufu-data'
            "bakufu-data/skills",  # too short (no <rest>)
        ],
    )
    def test_wrong_prefix_rejected(self, bad_path: str) -> None:
        """H7: prefix not matching ('bakufu-data', 'skills') raises."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H7"


class TestH9WindowsReserved:
    """H9 / TC-UT-AG-043 — Windows reserved device names (CON / NUL / etc.)."""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "bakufu-data/skills/CON.md",
            "bakufu-data/skills/prn.txt",  # case-insensitive
            "bakufu-data/skills/AUX",  # no extension
            "bakufu-data/skills/NUL.markdown",
            "bakufu-data/skills/COM1.md",
            "bakufu-data/skills/LPT9.md",
            "bakufu-data/skills/con",  # bare lowercase
        ],
    )
    def test_windows_reserved_name_rejected(self, bad_path: str) -> None:
        """H9: every Windows reserved device name (case-insensitive) raises."""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H9"


class TestH10BaseEscape:
    """H10 / TC-UT-AG-042 — resolved path must stay under BAKUFU_DATA_DIR/skills/."""

    def test_unset_bakufu_data_dir_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """H10: missing BAKUFU_DATA_DIR is a structured failure (not a silent skip)."""
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref("bakufu-data/skills/sample.md")
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H10"


class TestPathLengthBoundary:
    """H2 / TC-UT-AG-044 — path length 1〜500 (lower bound enforced via H4 / structural)."""

    def test_500_char_valid_path_succeeds(self) -> None:
        """H2: a structurally-valid 500-char path constructs."""
        # Build "bakufu-data/skills/" (19 chars) + (some extra prefix) + filename
        # to total exactly 500 chars.
        prefix = "bakufu-data/skills/"
        remaining = 500 - len(prefix)
        # Use a long filename of 'a'*remaining; H9 stem is 'a'*remaining minus
        # extension which is fine (not a reserved name).
        path = prefix + "a" * remaining
        assert len(path) == 500
        ref = _ref(path)
        assert ref.path == path

    def test_501_char_path_rejected(self) -> None:
        """H2: a 501-char path raises skill_path_invalid (H2)."""
        prefix = "bakufu-data/skills/"
        remaining = 501 - len(prefix)
        path = prefix + "a" * remaining
        assert len(path) == 501
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H2"


class TestValidPathHappyPath:
    """Sanity: a fully valid SkillRef.path constructs and is stored normalized."""

    def test_canonical_path_constructs(self) -> None:
        """Happy path: 'bakufu-data/skills/reviewer.md' goes through all H1〜H10."""
        ref = _ref("bakufu-data/skills/reviewer.md")
        assert ref.path == "bakufu-data/skills/reviewer.md"

    def test_nested_subdir_constructs(self) -> None:
        """Happy path: nested subdir under skills/ is permitted."""
        ref = _ref("bakufu-data/skills/sub/sub2/file.md")
        assert ref.path == "bakufu-data/skills/sub/sub2/file.md"
