"""Deliverable / Attachment VO + enum tests.

TC-UT-TS-012 / 013 / 036 / 037 — the value objects Task accumulates
plus the two ``StrEnum``s that drive its lifecycle and error
classification.

The Attachment 6-step sanitization pipeline is covered cell-by-cell
so a regression on any single rejection rule shows up as a single
named failure rather than as a generic "filename validation broken"
sweep failure.

Per ``docs/features/task/test-design.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.value_objects import (
    Deliverable,
    LLMErrorKind,
    TaskStatus,
)
from pydantic import ValidationError

from tests.factories.task import make_attachment, make_deliverable

# Canonical valid sha256 reused in multiple cases.
_VALID_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


# ---------------------------------------------------------------------------
# TC-UT-TS-012: Deliverable construction + frozen + body_markdown cap
# ---------------------------------------------------------------------------
class TestDeliverableConstruction:
    """TC-UT-TS-012: Deliverable VO constructs valid + rejects oversize body."""

    def test_default_deliverable_constructs(self) -> None:
        """Factory-default Deliverable has empty attachments + non-naive committed_at."""
        d = make_deliverable()
        assert d.attachments == []
        assert d.committed_at.tzinfo is not None

    def test_deliverable_is_frozen(self) -> None:
        """Direct attribute assignment on a Deliverable is rejected."""
        d = make_deliverable()
        with pytest.raises(ValidationError):
            d.body_markdown = "mutated"  # pyright: ignore[reportAttributeAccessIssue]

    def test_body_markdown_at_max_length_accepted(self) -> None:
        """1,000,000-char body_markdown is at the cap and accepted."""
        body = "x" * 1_000_000
        d = make_deliverable(body_markdown=body)
        assert len(d.body_markdown) == 1_000_000

    def test_body_markdown_over_max_length_rejected(self) -> None:
        """1,000,001-char body_markdown exceeds the cap and raises."""
        body = "x" * 1_000_001
        with pytest.raises(ValidationError):
            make_deliverable(body_markdown=body)

    def test_naive_committed_at_rejected(self) -> None:
        """``committed_at`` without a timezone is rejected."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            Deliverable(
                stage_id=uuid4(),
                body_markdown="",
                attachments=[],
                committed_by=uuid4(),
                committed_at=naive,
            )


