"""MSG-DR-001 / 002 ワーディング + Next: ヒント物理保証
（TC-UT-DR-022 / 023）.

各 MSG は 2 行構造に従う（Confirmation F、room §確定 I 踏襲）:

    [FAIL] <failure fact>
    Next: <recommended next action>

1 行目は **厳密に** アサート。i18n / リファクタリング後の運用者側
可視化失敗事実の無言漂流を防止。2 行目は先頭 Next: トークンと
トピック フレーズでアサート。設計時ヒント契約は化粧直しに耐え、
「ヒント存在」プロパティは CI で施錠。

MSG-DR-003（型違反）は pydantic.ValidationError 経路を辿る。
test_construction.py でカバー。MSG-DR-004 / 005 はアプリケーション層
（DirectiveService.issue()）に属す。本アグリゲートテストスイート
の対象外。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestMsgDr001TextRange:
    """TC-UT-DR-022: MSG-DR-001 + Next: ヒント."""

    def test_failure_line_matches_exact_wording(self) -> None:
        """TC-UT-DR-022: '[FAIL] Directive text must be 1-10000 ...'
        厳密なプレフィックス."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="a" * 10_001)
        assert excinfo.value.message.startswith(
            "[FAIL] Directive text must be 1-10000 characters (got 10001)"
        )

    def test_next_hint_present_with_topic_phrase(self) -> None:
        """TC-UT-DR-022: 'Next:' ヒントが複数 directive / trim
        トピック フレーズで存在."""
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text="a" * 10_001)
        message = excinfo.value.message
        assert "Next:" in message
        # ヒントはトリミングまたは複数 directive への分割を示す必須
        # （Confirmation F の設計済み Next フレーズ）
        assert ("Trim" in message) or ("multiple directives" in message)


class TestMsgDr002TaskAlreadyLinked:
    """TC-UT-DR-023: MSG-DR-002 + Next: ヒント（新 Directive 発行）."""

    def test_failure_line_includes_pair_identifiers(self) -> None:
        """TC-UT-DR-023: '[FAIL] Directive already has a linked Task: ...'
        フォーマット."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        new_task_id = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(new_task_id)
        message = excinfo.value.message
        assert "[FAIL] Directive already has a linked Task" in message
        assert f"directive_id={directive.id}" in message
        assert f"existing_task_id={existing_task_id}" in message

    def test_next_hint_advises_new_directive_and_states_one_to_one(self) -> None:
        """TC-UT-DR-023: 'Next:' ヒントが新 Directive 発行 + 1:1 設計文
        を言及."""
        directive = make_linked_directive(task_id=uuid4())
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(uuid4())
        message = excinfo.value.message
        assert "Next:" in message
        assert "Issue a new Directive" in message
        # Confirmation F の設計文: 「1 つの Directive は 1 つの Task に
        # マップされる」
        assert "one Directive maps to one Task" in message
