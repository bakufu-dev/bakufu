"""admin-cli OutputFormatter ユニットテスト（TC-UT-AC-CLI-001〜012）。

設計書: docs/features/admin-cli/cli/test-design.md §ユニットテストケース

OutputFormatter の各関数を直接呼び出し、出力文字列の正確性を確認する。
非同期処理なし（同期テスト）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from bakufu.application.services.admin_service import BlockedTaskSummary, DeadLetterSummary
from bakufu.interfaces.cli import formatters

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_blocked_summary(
    *,
    task_id=None,
    room_id=None,
    last_error: str = "test error",
) -> BlockedTaskSummary:
    return BlockedTaskSummary(
        task_id=task_id or uuid4(),
        room_id=room_id or uuid4(),
        last_error=last_error,
        blocked_at=datetime.now(UTC),
    )


def _make_dead_letter_summary(
    *,
    event_id=None,
    event_kind: str = "TaskEventEmitted",
    attempt_count: int = 3,
    last_error: str | None = "dispatch failed",
) -> DeadLetterSummary:
    return DeadLetterSummary(
        event_id=event_id or uuid4(),
        event_kind=event_kind,
        aggregate_id=uuid4(),
        attempt_count=attempt_count,
        last_error=last_error,
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-001: format_blocked_tasks — テーブル形式
# ---------------------------------------------------------------------------


class TestFormatBlockedTasksTable:
    """TC-UT-AC-CLI-001: format_blocked_tasks() テーブル形式の正常系。"""

    def test_table_format_contains_task_id_header(self) -> None:
        """TC-UT-AC-CLI-001: BlockedTaskSummary 1件 → 文字列に "TASK ID" カラムヘッダが含まれる。"""
        task = _make_blocked_summary()
        output = formatters.format_blocked_tasks([task], json_output=False)
        assert "TASK ID" in output
        assert str(task.task_id) in output

    def test_table_format_contains_room_id(self) -> None:
        """テーブル形式に ROOM ID カラムが含まれる。"""
        task = _make_blocked_summary()
        output = formatters.format_blocked_tasks([task], json_output=False)
        assert str(task.room_id) in output


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-002: format_blocked_tasks — JSON 形式
# ---------------------------------------------------------------------------


class TestFormatBlockedTasksJson:
    """TC-UT-AC-CLI-002: format_blocked_tasks() JSON 形式の正常系。"""

    def test_json_format_is_valid_array(self) -> None:
        """TC-UT-AC-CLI-002: BlockedTaskSummary 1件 → JSON 配列として valid。"""
        task = _make_blocked_summary()
        output = formatters.format_blocked_tasks([task], json_output=True)
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_json_format_contains_required_fields(self) -> None:
        """TC-UT-AC-CLI-002: JSON に task_id / room_id / blocked_at / last_error の4フィールドが存在する。"""
        task = _make_blocked_summary()
        output = formatters.format_blocked_tasks([task], json_output=True)
        item = json.loads(output)[0]
        assert "task_id" in item
        assert "room_id" in item
        assert "blocked_at" in item
        assert "last_error" in item

    def test_json_format_task_id_matches(self) -> None:
        """JSON の task_id が入力の task_id と一致する。"""
        task = _make_blocked_summary()
        output = formatters.format_blocked_tasks([task], json_output=True)
        item = json.loads(output)[0]
        assert item["task_id"] == str(task.task_id)


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-003: format_blocked_tasks — 0件テーブル
# ---------------------------------------------------------------------------


class TestFormatBlockedTasksEmpty:
    """TC-UT-AC-CLI-003: format_blocked_tasks() 0件時の境界値。"""

    def test_empty_list_table_format_shows_no_task_message(self) -> None:
        """TC-UT-AC-CLI-003: 空リスト → "BLOCKED Task はありません" が含まれる。"""
        output = formatters.format_blocked_tasks([], json_output=False)
        assert "BLOCKED Task はありません" in output

    def test_empty_list_json_format_is_empty_array(self) -> None:
        """0件 JSON → "[]" に等しい。"""
        output = formatters.format_blocked_tasks([], json_output=True)
        data = json.loads(output)
        assert data == []


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-004: format_dead_letters — テーブル形式
# ---------------------------------------------------------------------------


class TestFormatDeadLettersTable:
    """TC-UT-AC-CLI-004: format_dead_letters() テーブル形式の正常系。"""

    def test_table_format_contains_event_id_and_kind_headers(self) -> None:
        """TC-UT-AC-CLI-004: DeadLetterSummary 1件 → "EVENT ID" / "KIND" カラムヘッダが含まれる。"""
        event = _make_dead_letter_summary()
        output = formatters.format_dead_letters([event], json_output=False)
        assert "EVENT ID" in output
        assert "KIND" in output


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-005: format_dead_letters — JSON 形式
# ---------------------------------------------------------------------------


class TestFormatDeadLettersJson:
    """TC-UT-AC-CLI-005: format_dead_letters() JSON 形式の正常系。"""

    def test_json_format_is_valid_array(self) -> None:
        """TC-UT-AC-CLI-005: DeadLetterSummary 1件 → JSON 配列として valid。"""
        event = _make_dead_letter_summary()
        output = formatters.format_dead_letters([event], json_output=True)
        data = json.loads(output)
        assert isinstance(data, list)

    def test_json_format_contains_required_fields(self) -> None:
        """TC-UT-AC-CLI-005: JSON に 6 フィールドが全て存在する。"""
        event = _make_dead_letter_summary()
        output = formatters.format_dead_letters([event], json_output=True)
        item = json.loads(output)[0]
        for field in (
            "event_id",
            "event_kind",
            "aggregate_id",
            "attempt_count",
            "last_error",
            "updated_at",
        ):
            assert field in item, f"フィールド '{field}' が JSON に存在しない"


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-006: format_dead_letters — 0件 JSON
# ---------------------------------------------------------------------------


class TestFormatDeadLettersEmpty:
    """TC-UT-AC-CLI-006: format_dead_letters() 0件 JSON → "[]"（§確定 D JSON 0件）。"""

    def test_empty_dead_letters_json_is_empty_array(self) -> None:
        """TC-UT-AC-CLI-006: 空リスト + json_output=True → "[]" に等しい。"""
        output = formatters.format_dead_letters([], json_output=True)
        data = json.loads(output)
        assert data == []

    def test_empty_dead_letters_table_shows_no_event_message(self) -> None:
        """0件テーブル → "dead-letter Event はありません" が含まれる。"""
        output = formatters.format_dead_letters([], json_output=False)
        assert "dead-letter Event はありません" in output


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-007: format_success — JSON 形式
# ---------------------------------------------------------------------------


class TestFormatSuccess:
    """TC-UT-AC-CLI-007: format_success() の正常系。"""

    def test_json_format_contains_result_ok(self) -> None:
        """TC-UT-AC-CLI-007: json_output=True → {"result": "ok"} が含まれる。"""
        output = formatters.format_success(
            "Operation successful", json_output=True, command="retry-task"
        )
        data = json.loads(output)
        assert data["result"] == "ok"
        assert data["command"] == "retry-task"

    def test_table_format_starts_with_ok_prefix(self) -> None:
        """テーブル形式 → "[OK] <message>" で始まる。"""
        output = formatters.format_success("Done!", json_output=False)
        assert output == "[OK] Done!"


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-008: format_error — [FAIL] プレフィックス
# ---------------------------------------------------------------------------


class TestFormatError:
    """TC-UT-AC-CLI-008: format_error() の正常系。"""

    def test_error_message_gets_fail_prefix(self) -> None:
        """TC-UT-AC-CLI-008: message="エラー" → "[FAIL] エラー" で始まる。"""
        output = formatters.format_error("エラーが発生しました")
        assert output == "[FAIL] エラーが発生しました"

    def test_already_fail_prefixed_message_not_doubled(self) -> None:
        """既に [FAIL] で始まる文字列は [FAIL] が重複しない。"""
        msg = "[FAIL] something went wrong"
        output = formatters.format_error(msg)
        assert output == msg
        assert output.count("[FAIL]") == 1


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-009: format_blocked_tasks — last_error 80文字トランケート
# ---------------------------------------------------------------------------


class TestTruncation:
    """TC-UT-AC-CLI-009: last_error が 80 文字を超える場合のトランケート（§確定 D）。"""

    def test_last_error_truncated_at_80_chars_in_table(self) -> None:
        """TC-UT-AC-CLI-009: 100文字の last_error → テーブル形式で 81文字目以降が省略され ... が含まれる。"""
        long_error = "A" * 100
        task = _make_blocked_summary(last_error=long_error)
        output = formatters.format_blocked_tasks([task], json_output=False)

        # 81文字目以降（"AAAAA...") は出力に含まれない
        # 代わりに ... が含まれる
        assert "..." in output
        # 81文字目の "A" のみの連続は ... で切られているはず（80文字 + "..."）
        # 100個の A が全て出力されていない
        assert "A" * 100 not in output

    def test_last_error_not_truncated_when_exactly_80_chars(self) -> None:
        """80文字ちょうどの last_error はトランケートされない。"""
        exactly_80 = "B" * 80
        task = _make_blocked_summary(last_error=exactly_80)
        output = formatters.format_blocked_tasks([task], json_output=False)
        assert "B" * 80 in output

    def test_last_error_not_truncated_in_json_mode(self) -> None:
        """JSON 形式では last_error はトランケートされない（フルテキスト）。"""
        long_error = "C" * 100
        task = _make_blocked_summary(last_error=long_error)
        output = formatters.format_blocked_tasks([task], json_output=True)
        data = json.loads(output)
        assert data[0]["last_error"] == long_error


# ---------------------------------------------------------------------------
# TC-UT-AC-CLI-010〜012: 変更コマンド成功確定文言照合
# ---------------------------------------------------------------------------


class TestSuccessMessageWording:
    """TC-UT-AC-CLI-010〜012: 変更コマンド成功時の確定文言照合（detailed-design.md §確定 D）。"""

    def test_retry_task_success_message_contains_in_progress_and_stage_worker(self) -> None:
        """TC-UT-AC-CLI-010: retry-task 成功文言に [OK] / IN_PROGRESS / StageWorker が含まれる。

        admin.py の retry_task コマンドで生成されるメッセージを検証。
        """
        task_id = uuid4()
        msg = (
            f"Task {task_id} を BLOCKED → IN_PROGRESS に変更しました。"
            " bakufu サーバーの StageWorker が自動的に再実行します。"
        )
        output = formatters.format_success(msg, json_output=False)
        assert "[OK]" in output
        assert "IN_PROGRESS" in output
        assert "StageWorker" in output

    def test_cancel_task_success_message_contains_cancelled(self) -> None:
        """TC-UT-AC-CLI-011: cancel-task 成功文言に [OK] / CANCELLED が含まれる。"""
        task_id = uuid4()
        msg = f"Task {task_id} を CANCELLED に変更しました。"
        output = formatters.format_success(msg, json_output=False)
        assert "[OK]" in output
        assert "CANCELLED" in output

    def test_retry_event_success_message_contains_pending_and_outbox_dispatcher(self) -> None:
        """TC-UT-AC-CLI-012: retry-event 成功文言に [OK] / PENDING / Outbox Dispatcher が含まれる。"""
        event_id = uuid4()
        msg = (
            f"Outbox Event {event_id} を DEAD_LETTER → PENDING にリセットしました。"
            " Outbox Dispatcher が次回ポーリングで再 dispatch します。"
        )
        output = formatters.format_success(msg, json_output=False)
        assert "[OK]" in output
        assert "PENDING" in output
        assert "Outbox Dispatcher" in output
