"""ExternalReviewGate HTTP API service unit tests.

Covers:
  TC-UT-ERG-HTTP-003, TC-UT-ERG-HTTP-004, TC-UT-ERG-HTTP-006,
  TC-UT-ERG-HTTP-007

Issue: #61
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest


class _Begin:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class _Session:
    def begin(self) -> _Begin:
        return _Begin()


class _Repo:
    def __init__(self, gates: list[Any]) -> None:
        self.gates = gates
        self.saved: list[Any] = []

    async def find_pending_by_reviewer(self, reviewer_id: Any) -> list[Any]:
        return [gate for gate in self.gates if gate.reviewer_id == reviewer_id]

    async def find_by_task_id(self, task_id: Any) -> list[Any]:
        return [gate for gate in self.gates if gate.task_id == task_id]

    async def find_by_id(self, gate_id: Any) -> Any | None:
        return next((gate for gate in self.gates if gate.id == gate_id), None)

    async def save(self, gate: Any) -> None:
        self.saved.append(gate)

    async def count(self) -> int:
        return len(self.gates)

    async def count_by_decision(self, decision: Any) -> int:
        return sum(1 for gate in self.gates if gate.decision == decision)


class _TaskRepo:
    def __init__(self, task: Any | None) -> None:
        self.task = task
        self.saved: list[Any] = []

    async def find_by_id(self, task_id: Any) -> Any | None:
        if self.task is not None and self.task.id == task_id:
            return self.task
        return None

    async def save(self, task: Any) -> None:
        self.saved.append(task)


class _RoomRepo:
    def __init__(self, *, room_id: Any, workflow_id: Any) -> None:
        self.room_id = room_id
        self.workflow_id = workflow_id

    async def find_by_id(self, room_id: Any) -> Any | None:
        if room_id != self.room_id:
            return None

        class _Room:
            workflow_id = self.workflow_id

        return _Room()


class _TransitionResolver:
    def __init__(self, transition: Any) -> None:
        self.transition = transition
        self.calls: list[tuple[Any, Any, Any]] = []

    async def find_by_workflow_and_stage(self, workflow_id: Any, stage_id: Any) -> Any | None:
        return None

    async def find_entry_stage_id(self, workflow_id: Any) -> Any | None:
        return None

    async def find_transition_by_workflow_stage_condition(
        self,
        workflow_id: Any,
        stage_id: Any,
        condition: Any,
    ) -> Any | None:
        self.calls.append((workflow_id, stage_id, condition))
        return self.transition


def _make_service(gates: list[Any], repo: _Repo | None = None) -> Any:
    from bakufu.application.services.external_review_gate_service import (
        ExternalReviewGateService,
    )

    room_id = uuid4()
    return ExternalReviewGateService(
        repo if repo is not None else _Repo(gates),
        _Session(),  # type: ignore[arg-type]
        _TaskRepo(None),  # type: ignore[arg-type]
        _RoomRepo(room_id=room_id, workflow_id=uuid4()),  # type: ignore[arg-type]
        _TransitionResolver(None),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
class TestExternalReviewGateService:
    @pytest.mark.parametrize(
        ("missing_name", "task_repo", "room_repo", "workflow_stage_resolver"),
        [
            ("task_repo", None, object(), object()),
            ("room_repo", object(), None, object()),
            ("workflow_stage_resolver", object(), object(), None),
        ],
    )
    async def test_init_rejects_missing_task_transition_dependency(
        self,
        missing_name: str,
        task_repo: object | None,
        room_repo: object | None,
        workflow_stage_resolver: object | None,
    ) -> None:
        """TC-UT-ERG-HTTP-015: Task 遷移依存の欠落は初期化時に fail fast する。"""
        from bakufu.application.services.external_review_gate_service import (
            ExternalReviewGateService,
        )

        with pytest.raises(ValueError, match=missing_name):
            ExternalReviewGateService(
                _Repo([]),
                _Session(),  # type: ignore[arg-type]
                task_repo,  # type: ignore[arg-type]
                room_repo,  # type: ignore[arg-type]
                workflow_stage_resolver,  # type: ignore[arg-type]
            )

    async def test_get_and_record_view_saves_viewed_gate(self) -> None:
        """TC-UT-ERG-HTTP-003: 詳細取得は VIEWED 追記後に save する。"""
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
        )

        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        repo = _Repo([gate])
        service = _make_service([gate], repo)

        viewed = await service.get_and_record_view(
            gate.id,
            AuthenticatedSubject.from_owner_id(reviewer_id),
        )

        assert [entry.action for entry in viewed.audit_trail] == ["VIEWED"]
        assert repo.saved == [viewed]

    async def test_authorization_guard_rejects_different_subject(self) -> None:
        """TC-UT-ERG-HTTP-004: subject.owner_id 不一致は authorization error。"""
        from bakufu.application.exceptions.external_review_gate_exceptions import (
            ExternalReviewGateAuthorizationError,
        )
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
        )

        from tests.factories.external_review_gate import make_gate

        gate = make_gate(reviewer_id=uuid4())
        service = _make_service([gate])

        with pytest.raises(ExternalReviewGateAuthorizationError):
            await service.get_and_record_view(
                gate.id,
                AuthenticatedSubject.from_owner_id(uuid4()),
            )

    async def test_conflict_mapper_converts_decided_gate_violation(self) -> None:
        """TC-UT-ERG-HTTP-006: 既決 Gate の再判断は decision conflict error。"""
        from bakufu.application.exceptions.external_review_gate_exceptions import (
            ExternalReviewGateDecisionConflictError,
        )
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
        )

        from tests.factories.external_review_gate import make_approved_gate

        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        service = _make_service([gate])

        with pytest.raises(ExternalReviewGateDecisionConflictError):
            await service.approve(
                gate.id,
                AuthenticatedSubject.from_owner_id(reviewer_id),
                "again",
            )

    async def test_list_by_task_filters_other_reviewers(self) -> None:
        """TC-UT-ERG-HTTP-007: Task 履歴は subject reviewer の Gate だけ返す。"""
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
        )

        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        task_id = uuid4()
        own_gate = make_gate(task_id=task_id, reviewer_id=reviewer_id)
        other_gate = make_gate(task_id=task_id, reviewer_id=uuid4())
        service = _make_service([own_gate, other_gate])

        gates = await service.list_by_task(
            task_id,
            AuthenticatedSubject.from_owner_id(reviewer_id),
        )

        assert gates == [own_gate]

    async def test_approve_advances_task_to_workflow_approved_transition_target(self) -> None:
        """TC-UT-ERG-HTTP-013: approve は Gate stage ではなく APPROVED 遷移先へ進める。"""
        from bakufu.application.ports.workflow_stage_resolver import WorkflowTransitionContract
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
            ExternalReviewGateService,
        )
        from bakufu.domain.value_objects import TransitionCondition

        from tests.factories.external_review_gate import make_gate
        from tests.factories.task import make_awaiting_review_task

        reviewer_id = uuid4()
        workflow_id = uuid4()
        review_stage_id = uuid4()
        approved_stage_id = uuid4()
        transition = WorkflowTransitionContract(
            id=uuid4(),
            from_stage_id=review_stage_id,
            to_stage_id=approved_stage_id,
            condition=TransitionCondition.APPROVED,
        )
        task = make_awaiting_review_task(current_stage_id=review_stage_id)
        gate = make_gate(task_id=task.id, stage_id=review_stage_id, reviewer_id=reviewer_id)
        task_repo = _TaskRepo(task)
        resolver = _TransitionResolver(transition)
        service = ExternalReviewGateService(
            _Repo([gate]),
            _Session(),  # type: ignore[arg-type]
            task_repo,  # type: ignore[arg-type]
            _RoomRepo(room_id=task.room_id, workflow_id=workflow_id),  # type: ignore[arg-type]
            resolver,  # type: ignore[arg-type]
        )

        await service.approve(gate.id, AuthenticatedSubject.from_owner_id(reviewer_id), "ok")

        assert resolver.calls == [(workflow_id, review_stage_id, TransitionCondition.APPROVED)]
        assert task_repo.saved[0].current_stage_id == approved_stage_id

    async def test_reject_advances_task_to_workflow_rejected_transition_target(self) -> None:
        """TC-UT-ERG-HTTP-014: reject は REJECTED 遷移先 Stage へ差し戻す。"""
        from bakufu.application.ports.workflow_stage_resolver import WorkflowTransitionContract
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
            ExternalReviewGateService,
        )
        from bakufu.domain.value_objects import TransitionCondition

        from tests.factories.external_review_gate import make_gate
        from tests.factories.task import make_awaiting_review_task

        reviewer_id = uuid4()
        workflow_id = uuid4()
        review_stage_id = uuid4()
        rollback_stage_id = uuid4()
        transition = WorkflowTransitionContract(
            id=uuid4(),
            from_stage_id=review_stage_id,
            to_stage_id=rollback_stage_id,
            condition=TransitionCondition.REJECTED,
        )
        task = make_awaiting_review_task(current_stage_id=review_stage_id)
        gate = make_gate(task_id=task.id, stage_id=review_stage_id, reviewer_id=reviewer_id)
        task_repo = _TaskRepo(task)
        resolver = _TransitionResolver(transition)
        service = ExternalReviewGateService(
            _Repo([gate]),
            _Session(),  # type: ignore[arg-type]
            task_repo,  # type: ignore[arg-type]
            _RoomRepo(room_id=task.room_id, workflow_id=workflow_id),  # type: ignore[arg-type]
            resolver,  # type: ignore[arg-type]
        )

        await service.reject(gate.id, AuthenticatedSubject.from_owner_id(reviewer_id), "fix it")

        assert resolver.calls == [(workflow_id, review_stage_id, TransitionCondition.REJECTED)]
        assert task_repo.saved[0].current_stage_id == rollback_stage_id
