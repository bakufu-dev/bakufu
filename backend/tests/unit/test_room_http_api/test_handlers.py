"""room / http-api ユニットテスト — ハンドラ検証 (TC-UT-RM-HTTP-005).

Covers:
  TC-UT-RM-HTTP-005  room_invariant_violation_handler [FAIL]/Next: 除去 + kind 分岐

Issue: #57
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestRoomInvariantViolationHandler:
    """TC-UT-RM-HTTP-005: room_invariant_violation_handler 前処理ルール + kind 分岐 (確定 C)."""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_name_range_returns_422(self) -> None:
        """(a) kind='name_range' → HTTP 422."""
        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Room name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 422  # type: ignore[union-attr]

    async def test_name_range_error_code_is_validation_error(self) -> None:
        import json

        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Room name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "validation_error"

    async def test_name_range_removes_fail_prefix(self) -> None:
        """[FAIL] プレフィックスが除去され message に含まれないこと (確定 C)."""
        import json

        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Room name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_name_range_removes_next_suffix(self) -> None:
        """\\nNext:.* サフィックスが除去されること (確定 C)."""
        import json

        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Room name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "Next:" not in body["error"]["message"]

    async def test_name_range_message_is_clean_business_text(self) -> None:
        """期待 message: 'Room name は 1〜80 文字でなければなりません。' (前処理後の本文のみ)."""
        import json

        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Room name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Room name は 1〜80 文字でなければなりません。"

    async def test_member_not_found_returns_404(self) -> None:
        """(b) kind='member_not_found' → HTTP 404 (MSG-RM-HTTP-005 分岐確認)."""
        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="member_not_found",
            message="[FAIL] Member not found: agent_id=..., role=LEADER\nNext: ...",
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 404  # type: ignore[union-attr]

    async def test_member_not_found_error_code(self) -> None:
        """kind='member_not_found' → error.code='not_found'."""
        import json

        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="member_not_found",
            message="[FAIL] Member not found\nNext: ...",
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "not_found"

    async def test_member_not_found_error_message(self) -> None:
        """kind='member_not_found' → MSG-RM-HTTP-005 固定文言 (確定 C)."""
        import json

        from bakufu.domain.exceptions import RoomInvariantViolation
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        exc = RoomInvariantViolation(
            kind="member_not_found",
            message="[FAIL] Member not found\nNext: ...",
        )
        resp = await room_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent membership not found in this room."

    async def test_wrong_type_raises_type_error(self) -> None:
        """非 RoomInvariantViolation → TypeError (Fail Fast 確認)."""
        from bakufu.interfaces.http.error_handlers import room_invariant_violation_handler

        with pytest.raises(TypeError, match="Expected RoomInvariantViolation"):
            await room_invariant_violation_handler(self._make_request(), ValueError("oops"))  # type: ignore[arg-type]