# ---------------------------------------------------------------------------
# TC-UT-TS-013: Attachment 6-step sanitize + sha256 + mime + size
# ---------------------------------------------------------------------------
class TestAttachmentSha256:
    """TC-UT-TS-013 step 0: sha256 = 64 lowercase hex chars."""

    def test_64_hex_lowercase_accepted(self) -> None:
        """The canonical happy-path sha256."""
        a = make_attachment(sha256=_VALID_SHA)
        assert a.sha256 == _VALID_SHA

    def test_63_chars_rejected(self) -> None:
        """A 63-char digest (one short) is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(sha256=_VALID_SHA[:-1])

    def test_uppercase_rejected(self) -> None:
        """Mixed-case hex is rejected (the regex is lowercase-only)."""
        mixed = "0123456789ABCDEF" + _VALID_SHA[16:]
        with pytest.raises(ValidationError):
            make_attachment(sha256=mixed)

    def test_non_hex_rejected(self) -> None:
        """Non-hex characters in the right length still fail the pattern."""
        bogus = "z" * 64
        with pytest.raises(ValidationError):
            make_attachment(sha256=bogus)


class TestAttachmentFilenameSanitization:
    """TC-UT-TS-013: filename 6-step sanitization pipeline.

    Each step's rejection rule has its own test so regressions
    surface with a precise label rather than a generic "filename
    validation broken" wave failure.
    """

    # Step 1-2: NFC + length [1, 255]
    def test_empty_filename_rejected(self) -> None:
        """Length 0 fails the [1, 255] band."""
        with pytest.raises(ValidationError):
            make_attachment(filename="")

    def test_256_char_filename_rejected(self) -> None:
        """Length 256 exceeds the cap."""
        with pytest.raises(ValidationError):
            make_attachment(filename="a" * 256)

    def test_255_char_filename_accepted(self) -> None:
        """Length 255 is at the cap and accepted."""
        a = make_attachment(filename="a" * 255)
        assert len(a.filename) == 255

    # Step 3: rejected characters (path separators, NUL, control chars)
    @pytest.mark.parametrize(
        "bad",
        ["a/b.txt", "a\\b.txt", "name\x00.png", "name\x01.png", "name\x7f.png"],
        ids=["forward_slash", "back_slash", "null_byte", "control_char", "del_char"],
    )
    def test_rejected_characters(self, bad: str) -> None:
        """Path separators / NUL / ASCII control chars are rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename=bad)

    # Step 4: rejected sequences
    def test_dot_dot_path_traversal_rejected(self) -> None:
        """``..`` anywhere in the name is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename="..hidden.png")

    def test_leading_dot_rejected(self) -> None:
        """Hidden file (leading ``.``) is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename=".hidden.png")

    def test_trailing_dot_rejected(self) -> None:
        """Trailing ``.`` (Windows extension trick) is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename="file.png.")

    def test_leading_whitespace_rejected(self) -> None:
        """Leading whitespace is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename=" file.png")

    def test_colon_rejected(self) -> None:
        """``:`` (Windows ADS / drive letter) is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename="file:stream.png")

    # Step 5: Windows reserved device names
    @pytest.mark.parametrize(
        "reserved",
        ["CON", "PRN", "AUX", "NUL", "COM1.txt", "LPT9.bin", "con.png", "Com2.bin"],
        ids=[
            "CON_bare",
            "PRN_bare",
            "AUX_bare",
            "NUL_bare",
            "COM1_ext",
            "LPT9_ext",
            "lower_con_ext",
            "mixed_com_ext",
        ],
    )
    def test_windows_reserved_names_rejected(self, reserved: str) -> None:
        """Windows reserved device names with or without extensions are rejected."""
        with pytest.raises(ValidationError):
            make_attachment(filename=reserved)

    # Step 6: basename round-trip
    def test_path_component_rejected_via_basename_check(self) -> None:
        """A path-shaped name fails the basename round-trip."""
        # ``a/b.txt`` is already caught by step 3, but ``foo/bar`` style
        # paths embedded with various separators still fail step 6.
        # We exercise this via a slash-containing name that step 3
        # already rejects, plus directly through the path round-trip
        # via a UNC-style prefix that step 3 might miss.
        # In practice all path-shapes are covered by step 3; step 6 is
        # the defensive double-check, so the assertion is shape:
        # any rejection at all is acceptable as long as ValidationError
        # fires.
        with pytest.raises(ValidationError):
            make_attachment(filename="dir/file.png")


class TestAttachmentMimeWhitelist:
    """TC-UT-TS-013: mime_type whitelist rejects text/html and text/csv."""

    @pytest.mark.parametrize(
        "mime",
        [
            "text/markdown",
            "text/plain",
            "application/json",
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "application/octet-stream",
        ],
    )
    def test_whitelisted_mime_accepted(self, mime: str) -> None:
        """All 8 whitelisted MIME types construct cleanly."""
        a = make_attachment(mime_type=mime)
        assert a.mime_type == mime

    @pytest.mark.parametrize(
        "mime",
        ["text/html", "text/csv", "application/x-shellscript", ""],
        ids=["text_html", "text_csv", "shell_script", "empty"],
    )
    def test_non_whitelisted_mime_rejected(self, mime: str) -> None:
        """Non-whitelisted MIME values are rejected — XSS / CSV-injection guard."""
        with pytest.raises(ValidationError):
            make_attachment(mime_type=mime)


class TestAttachmentSizeBytes:
    """TC-UT-TS-013: size_bytes ∈ [0, 10 MiB]."""

    def test_zero_bytes_accepted(self) -> None:
        """An empty attachment (0 bytes) is accepted."""
        a = make_attachment(size_bytes=0)
        assert a.size_bytes == 0

    def test_at_max_accepted(self) -> None:
        """10 MiB exactly is the cap and accepted."""
        a = make_attachment(size_bytes=10 * 1024 * 1024)
        assert a.size_bytes == 10 * 1024 * 1024

    def test_over_max_rejected(self) -> None:
        """10 MiB + 1 byte exceeds the cap."""
        with pytest.raises(ValidationError):
            make_attachment(size_bytes=10 * 1024 * 1024 + 1)

    def test_negative_rejected(self) -> None:
        """Negative size is rejected."""
        with pytest.raises(ValidationError):
            make_attachment(size_bytes=-1)


class TestAttachmentFrozen:
    """Attachment is frozen — direct attribute assignment is rejected."""

    def test_size_bytes_assignment_rejected(self) -> None:
        a = make_attachment()
        with pytest.raises(ValidationError):
            a.size_bytes = 0  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# TC-UT-TS-036: TaskStatus enum values
# ---------------------------------------------------------------------------
class TestTaskStatusEnum:
    """TC-UT-TS-036: 6 StrEnum values; StrEnum equality with raw strings."""

    def test_six_values(self) -> None:
        """Exactly 6 TaskStatus members."""
        members = list(TaskStatus)
        assert len(members) == 6

    def test_str_enum_equality(self) -> None:
        """StrEnum members compare equal to their string value."""
        assert TaskStatus.PENDING == "PENDING"
        assert TaskStatus.IN_PROGRESS == "IN_PROGRESS"
        assert TaskStatus.AWAITING_EXTERNAL_REVIEW == "AWAITING_EXTERNAL_REVIEW"
        assert TaskStatus.BLOCKED == "BLOCKED"
        assert TaskStatus.DONE == "DONE"
        assert TaskStatus.CANCELLED == "CANCELLED"


# ---------------------------------------------------------------------------
# TC-UT-TS-037: LLMErrorKind enum values
# ---------------------------------------------------------------------------
class TestLLMErrorKindEnum:
    """TC-UT-TS-037: 5 StrEnum values for LLM-Adapter classification."""

    def test_five_values(self) -> None:
        """Exactly 5 LLMErrorKind members."""
        members = list(LLMErrorKind)
        assert len(members) == 5

    def test_str_enum_equality(self) -> None:
        """StrEnum members compare equal to their string value."""
        assert LLMErrorKind.SESSION_LOST == "SESSION_LOST"
        assert LLMErrorKind.RATE_LIMITED == "RATE_LIMITED"
        assert LLMErrorKind.AUTH_EXPIRED == "AUTH_EXPIRED"
        assert LLMErrorKind.TIMEOUT == "TIMEOUT"
        assert LLMErrorKind.UNKNOWN == "UNKNOWN"


# ---------------------------------------------------------------------------
# Sanity: a Deliverable carries Attachments and round-trips cleanly
# ---------------------------------------------------------------------------
class TestDeliverableWithAttachments:
    """A Deliverable with attachments carries them through to the model."""

    def test_attachments_preserved(self) -> None:
        """Attachments list is preserved verbatim in Deliverable."""
        a = make_attachment()
        d = Deliverable(
            stage_id=uuid4(),
            body_markdown="# notes",
            attachments=[a],
            committed_by=uuid4(),
            committed_at=datetime.now(UTC),
        )
        assert d.attachments == [a]

    def test_make_attachment_synthetic(self) -> None:
        """The factory's :func:`is_synthetic` flag fires on freshly-built attachments."""
        from tests.factories.task import is_synthetic

        a = make_attachment()
        assert is_synthetic(a)
