"""Application-layer responsibility boundary tests (TC-UT-DR-018 / 019).

Confirmation G / H freeze that **Aggregate-internal invariants are
structural only**: ``text`` length and ``task_id`` uniqueness. Cross-
aggregate concerns (``target_room_id`` Room existence, ``$``-prefix
normalization, Workflow resolution, Task creation in 1 Tx) live in
``DirectiveService.issue()`` because they require external knowledge.
These tests freeze that boundary so a future refactor cannot silently
push aggregate-level checks into Directive (the regression direction
Norman / Steve worked hard to keep clean for agent / room).
"""

from __future__ import annotations

from uuid import uuid4

from tests.factories.directive import make_directive


class TestTargetRoomIdReferentialIntegrityNotEnforcedByAggregate:
    """TC-UT-DR-018: Aggregate は任意の UUID を ``target_room_id`` として受け入れる。"""

    def test_arbitrary_room_id_constructs(self) -> None:
        """TC-UT-DR-018: Room 存在性は DirectiveService で検証、Directive ではない。"""
        # UUID は任意。該当 Room は存在しない。Aggregate は受け入れるが、
        # 参照完全性はアプリケーション層責務。
        directive = make_directive(target_room_id=uuid4())
        assert directive.target_room_id is not None


class TestDollarPrefixNotNormalizedByAggregate:
    """TC-UT-DR-019: Aggregate は ``text`` を逐語的に保存。``$`` プレフィックス注入はない。"""

    def test_text_without_dollar_prefix_constructs_unchanged(self) -> None:
        """TC-UT-DR-019: ``$`` プレフィックス正規化は DirectiveService 責務。

        ``DirectiveService.issue(raw_text)`` が ``text`` 先頭に ``$`` を
        確保するレイヤー。Aggregate は入力を逐語的に信頼する——
        Agent §確定 I の ``provider_kind`` MVP gating と同パターン。
        """
        # 入力に ``$`` プレフィックスなし、Aggregate はテキストをそのまま保持。
        directive = make_directive(text="ブログ分析機能を作って")
        assert not directive.text.startswith("$")
        assert directive.text == "ブログ分析機能を作って"
