"""ExternalReviewGateService — ExternalReviewGate Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.external_review_gate_exceptions import (
    ExternalReviewGateAuthorizationError,
    ExternalReviewGateDecisionConflictError,
    ExternalReviewGateNotFoundError,
)
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import GateId, OwnerId, TaskId, TaskStatus


@dataclass(frozen=True, slots=True)
class AuthenticatedSubject:
    """HTTP 認証済み reviewer subject。"""

    owner_id: OwnerId

    @classmethod
    def from_owner_id(cls, owner_id: UUID) -> AuthenticatedSubject:
        """HTTP DI が UUID から subject を明示的に組み立てる入口。"""
        return cls(owner_id=owner_id)


class ExternalReviewGateService:
    """ExternalReviewGate Aggregate 操作の application 層サービス。"""

    def __init__(
        self,
        repo: ExternalReviewGateRepository,
        session: AsyncSession,
        task_repo: TaskRepository | None = None,
    ) -> None:
        self._repo = repo
        self._session = session
        self._task_repo = task_repo

    async def list_pending(self, subject: AuthenticatedSubject) -> list[ExternalReviewGate]:
        """認証済み reviewer の PENDING Gate 一覧を返す。"""
        return await self._repo.find_pending_by_reviewer(subject.owner_id)

    async def list_by_task(
        self,
        task_id: TaskId,
        subject: AuthenticatedSubject,
    ) -> list[ExternalReviewGate]:
        """Task の Gate 履歴から認証済み reviewer の Gate だけを返す。"""
        gates = await self._repo.find_by_task_id(task_id)
        return [gate for gate in gates if gate.reviewer_id == subject.owner_id]

    async def get_and_record_view(
        self,
        gate_id: GateId,
        subject: AuthenticatedSubject,
    ) -> ExternalReviewGate:
        """Gate を取得し、閲覧監査を追記して保存する。"""
        async with self._session.begin():
            gate = await self._find_authorized_gate(gate_id, subject)
            viewed = gate.record_view(subject.owner_id, viewed_at=self._now())
            await self._repo.save(viewed)
        return viewed

    async def approve(
        self,
        gate_id: GateId,
        subject: AuthenticatedSubject,
        comment: str,
    ) -> ExternalReviewGate:
        """PENDING Gate を承認する。"""
        async with self._session.begin():
            gate = await self._find_authorized_gate(gate_id, subject)
            updated = self._decide(gate, subject.owner_id, "approve", comment)
            await self._repo.save(updated)
            await self._advance_task_if_available(updated, subject.owner_id, approved=True)
            return await self._find_saved_gate(updated.id)

    async def reject(
        self,
        gate_id: GateId,
        subject: AuthenticatedSubject,
        feedback_text: str,
    ) -> ExternalReviewGate:
        """PENDING Gate を差し戻す。"""
        async with self._session.begin():
            gate = await self._find_authorized_gate(gate_id, subject)
            updated = self._decide(gate, subject.owner_id, "reject", feedback_text)
            await self._repo.save(updated)
            await self._advance_task_if_available(updated, subject.owner_id, approved=False)
            return await self._find_saved_gate(updated.id)

    async def cancel(
        self,
        gate_id: GateId,
        subject: AuthenticatedSubject,
        reason: str,
    ) -> ExternalReviewGate:
        """PENDING Gate を取り消す。"""
        async with self._session.begin():
            gate = await self._find_authorized_gate(gate_id, subject)
            updated = self._decide(gate, subject.owner_id, "cancel", reason)
            await self._repo.save(updated)
            return await self._find_saved_gate(updated.id)

    async def _find_authorized_gate(
        self,
        gate_id: GateId,
        subject: AuthenticatedSubject,
    ) -> ExternalReviewGate:
        gate = await self._repo.find_by_id(gate_id)
        if gate is None:
            raise ExternalReviewGateNotFoundError(gate_id)
        if gate.reviewer_id != subject.owner_id:
            raise ExternalReviewGateAuthorizationError(gate.id, subject.owner_id)
        return gate

    async def _find_saved_gate(self, gate_id: GateId) -> ExternalReviewGate:
        gate = await self._repo.find_by_id(gate_id)
        if gate is None:
            raise ExternalReviewGateNotFoundError(gate_id)
        return gate

    def _decide(
        self,
        gate: ExternalReviewGate,
        owner_id: OwnerId,
        action: str,
        text: str,
    ) -> ExternalReviewGate:
        try:
            if action == "approve":
                return gate.approve(owner_id, text, decided_at=self._now())
            if action == "reject":
                return gate.reject(owner_id, text, decided_at=self._now())
            if action == "cancel":
                return gate.cancel(owner_id, text, decided_at=self._now())
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise ExternalReviewGateDecisionConflictError(
                    gate.id,
                    gate.decision,
                    action,
                ) from exc
            raise
        raise ValueError(f"Unsupported gate decision action: {action}")

    async def _advance_task_if_available(
        self,
        gate: ExternalReviewGate,
        owner_id: OwnerId,
        *,
        approved: bool,
    ) -> None:
        if self._task_repo is None:
            return
        task = await self._task_repo.find_by_id(gate.task_id)
        if task is None:
            return
        if task.status is not TaskStatus.AWAITING_EXTERNAL_REVIEW:
            return
        if approved:
            updated_task = task.approve_review(
                uuid4(),
                owner_id,
                gate.stage_id,
                updated_at=self._now(),
            )
        else:
            updated_task = task.reject_review(
                uuid4(),
                owner_id,
                gate.stage_id,
                updated_at=self._now(),
            )
        await self._task_repo.save(updated_task)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)


__all__ = ["AuthenticatedSubject", "ExternalReviewGateService"]
