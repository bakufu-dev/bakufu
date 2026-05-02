"""websocket-broadcast / domain ユニットテスト（TC-UT-WSB-001〜029）。

設計書: docs/features/websocket-broadcast/domain/test-design.md
対象: REQ-WSB-001〜008 / MSG-WSB-001〜002 / 確定E(Fail Fast)
Issue: #158
"""

from __future__ import annotations

import inspect
import logging
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-WSB-001: DomainEvent 基底クラス
# ---------------------------------------------------------------------------


class TestDomainEventBase:
    """TC-UT-WSB-001〜005: DomainEvent 基底クラスの共通フィールドと to_ws_message()。"""

    def test_event_id_is_uuid(self) -> None:
        """TC-UT-WSB-001: event_id が UUID インスタンスである。"""
        from uuid import UUID

        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        assert isinstance(event.event_id, UUID)

    def test_occurred_at_is_utc_aware(self) -> None:
        """TC-UT-WSB-002: occurred_at が timezone.utc 付き datetime インスタンスである。"""
        from datetime import datetime

        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo is not None
        # UTC タイムゾーン確認: utcoffset() が timedelta(0) であることを検証
        from datetime import timedelta

        assert event.occurred_at.utcoffset() == timedelta(0)

    def test_to_ws_message_keys(self) -> None:
        """TC-UT-WSB-003: to_ws_message() の戻り値は 5 キーのみ持つ。"""
        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        msg = event.to_ws_message()
        assert set(msg.keys()) == {
            "event_type",
            "aggregate_id",
            "aggregate_type",
            "occurred_at",
            "payload",
        }

    def test_occurred_at_in_ws_message_is_iso8601_utc_string(self) -> None:
        """TC-UT-WSB-004: to_ws_message() の occurred_at が ISO 8601 UTC 形式文字列。"""
        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        msg = event.to_ws_message()
        occurred_at_val = msg["occurred_at"]
        assert isinstance(occurred_at_val, str)
        # isoformat() は +00:00 または Z を含む
        assert "+00:00" in occurred_at_val or "Z" in occurred_at_val

    def test_payload_excludes_base_fields(self) -> None:
        """TC-UT-WSB-005: payload に基底クラス 5 フィールドが含まれない。"""
        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        msg = event.to_ws_message()
        payload = msg["payload"]
        base_field_names = {
            "event_id",
            "event_type",
            "aggregate_id",
            "aggregate_type",
            "occurred_at",
        }
        for field_name in base_field_names:
            assert field_name not in payload, f"payload に {field_name} が含まれている"


# ---------------------------------------------------------------------------
# REQ-WSB-002: TaskStateChangedEvent
# ---------------------------------------------------------------------------


class TestTaskStateChangedEvent:
    """TC-UT-WSB-006〜009: TaskStateChangedEvent の正常系・異常系。"""

    def test_instantiation_succeeds(self) -> None:
        """TC-UT-WSB-006: インスタンスが生成される（例外なし）。"""
        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        assert event is not None

    def test_event_type_is_task_state_changed(self) -> None:
        """TC-UT-WSB-007: event_type == "task.state_changed"。"""
        from tests.factories.domain_event_factory import make_task_state_changed_event

        event = make_task_state_changed_event()
        assert event.event_type == "task.state_changed"

    def test_to_ws_message_payload_contains_task_specific_fields(self) -> None:
        """TC-UT-WSB-008: to_ws_message() の payload に task 固有フィールドが含まれる。

        TaskStateChangedEvent の payload は directive_id / old_status /
        new_status / room_id を持つ。aggregate_id (task_id) は基底クラス
        フィールドのため payload に含まれない。
        """
        from bakufu.domain.events import TaskStateChangedEvent

        event = TaskStateChangedEvent(
            aggregate_id="t1",
            directive_id="d1",
            old_status="PENDING",
            new_status="IN_PROGRESS",
            room_id="r1",
        )
        msg = event.to_ws_message()
        assert msg["payload"] == {
            "directive_id": "d1",
            "old_status": "PENDING",
            "new_status": "IN_PROGRESS",
            "room_id": "r1",
        }

    def test_missing_required_field_raises_validation_error(self) -> None:
        """TC-UT-WSB-009: 必須フィールド(directive_id)欠落 → pydantic.ValidationError。"""
        from bakufu.domain.events import TaskStateChangedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskStateChangedEvent(
                aggregate_id="t1",
                # directive_id は省略（必須フィールド）
                old_status="PENDING",
                new_status="IN_PROGRESS",
                room_id="r1",
            )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# REQ-WSB-003: ExternalReviewGateStateChangedEvent
# ---------------------------------------------------------------------------


