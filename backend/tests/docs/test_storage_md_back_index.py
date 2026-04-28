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
_STORAGE_MD = _REPO_ROOT / "docs" / "design" / "domain-model" / "storage.md"


@pytest.fixture(scope="module")
def storage_md_text() -> str:
    """Read storage.md once per module (the file is small)."""
    assert _STORAGE_MD.is_file(), (
        f"storage.md missing at {_STORAGE_MD}; the §逆引き表 lives there per "
        f"docs/design/domain-model/storage.md."
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


class TestBackIndexHasAgentRows:
    """TC-DOC-AGR-001: §逆引き表 includes the Agent partial-mask + no-mask entries.

    The Agent Repository PR (#45) is the second partial-mask
    Aggregate (after Workflow): ``agents.prompt_body`` is the
    **only** masked column on the Agent surface, with
    ``agent_providers`` / ``agent_skills`` and the rest of
    ``agents`` registered as no-mask. **Schneier 申し送り #3 实適用
    クローズ** is documented through this line.
    """

    def test_agents_prompt_body_row_present(self, storage_md_text: str) -> None:
        """§逆引き表 declares ``MaskedText`` on ``agents.prompt_body``.

        The line must co-locate ``Persona.prompt_body`` (or
        ``agents.prompt_body``) and ``MaskedText`` so an operator
        scrolling to the Agent row sees the redaction policy
        directly.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if (
                "prompt_body" in line
                and "MaskedText" in line
                and ("agents" in line or "Persona" in line)
            )
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'prompt_body' and 'MaskedText' on an Agent-"
            "owned row per agent-repository §確定 H (Schneier 申し送り "
            "#3 实適用)."
        )

    def test_agent_no_mask_row_present(self, storage_md_text: str) -> None:
        """§逆引き表 declares the Agent remaining columns no-mask.

        agent_providers / agent_skills and other agents columns are
        registered as "masking 対象なし" so the partial-mask intent
        is visible from the Agent row directly.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "Agent" in line and "masking 対象なし" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'Agent' and 'masking 対象なし' so the partial-"
            "mask Aggregate's non-masked columns are operator-readable "
            "from the Agent row directly. Required by agent-repository "
            "§確定 H (partial-mask テンプレート)."
        )


class TestBackIndexHasDirectiveRows:
    """TC-DOC-DRR-001: §逆引き表 includes Directive partial-mask + no-mask entries.

    Directive Repository PR (#34): ``directives.text`` is the **only**
    masked column (directive §確定 G 実適用), with the remaining columns
    (id / target_room_id / created_at / task_id) registered as no-mask.
    """

    def test_directives_text_masked_text_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-DRR-001a: §逆引き表 declares MaskedText on directives.text.

        The line must co-locate ``directives.text`` (or ``Directive.text``)
        and ``MaskedText`` so an operator sees the redaction policy directly.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if ("directives" in line and "MaskedText" in line)
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'directives' and 'MaskedText' per "
            "directive-repository §確定 G 実適用 (Issue #34)."
        )

    def test_directive_no_mask_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-DRR-001b: §逆引き表 declares Directive remaining columns no-mask.

        id / target_room_id / created_at / task_id carry no secret semantics
        and are registered as 'masking 対象なし' so over-masking is prevented.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "Directive" in line and "masking 対象なし" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'Directive' and 'masking 対象なし' per "
            "directive-repository §確定 R1-E (partial-mask テンプレート, Issue #34)."
        )


class TestBackIndexHasTaskRows:
    """TC-DOC-TR-001: §逆引き表 includes Task partial-mask + no-mask entries.

    Task Repository PR (#35) is the third partial-mask Aggregate:
    * ``tasks.last_error`` — MaskedText (Task §確定 G 実適用)
    * ``deliverables.body_markdown`` — MaskedText
    * ``conversation_messages.body_markdown`` — MaskedText
    The remaining Task-aggregate columns (task_assigned_agents / conversations /
    conversation_messages の body_markdown 以外 / deliverables の body_markdown
    以外 / deliverable_attachments) are registered as 'masking 対象なし'.
    """

    def test_tasks_last_error_masked_text_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-TR-001a: §逆引き表 declares MaskedText on tasks.last_error.

        The line must co-locate ``tasks`` and ``MaskedText`` so an operator
        scrolling to the Task row sees the redaction policy directly.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "tasks" in line and "MaskedText" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'tasks' and 'MaskedText' per "
            "task-repository §確定 G 実適用 (Issue #35)."
        )

    def test_conversation_messages_bug_tr_002_frozen_row_present(
        self, storage_md_text: str
    ) -> None:
        """TC-DOC-TR-001b: §逆引き表 declares §BUG-TR-002 凍結 for conversation_messages.

        conversation_messages.body_markdown masking is deferred to
        feature/conversation-repository (§BUG-TR-002 凍結). The storage.md
        §逆引き表 must document this frozen state so future PR reviewers can
        identify the pending masking requirement without opening the issue.

        The line must co-locate ``conversation_messages`` (or ``Conversation``)
        and ``BUG-TR-002`` so the frozen state is operator-readable directly.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if ("conversation_messages" in line or "Conversation" in line) and "BUG-TR-002" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'conversation_messages' (or 'Conversation') and "
            "'BUG-TR-002' to document the §BUG-TR-002 凍結 frozen state. "
            "conversation_messages.body_markdown masking is deferred to "
            "feature/conversation-repository PR (Issue #35 §BUG-TR-002)."
        )

    def test_deliverables_body_markdown_masked_text_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-TR-001c: §逆引き表 declares MaskedText on deliverables.body_markdown.

        The line must co-locate ``deliverables`` and ``MaskedText``.
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "deliverables" in line and "MaskedText" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'deliverables' and 'MaskedText' per "
            "task-repository §確定 G 実適用 (Issue #35, deliverable output masking)."
        )

    def test_task_no_mask_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-TR-001d: §逆引き表 declares Task remaining columns no-mask.

        task_assigned_agents / conversations / conversation_messages 除 body_markdown /
        deliverables 除 body_markdown / deliverable_attachments は 'masking 対象なし'
        として登録されており、過剰マスキングを防止する。
        """
        co_located_lines = [
            line
            for line in storage_md_text.splitlines()
            if "Task" in line and "masking 対象なし" in line
        ]
        assert co_located_lines, (
            "storage.md §逆引き表 must contain at least one line that "
            "co-locates 'Task' and 'masking 対象なし' per "
            "task-repository §確定 R1-E (partial-mask テンプレート, Issue #35)."
        )
