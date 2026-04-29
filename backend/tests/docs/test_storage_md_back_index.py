"""storage.md §逆引き表 の契約テスト (TC-DOC-EMR-001)。

``docs/features/empire-repository/test-design.md`` に従う。逆引き表は
「どの DB カラムをマスクするか・どれを明示的にノーマスク宣言するか」の
設計上の真実源であり、CI の三層防御 (grep ガード + アーキテクチャテスト +
本ドキュメントテスト) によって本表を物理的に権威づけする。

今後の Repository PR では各 Aggregate のテーブルに対応する行を追加していくが、
アサーションの形は同一に保たれる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STORAGE_MD = _REPO_ROOT / "docs" / "design" / "domain-model" / "storage.md"


@pytest.fixture(scope="module")
def storage_md_text() -> str:
    """モジュールごとに 1 回だけ storage.md を読み込む(ファイルは小さい)。"""
    assert _STORAGE_MD.is_file(), (
        f"storage.md missing at {_STORAGE_MD}; the §逆引き表 lives there per "
        f"docs/design/domain-model/storage.md."
    )
    return _STORAGE_MD.read_text(encoding="utf-8")


class TestBackIndexHasEmpireRow:
    """TC-DOC-EMR-001: §逆引き表 に Empire の「masking 対象なし」エントリが含まれることを検証。"""

    def test_empire_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-EMR-001: 少なくとも 1 件の Empire 行がノーマスクとして登録されている。

        体裁の変更(表の並び順や言い回しの差し替え)にアサーションが耐えられるよう、
        箇条書きの厳密一致ではなく部分文字列で検査する。存在することが契約であり、
        厳密なフォーマットは設計レビューの管轄である。
        """
        assert "Empire" in storage_md_text, (
            "storage.md must mention Empire so the §逆引き表 can register "
            "the 'masking 対象なし' entry per empire-repository §確定 E."
        )
        # いずれかの日本語表現がノーマスクの意図を凍結する
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
        """TC-DOC-EMR-001: §逆引き表 の行に 'Empire' と 'masking 対象なし' が同居することを検証。

        逆引き表では Empire を Markdown テーブルの 1 行として表現し、3 つの Empire
        テーブルと明示的な「masking 対象なし」宣言を併記する。storage.md の中に
        **少なくとも 1 行**が両方の部分文字列を含んでいることをアサートする ——
        運用者が読みやすさを担保する契約であり、Empire 行までスクロールすれば
        追加のナビゲーションなしにノーマスク宣言を読み取れる。
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
    """TC-DOC-WFR-001: §逆引き表 に Workflow の partial-mask + no-mask エントリが含まれる。

    Workflow PR (#41) は empire-repo のノーマスクテンプレートに加えて
    *partial-mask* テンプレートを導入する: ``workflow_stages.notify_channels_json``
    が Workflow 表面で**唯一**マスクされるカラムであり、``workflows`` /
    ``workflow_transitions`` および ``workflow_stages`` の残りのカラムは
    明示的にノーマスクとして登録される。本契約の両側が ``storage.md``
    の運用者可読な行として記載されていることをアサートする。
    """

    def test_workflow_stages_notify_channels_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-WFR-001a: §逆引き表 が notify カラムに ``MaskedJSONEncoded`` を宣言する。

        運用者が Workflow 行までスクロールすればマスキングポリシーを直接読み取れるよう、
        ``workflow_stages.notify_channels_json`` と ``MaskedJSONEncoded`` が
        同一行に併記されていなければならない。
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
        """TC-DOC-WFR-001b: §逆引き表 が Workflow の残りのカラムをノーマスクとして宣言する。

        契約フレーズは ``Workflow`` と同一行に併記された「masking 対象なし」である
        (これにより partial-mask Aggregate の*非*マスクカラムも Workflow 行から
        直接読み取れる)。
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
    """TC-DOC-AGR-001: §逆引き表 に Agent の partial-mask + no-mask エントリが含まれる。

    Agent Repository PR (#45) は (Workflow に続く) 2 番目の partial-mask
    Aggregate である: ``agents.prompt_body`` が Agent 表面で**唯一**
    マスクされるカラムであり、``agent_providers`` / ``agent_skills`` および
    ``agents`` の残りのカラムはノーマスクとして登録される。本行を通じて
    **Schneier 申し送り #3 实適用クローズ**が文書化される。
    """

    def test_agents_prompt_body_row_present(self, storage_md_text: str) -> None:
        """§逆引き表 が ``agents.prompt_body`` に ``MaskedText`` を宣言する。

        運用者が Agent 行までスクロールすればマスキングポリシーを直接読み取れるよう、
        ``Persona.prompt_body`` (または ``agents.prompt_body``) と ``MaskedText``
        が同一行に併記されていなければならない。
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
        """§逆引き表 が Agent の残りのカラムをノーマスクとして宣言する。

        agent_providers / agent_skills およびその他の agents カラムは
        「masking 対象なし」として登録され、partial-mask の意図が Agent 行から
        直接読み取れるようになっている。
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
    """TC-DOC-DRR-001: §逆引き表 に Directive の partial-mask + no-mask エントリが含まれる。

    Directive Repository PR (#34): ``directives.text`` が**唯一**マスクされる
    カラムであり (directive §確定 G 実適用)、残りのカラム
    (id / target_room_id / created_at / task_id) はノーマスクとして登録される。
    """

    def test_directives_text_masked_text_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-DRR-001a: §逆引き表 が directives.text に MaskedText を宣言する。

        運用者がマスキングポリシーを直接読み取れるよう、``directives.text``
        (または ``Directive.text``) と ``MaskedText`` が同一行に併記されていなければならない。
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
        """TC-DOC-DRR-001b: §逆引き表 が Directive の残りのカラムをノーマスクとして宣言する。

        id / target_room_id / created_at / task_id は秘匿セマンティクスを持たず、
        過剰マスキングを防止するため「masking 対象なし」として登録される。
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
    """TC-DOC-TR-001: §逆引き表 に Task の partial-mask + no-mask エントリが含まれる。

    Task Repository PR (#35) は 3 番目の partial-mask Aggregate である:
    * ``tasks.last_error`` — MaskedText (Task §確定 G 実適用)
    * ``deliverables.body_markdown`` — MaskedText
    * ``conversation_messages.body_markdown`` — MaskedText
    残りの Task Aggregate のカラム (task_assigned_agents / conversations /
    conversation_messages の body_markdown 以外 / deliverables の body_markdown
    以外 / deliverable_attachments) は「masking 対象なし」として登録される。
    """

    def test_tasks_last_error_masked_text_row_present(self, storage_md_text: str) -> None:
        """TC-DOC-TR-001a: §逆引き表 が tasks.last_error に MaskedText を宣言する。

        運用者が Task 行までスクロールすればマスキングポリシーを直接読み取れるよう、
        ``tasks`` と ``MaskedText`` が同一行に併記されていなければならない。
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
        """TC-DOC-TR-001b: §逆引き表 が conversation_messages について §BUG-TR-002 凍結 を宣言する。

        conversation_messages.body_markdown のマスキングは
        feature/conversation-repository に延期されている (§BUG-TR-002 凍結)。
        storage.md §逆引き表 はこの凍結状態を文書化していなければならず、
        これにより今後の PR レビュアーは Issue を開かずに保留中のマスキング
        要求を特定できる。

        凍結状態が直接運用者可読となるよう、``conversation_messages``
        (または ``Conversation``) と ``BUG-TR-002`` が同一行に併記されていなければならない。
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
        """TC-DOC-TR-001c: §逆引き表 が deliverables.body_markdown に MaskedText を宣言する。

        ``deliverables`` と ``MaskedText`` が同一行に併記されていなければならない。
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
        """TC-DOC-TR-001d: §逆引き表 が Task の残りのカラムをノーマスクとして宣言する。

        task_assigned_agents / conversations / conversation_messages 除 body_markdown /
        deliverables 除 body_markdown / deliverable_attachments は「masking 対象なし」
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
