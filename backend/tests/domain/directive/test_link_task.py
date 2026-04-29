"""link_task 振る舞い + 一意性契約テスト（TC-UT-DR-005 / 006 / 016 / 017）.

Confirmation C / D: link_task は task_id を None から実値に正確に 1 回反転。
再リンク（同じ TaskId でも）は常に Fail Fast。コンストラクタ経路
（リポジトリ再構成）は既存 task_id を持つことができる。それは
永続属性値であって遷移ではないため。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestLinkTaskHappyPath:
    """TC-UT-DR-005: link_task は None → 有効な TaskId に反転、
    新インスタンス返却."""

    def test_link_task_returns_directive_with_task_id(self) -> None:
        """TC-UT-DR-005: 返却される Directive は新 task_id を持つ."""
        directive = make_directive()
        task_id = uuid4()
        linked = directive.link_task(task_id)
        assert linked.task_id == task_id

    def test_link_task_does_not_mutate_original(self) -> None:
        """TC-UT-DR-005: 元の Directive.task_id は link_task 後も
        None のまま."""
        directive = make_directive()
        directive.link_task(uuid4())
        assert directive.task_id is None

    def test_linked_directive_preserves_other_attributes(self) -> None:
        """TC-UT-DR-005: task_id のみ変化。id / text / target_room_id /
        created_at は保持."""
        directive = make_directive()
        new_task_id = uuid4()
        linked = directive.link_task(new_task_id)
        assert linked.id == directive.id
        assert linked.text == directive.text
        assert linked.target_room_id == directive.target_room_id
        assert linked.created_at == directive.created_at


class TestLinkTaskRejectsRelink:
    """TC-UT-DR-006: リンク済み Directive の link_task は例外
    （§確定 C）."""

    def test_relink_with_different_task_id_raises(self) -> None:
        """TC-UT-DR-006: 既存 → 新 task_id は
        task_already_linked を発火."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        new_task_id = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(new_task_id)
        assert excinfo.value.kind == "task_already_linked"

    def test_relink_detail_includes_pair_identifiers(self) -> None:
        """TC-UT-DR-006: detail dict は directive_id / existing_task_id
        / attempted_task_id を持つ."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        new_task_id = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(new_task_id)
        detail = excinfo.value.detail
        assert detail.get("directive_id") == str(directive.id)
        assert detail.get("existing_task_id") == str(existing_task_id)
        assert detail.get("attempted_task_id") == str(new_task_id)


class TestLinkTaskNoIdempotency:
    """TC-UT-DR-016: 同じ TaskId 再リンクは例外（§確定 D — 冪等なし）."""

    def test_relink_with_identical_task_id_still_raises(self) -> None:
        """TC-UT-DR-016: 同じ task_id での再リンクは Fail Fast."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        # Confirmation D は「1 リンクのみ、2 回目呼び出しは常に失敗」を
        # 固定。より単純な契約は validator の特殊ケースを回避。
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            directive.link_task(existing_task_id)
        assert excinfo.value.kind == "task_already_linked"


class TestPreValidateRollback:
    """TC-UT-DR-017: 失敗した link_task は元 Directive をそのままに
    （§確定 A）."""

    def test_link_task_failure_does_not_mutate_original(self) -> None:
        """TC-UT-DR-017: 元の Directive.task_id は失敗した再リンク後も
        変化しない."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        with pytest.raises(DirectiveInvariantViolation):
            directive.link_task(uuid4())
        # 元のインスタンスは元の task_id を参照したままである。
        assert directive.task_id == existing_task_id

    def test_failed_relink_can_be_repeated_without_progress(self) -> None:
        """TC-UT-DR-017: 状態破損は繰り返し失敗で蓄積しない."""
        existing_task_id = uuid4()
        directive = make_linked_directive(task_id=existing_task_id)
        # 3 つの異なる試行 task_id。各失敗必須。Directive は
        # 「元にリンク」のまま識別可能
        for _ in range(3):
            with pytest.raises(DirectiveInvariantViolation):
                directive.link_task(uuid4())
        assert directive.task_id == existing_task_id