class TestExternalReviewGateStateChangedEvent:
    """TC-UT-WSB-010〜013: ExternalReviewGateStateChangedEvent の正常系・異常系・境界値。"""

    def test_reviewer_comment_none(self) -> None:
        """TC-UT-WSB-010: reviewer_comment=None でインスタンス生成される（境界値）。"""
        from tests.factories.domain_event_factory import (
            make_external_review_gate_state_changed_event,
        )

        event = make_external_review_gate_state_changed_event(reviewer_comment=None)
        assert event.reviewer_comment is None

    def test_reviewer_comment_string(self) -> None:
        """TC-UT-WSB-011: reviewer_comment="LGTM" でインスタンス生成される。"""
        from tests.factories.domain_event_factory import (
            make_external_review_gate_state_changed_event,
        )

        event = make_external_review_gate_state_changed_event(reviewer_comment="LGTM")
        assert event.reviewer_comment == "LGTM"

    def test_event_type_is_external_review_gate_state_changed(self) -> None:
        """TC-UT-WSB-012: event_type == "external_review_gate.state_changed"。"""
        from tests.factories.domain_event_factory import (
            make_external_review_gate_state_changed_event,
        )

        event = make_external_review_gate_state_changed_event()
        assert event.event_type == "external_review_gate.state_changed"

    def test_missing_required_field_raises_validation_error(self) -> None:
        """TC-UT-WSB-013: 必須フィールド(aggregate_id=gate_id)欠落 → pydantic.ValidationError。"""
        from bakufu.domain.events import ExternalReviewGateStateChangedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExternalReviewGateStateChangedEvent(
                # aggregate_id (gate_id) は省略（必須フィールド）
                task_id="task-1",
                old_status="PENDING",
                new_status="APPROVED",
            )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# REQ-WSB-004: AgentStatusChangedEvent
# ---------------------------------------------------------------------------


class TestAgentStatusChangedEvent:
    """TC-UT-WSB-014〜016: AgentStatusChangedEvent の正常系・異常系。"""

    def test_instantiation_succeeds(self) -> None:
        """TC-UT-WSB-014: インスタンスが生成される（例外なし）。"""
        from tests.factories.domain_event_factory import make_agent_status_changed_event

        event = make_agent_status_changed_event()
        assert event is not None

    def test_event_type_is_agent_status_changed(self) -> None:
        """TC-UT-WSB-015: event_type == "agent.status_changed"。"""
        from tests.factories.domain_event_factory import make_agent_status_changed_event

        event = make_agent_status_changed_event()
        assert event.event_type == "agent.status_changed"

    def test_missing_required_field_raises_validation_error(self) -> None:
        """TC-UT-WSB-016: 必須フィールド(aggregate_id=agent_id)欠落 → pydantic.ValidationError。"""
        from bakufu.domain.events import AgentStatusChangedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentStatusChangedEvent(
                # aggregate_id (agent_id) は省略（必須フィールド）
                room_id="room-1",
                old_status="idle",
                new_status="running",
            )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# REQ-WSB-005: DirectiveCompletedEvent
# ---------------------------------------------------------------------------


class TestDirectiveCompletedEvent:
    """TC-UT-WSB-017〜019: DirectiveCompletedEvent の正常系・異常系。"""

    def test_instantiation_succeeds(self) -> None:
        """TC-UT-WSB-017: インスタンスが生成される（例外なし）。"""
        from tests.factories.domain_event_factory import make_directive_completed_event

        event = make_directive_completed_event()
        assert event is not None

    def test_event_type_is_directive_completed(self) -> None:
        """TC-UT-WSB-018: event_type == "directive.completed"。"""
        from tests.factories.domain_event_factory import make_directive_completed_event

        event = make_directive_completed_event()
        assert event.event_type == "directive.completed"

    def test_missing_required_field_raises_validation_error(self) -> None:
        """TC-UT-WSB-019: 必須フィールド(aggregate_id=directive_id)欠落 → ValidationError。"""
        from bakufu.domain.events import DirectiveCompletedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DirectiveCompletedEvent(
                # aggregate_id (directive_id) は省略（必須フィールド）
                empire_id="empire-1",
                final_status="DONE",
            )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# REQ-WSB-006: EventBusPort Protocol
# ---------------------------------------------------------------------------


