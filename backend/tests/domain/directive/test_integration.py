"""Directive + DirectiveInvariantViolation 全体のラウンドトリップシナリオ
(TC-IT-DR-001 / 002)。

Directive 機能は domain のみで外部 I/O なし。ここで「integration」は
*aggregate 内モジュール統合* を意味する：Directive ライフサイクルをまたぐ
チェーン動作。元の Directive は各ステップで変更されずに観察される
(frozen + pre-validate rebuild, Confirmation A)。

これらのテストは意図的に production constructors / behaviors を直接組み合わせる —
mocks なし、test-only back doors なし — 記載された受け入れ基準
1, 5, 6 を単一シーケンスで実行。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import (
    make_directive,
    make_linked_directive,
)


class TestDirectiveLifecycleRoundTrip:
    """TC-IT-DR-001: 完全な Directive ライフサイクル (construct → link → re-link rejected)。"""

    def test_full_lifecycle_preserves_immutability(self) -> None:
        """TC-IT-DR-001: construct → link_task → 2 番目の link_task
        が rejected."""
        # Step 1: リンクされていない Directive を構築
        d0 = make_directive()
        assert d0.task_id is None

        # Step 2: Task をリンク。新インスタンスが新 task_id を持つ
        task_id_1 = uuid4()
        d1 = d0.link_task(task_id_1)
        assert d1.task_id == task_id_1

        # Step 3: d1 を再リンク。Fail Fast しなければならない
        task_id_2 = uuid4()
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            d1.link_task(task_id_2)
        assert excinfo.value.kind == "task_already_linked"

        # Step 4: 元の Directives はシーケンス全体で変更されない
        # （frozen + pre-validate rebuild 契約）
        assert d0.task_id is None
        assert d1.task_id == task_id_1

        # Step 5: 構造上の等価性。d0 と d1 は task_id 値が異なるため
        # 等しくない
        assert d0 != d1


class TestRelinkFailureContinuity:
    """TC-IT-DR-002: re-link 失敗により繰り返した試行を超えて状態が分離。"""

    def test_repeated_relink_attempts_do_not_corrupt_state(self) -> None:
        """TC-IT-DR-002: 3 回連続した失敗 re-link で task_id は変化
        しない."""
        existing_task_id = uuid4()
        d = make_linked_directive(task_id=existing_task_id)

        # 3 つの異なる attempted_task_id。各失敗必須
        for _ in range(3):
            new_task_id = uuid4()
            with pytest.raises(DirectiveInvariantViolation) as excinfo:
                d.link_task(new_task_id)
            assert excinfo.value.kind == "task_already_linked"

        # Directive の既存 task_id は intact で生き残る。re-link 契約は
        # 永続的（Confirmation D）
        assert d.task_id == existing_task_id

    def test_relink_failure_does_not_block_unrelated_directives(self) -> None:
        """TC-IT-DR-002 補足: インスタンス間のエラー分離."""
        # Directive A をリンク。re-link は失敗必須
        a = make_linked_directive(task_id=uuid4())
        with pytest.raises(DirectiveInvariantViolation):
            a.link_task(uuid4())

        # 独立した Directive B はまだ通常リンク可能
        b = make_directive()
        new_task_id = uuid4()
        b_linked = b.link_task(new_task_id)
        assert b_linked.task_id == new_task_id
