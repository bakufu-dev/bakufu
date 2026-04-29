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


@pytest.mark.asyncio
class TestExternalReviewGateService:
    async def test_get_and_record_view_saves_viewed_gate(self) -> None:
        """TC-UT-ERG-HTTP-003: 詳細取得は VIEWED 追記後に save する。"""
        from bakufu.application.services.external_review_gate_service import (
            AuthenticatedSubject,
            ExternalReviewGateService,
        )

        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        gate = make_gate(reviewer_id=reviewer_id)
        repo = _Repo([gate])
        service = ExternalReviewGateService(repo, _Session())  # type: ignore[arg-type]

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
            ExternalReviewGateService,
        )

        from tests.factories.external_review_gate import make_gate

        gate = make_gate(reviewer_id=uuid4())
        service = ExternalReviewGateService(_Repo([gate]), _Session())  # type: ignore[arg-type]

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
            ExternalReviewGateService,
        )

        from tests.factories.external_review_gate import make_approved_gate

        reviewer_id = uuid4()
        gate = make_approved_gate(reviewer_id=reviewer_id)
        service = ExternalReviewGateService(_Repo([gate]), _Session())  # type: ignore[arg-type]

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
            ExternalReviewGateService,
        )

        from tests.factories.external_review_gate import make_gate

        reviewer_id = uuid4()
        task_id = uuid4()
        own_gate = make_gate(task_id=task_id, reviewer_id=reviewer_id)
        other_gate = make_gate(task_id=task_id, reviewer_id=uuid4())
        service = ExternalReviewGateService(_Repo([own_gate, other_gate]), _Session())  # type: ignore[arg-type]

        gates = await service.list_by_task(
            task_id,
            AuthenticatedSubject.from_owner_id(reviewer_id),
        )

        assert gates == [own_gate]
