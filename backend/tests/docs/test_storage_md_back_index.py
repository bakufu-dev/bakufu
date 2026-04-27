"""storage.md §逆引き表 contract test (TC-DOC-EMR-001).

Per ``docs/features/empire-repository/test-design.md``. The reverse-
lookup table is the design source of truth for "which DB column is
masked, which one is explicitly declared no-mask"; the CI three-layer
defense (grep guard + arch test + this doc test) makes the lookup
table physically authoritative.

Future Repository PRs append rows for their Aggregate's tables; the
shape of the assertion stays identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STORAGE_MD = _REPO_ROOT / "docs" / "architecture" / "domain-model" / "storage.md"


@pytest.fixture(scope="module")
def storage_md_text() -> str:
    """Read storage.md once per module (the file is small)."""
    assert _STORAGE_MD.is_file(), (
        f"storage.md missing at {_STORAGE_MD}; the §逆引き表 lives there per "
        f"docs/architecture/domain-model/storage.md."
    )
    return _STORAGE_MD.read_text(encoding="utf-8")


class TestBackIndexHasEmpireRow:
    """TC-DOC-EMR-001: §逆引き表 includes the Empire 'masking 対象なし' entry."""

    def test_empire_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-EMR-001: at least one Empire row is registered as no-mask.

        We check for the substring rather than the exact bullet so the
        assertion survives cosmetic edits (table ordering, alternative
        phrasing). The presence is the contract; the precise format
        belongs to the design review.
        """
        assert "Empire" in storage_md_text, (
            "storage.md must mention Empire so the §逆引き表 can register "
            "the 'masking 対象なし' entry per empire-repository §確定 E."
        )
        # Either Japanese phrasing variant freezes the no-mask intent.
        no_mask_phrasing_present = any(
            phrase in storage_md_text
            for phrase in (
                "masking 対象なし",
                "対象カラムなし",
                "no masking",
                "no masking targets",
            )
        )
        assert no_mask_phrasing_present, (
            "storage.md §逆引き表 must declare 'masking 対象なし' or an "
            "equivalent phrase so future Repository PRs can extend the "
            "reverse-lookup table with their own 'no-mask' entries."
        )

    def test_empire_table_row_co_locates_no_mask_phrase(self, storage_md_text: str) -> None:
        """TC-DOC-EMR-001: §逆引き表 row contains both 'Empire' and 'masking 対象なし'.

        The reverse-lookup table renders Empire as a single Markdown
        table row that lists the three Empire tables alongside the
        explicit "masking 対象なし" declaration. We assert that **at
        least one line** in storage.md carries both substrings — that
        is the operator-readable contract: scrolling to the Empire row
        reveals the no-mask declaration without further navigation.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "Empire" in line and "masking 対象なし" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'Empire' and 'masking 対象なし' so the no-mask "
            "declaration is operator-readable from the Empire row directly. "
            "Found Empire mentions and no-mask mentions but never on the "
            "same line — split rows would force an operator to cross-"
            "reference across the doc."
        )


class TestBackIndexHasWorkflowRows:
    """TC-DOC-WFR-001: §逆引き表 includes the Workflow partial-mask + no-mask entries.

    The Workflow PR (#41) introduces the *partial-mask* template
    alongside the empire-repo no-mask template: ``workflow_stages.notify_channels_json``
    is the **only** masked column on the Workflow surface, and
    ``workflows`` / ``workflow_transitions`` / the rest of
    ``workflow_stages`` are explicitly registered as no-mask. We
    assert both halves of that contract live on operator-readable
    lines in ``storage.md``.
    """

    def test_workflow_stages_notify_channels_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-WFR-001a: §逆引き表 declares ``MaskedJSONEncoded`` on the notify column.

        The line must co-locate ``workflow_stages.notify_channels_json``
        and ``MaskedJSONEncoded`` so an operator scrolling to the
        Workflow row sees the redaction policy directly.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "workflow_stages.notify_channels_json" in line and "MaskedJSONEncoded" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'workflow_stages.notify_channels_json' and "
            "'MaskedJSONEncoded' per workflow-repository §確定 H "
            "(Schneier 申し送り #6 Repository 実適用)."
        )

    def test_workflow_no_mask_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-WFR-001b: §逆引き表 declares the Workflow remaining columns no-mask.

        The contract phrase is "masking 対象なし" co-located with
        ``Workflow`` (so the partial-mask Aggregate's *non*-masked
        columns are still operator-readable from the Workflow row).
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "Workflow" in line and "masking 対象なし" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'Workflow' and 'masking 対象なし' so the partial-"
            "mask Aggregate's non-masked columns are operator-readable "
            "from the Workflow row directly. Required by workflow-"
            "repository §確定 H (partial-mask テンプレート)."
        )