class TestEventBusPortProtocol:
    """TC-UT-WSB-020: EventBusPort Protocol に InMemoryEventBus が構造的に適合する。"""

    def test_inmemory_eventbus_satisfies_protocol_structurally(self) -> None:
        """TC-UT-WSB-020: InMemoryEventBus が EventBusPort Protocol に構造的に適合する。

        EventBusPort は @runtime_checkable でないため isinstance チェックは不可。
        EventBusPort が要求するメンバ（subscribe / publish）を InMemoryEventBus が
        全て実装することをシグネチャレベルで確認する（structural subtyping 検証）。
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()

        # EventBusPort が要求する 2 メソッドを持つことを確認
        assert callable(getattr(bus, "subscribe", None)), (
            "InMemoryEventBus は subscribe メソッドを実装していない"
        )
        assert callable(getattr(bus, "publish", None)), (
            "InMemoryEventBus は publish メソッドを実装していない"
        )

        # メソッドシグネチャ検証: subscribe(handler) と publish(event) を持つ
        subscribe_sig = inspect.signature(InMemoryEventBus.subscribe)
        publish_sig = inspect.signature(InMemoryEventBus.publish)
        assert "handler" in subscribe_sig.parameters, "subscribe の引数に 'handler' がない"
        assert "event" in publish_sig.parameters, "publish の引数に 'event' がない"


# ---------------------------------------------------------------------------
# REQ-WSB-007: InMemoryEventBus
# ---------------------------------------------------------------------------


class TestInMemoryEventBus:
    """TC-UT-WSB-021〜027: InMemoryEventBus の正常系・異常系・境界値。"""

    def test_subscribe_adds_handler(self) -> None:
        """TC-UT-WSB-021: subscribe() 後、_handlers リストの長さが 1 増加する。"""
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()
        before = len(bus._handlers)

        async def dummy_handler(event: object) -> None:
            pass

        bus.subscribe(dummy_handler)
        assert len(bus._handlers) == before + 1

    async def test_publish_calls_single_handler(self) -> None:
        """TC-UT-WSB-022: publish() 後、spy handler が event を 1 回受け取る。"""
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.domain_event_factory import make_task_state_changed_event

        bus = InMemoryEventBus()
        received: list[object] = []

        async def spy(event: object) -> None:
            received.append(event)

        bus.subscribe(spy)
        event = make_task_state_changed_event()
        await bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    async def test_publish_with_no_handlers_does_not_raise(self) -> None:
        """TC-UT-WSB-023: ハンドラ未登録の空 EventBus への publish() が
        例外なく完了する（境界値）。
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.domain_event_factory import make_task_state_changed_event

        bus = InMemoryEventBus()
        event = make_task_state_changed_event()
        # 例外が発火しないことを確認
        await bus.publish(event)

    async def test_publish_calls_all_handlers(self) -> None:
        """TC-UT-WSB-024: 3 個の spy handler 全てが event を受け取る（asyncio.gather 並行実行）。"""
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.domain_event_factory import make_task_state_changed_event

        bus = InMemoryEventBus()
        received_counts: list[int] = [0, 0, 0]

        async def spy_0(event: object) -> None:
            received_counts[0] += 1

        async def spy_1(event: object) -> None:
            received_counts[1] += 1

        async def spy_2(event: object) -> None:
            received_counts[2] += 1

        bus.subscribe(spy_0)
        bus.subscribe(spy_1)
        bus.subscribe(spy_2)

        event = make_task_state_changed_event()
        await bus.publish(event)

        assert received_counts == [1, 1, 1]

    async def test_publish_fail_soft_continues_after_handler_exception(self) -> None:
        """TC-UT-WSB-025: 1 個目が例外を発火しても 2 個目の spy handler が受け取る（Fail Soft）。"""
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.domain_event_factory import make_task_state_changed_event

        bus = InMemoryEventBus()
        received: list[object] = []

        async def failing_handler(event: object) -> None:
            raise RuntimeError("synthetic handler failure")

        async def spy(event: object) -> None:
            received.append(event)

        bus.subscribe(failing_handler)
        bus.subscribe(spy)

        event = make_task_state_changed_event()
        await bus.publish(event)

        # 2 個目の spy handler は event を受け取っている
        assert len(received) == 1
        assert received[0] is event

    async def test_publish_logs_warning_on_handler_exception(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-UT-WSB-026: 例外発火ハンドラがある場合、WARNING ログに
        "EventBus handler error:" が含まれる（MSG-WSB-001）。
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.domain_event_factory import make_task_state_changed_event

        bus = InMemoryEventBus()

        async def failing_handler(event: object) -> None:
            raise ValueError("synthetic error for MSG-WSB-001")

        bus.subscribe(failing_handler)

        event = make_task_state_changed_event()
        with caplog.at_level(logging.WARNING, logger="bakufu.infrastructure.event_bus"):
            await bus.publish(event)

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("EventBus handler error:" in msg for msg in warning_messages), (
            f"MSG-WSB-001 ログが見つからない。実際のログ: {warning_messages}"
        )

    async def test_publish_logs_debug_on_completion(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-UT-WSB-027: 正常完了後、DEBUG ログに "DomainEvent published:" が含まれる。

        MSG-WSB-002 静的文字列照合。
        """
        from bakufu.infrastructure.event_bus import InMemoryEventBus

        from tests.factories.domain_event_factory import make_task_state_changed_event

        bus = InMemoryEventBus()
        received: list[object] = []

        async def spy(event: object) -> None:
            received.append(event)

        bus.subscribe(spy)

        event = make_task_state_changed_event()
        with caplog.at_level(logging.DEBUG, logger="bakufu.infrastructure.event_bus"):
            await bus.publish(event)

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("DomainEvent published:" in msg for msg in debug_messages), (
            f"MSG-WSB-002 ログが見つからない。実際のログ: {debug_messages}"
        )


# ---------------------------------------------------------------------------
# 確定E（Fail Fast）: event_bus=None 禁止
# ---------------------------------------------------------------------------


class TestFailFast:
    """TC-UT-WSB-028〜029: Service.__init__ が event_bus を必須引数として要求する（Fail Fast）。"""

    def test_task_service_requires_event_bus(self) -> None:
        """TC-UT-WSB-028: TaskService.__init__ は event_bus 省略を TypeError で拒否する。

        detailed-design.md §確定E: event_bus にはデフォルト値（None を含む）が設定されておらず、
        省略すると Python が TypeError を発火する。
        """
        from bakufu.application.services.task_service import TaskService

        with pytest.raises(TypeError):
            TaskService(  # type: ignore[call-arg]
                task_repo=AsyncMock(),
                room_repo=AsyncMock(),
                agent_repo=AsyncMock(),
                session=AsyncMock(),
                # event_bus は意図的に省略
            )

    def test_external_review_gate_service_requires_event_bus(self) -> None:
        """TC-UT-WSB-029: ExternalReviewGateService.__init__ は event_bus 省略を拒否する。

        detailed-design.md §確定E: event_bus には None デフォルトなし。省略で TypeError。
        """
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )

        with pytest.raises(TypeError):
            ExternalReviewGateService(  # type: ignore[call-arg]
                repo=AsyncMock(),
                template_repo=AsyncMock(),
                # event_bus は意図的に省略
            )


# ---------------------------------------------------------------------------
# §確定B（Fail Fast）: Literal event_type バリデーション
# ---------------------------------------------------------------------------


class TestLiteralEventTypeFailFast:
    """TC-UT-WSB-030〜033: Literal 型 event_type 違反 → ValidationError（§確定 B）。

    event_type は Literal["..."] で構築時バリデーション保証。
    不正な event_type 文字列を渡すと pydantic.ValidationError が即座に発火する。
    """

    def test_task_state_changed_event_rejects_invalid_event_type(self) -> None:
        """TC-UT-WSB-030: TaskStateChangedEvent + event_type="hacked.value" → ValidationError。"""
        from bakufu.domain.events import TaskStateChangedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskStateChangedEvent(
                aggregate_id="t1",
                directive_id="d1",
                old_status="PENDING",
                new_status="IN_PROGRESS",
                room_id="r1",
                event_type="hacked.value",  # type: ignore[arg-type]
            )

    def test_external_review_gate_event_rejects_invalid_event_type(self) -> None:
        """TC-UT-WSB-031: ExternalReviewGateStateChangedEvent Literal 型違反。

        event_type="hacked.value" → pydantic.ValidationError（§確定 B）。
        """
        from bakufu.domain.events import ExternalReviewGateStateChangedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExternalReviewGateStateChangedEvent(
                aggregate_id="g1",
                task_id="task-1",
                old_status="OPEN",
                new_status="PENDING",
                event_type="hacked.value",  # type: ignore[arg-type]
            )

    def test_agent_status_changed_event_rejects_invalid_event_type(self) -> None:
        """TC-UT-WSB-032: AgentStatusChangedEvent + event_type="hacked.value" → ValidationError。"""
        from bakufu.domain.events import AgentStatusChangedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentStatusChangedEvent(
                aggregate_id="a1",
                room_id="room-1",
                old_status="idle",
                new_status="running",
                event_type="hacked.value",  # type: ignore[arg-type]
            )

    def test_directive_completed_event_rejects_invalid_event_type(self) -> None:
        """TC-UT-WSB-033: DirectiveCompletedEvent + event_type="hacked.value" → ValidationError。"""
        from bakufu.domain.events import DirectiveCompletedEvent
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DirectiveCompletedEvent(
                aggregate_id="dir-1",
                empire_id="empire-1",
                final_status="DONE",
                event_type="hacked.value",  # type: ignore[arg-type]
            )
