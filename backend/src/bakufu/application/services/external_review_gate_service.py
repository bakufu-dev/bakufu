"""ExternalReviewGateService — ExternalReviewGate Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from datetime import datetime

from bakufu.application.exceptions.gate_exceptions import (
    GateAlreadyDecidedError,
    GateAuthorizationError,
    GateNotFoundError,
)
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import GateId, OwnerId, TaskId


class ExternalReviewGateService:
    """ExternalReviewGate Aggregate 操作の application 層サービス。

    reviewer_id 照合責務の凍結: approve / reject / cancel の各メソッドは
    Service 内で ``gate.reviewer_id != reviewer_id`` を照合し、
    GateAuthorizationError を raise する（basic-design.md §確定 UC4 参照）。
    save() はこのクラスに含めない。呼び出し元 router が UoW 内で管理する
    （detailed-design.md §確定E）。
    """

    def __init__(self, repo: ExternalReviewGateRepository) -> None:
        self._repo = repo

    async def find_by_id_or_raise(self, gate_id: GateId) -> ExternalReviewGate:
        """gate_id の Gate を返す。不在の場合は GateNotFoundError を raise。"""
        gate = await self._repo.find_by_id(gate_id)
        if gate is None:
            raise GateNotFoundError(gate_id)
        return gate

    async def find_pending_for_reviewer(self, reviewer_id: OwnerId) -> list[ExternalReviewGate]:
        """reviewer_id の全 PENDING Gate を返す（created_at DESC, id DESC）。"""
        return await self._repo.find_pending_by_reviewer(reviewer_id)

    async def find_by_task(self, task_id: TaskId) -> list[ExternalReviewGate]:
        """task_id の全 Gate を時系列昇順で返す（created_at ASC, id ASC）。"""
        return await self._repo.find_by_task_id(task_id)

    async def approve(
        self,
        gate: ExternalReviewGate,
        reviewer_id: OwnerId,
        comment: str,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """Gate を承認する。

        reviewer_id 照合（→ GateAuthorizationError 403）を Service 内で実行した後、
        domain の gate.approve() に委譲する。
        ExternalReviewGateInvariantViolation(kind='decision_already_decided')
        → GateAlreadyDecidedError (409) に変換する。save() は呼び出し元 router が
        async with session.begin() 内で行う（§確定E）。
        """
        if gate.reviewer_id != reviewer_id:
            raise GateAuthorizationError(
                gate_id=gate.id,
                reviewer_id=reviewer_id,
                expected_reviewer_id=gate.reviewer_id,
            )
        try:
            return gate.approve(by_owner_id=reviewer_id, comment=comment, decided_at=decided_at)
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise GateAlreadyDecidedError(
                    gate_id=gate.id,
                    current_decision=gate.decision,
                ) from exc
            raise

    async def reject(
        self,
        gate: ExternalReviewGate,
        reviewer_id: OwnerId,
        feedback_text: str,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """Gate を差し戻す。

        approve と同構造。domain の gate.reject() に委譲する。
        """
        if gate.reviewer_id != reviewer_id:
            raise GateAuthorizationError(
                gate_id=gate.id,
                reviewer_id=reviewer_id,
                expected_reviewer_id=gate.reviewer_id,
            )
        try:
            return gate.reject(
                by_owner_id=reviewer_id, comment=feedback_text, decided_at=decided_at
            )
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise GateAlreadyDecidedError(
                    gate_id=gate.id,
                    current_decision=gate.decision,
                ) from exc
            raise

    async def cancel(
        self,
        gate: ExternalReviewGate,
        reviewer_id: OwnerId,
        reason: str,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """Gate をキャンセルする。

        approve と同構造。domain の gate.cancel() に委譲する。
        """
        if gate.reviewer_id != reviewer_id:
            raise GateAuthorizationError(
                gate_id=gate.id,
                reviewer_id=reviewer_id,
                expected_reviewer_id=gate.reviewer_id,
            )
        try:
            return gate.cancel(by_owner_id=reviewer_id, reason=reason, decided_at=decided_at)
        except ExternalReviewGateInvariantViolation as exc:
            if exc.kind == "decision_already_decided":
                raise GateAlreadyDecidedError(
                    gate_id=gate.id,
                    current_decision=gate.decision,
                ) from exc
            raise

    async def save(self, gate: ExternalReviewGate) -> None:
        """Gate を永続化する。

        呼び出し元の router handler が `async with session.begin():` 内で
        本メソッドを呼ぶこと（detailed-design.md §確定E）。
        Service 内でトランザクション管理を行わない設計。
        """
        await self._repo.save(gate)
