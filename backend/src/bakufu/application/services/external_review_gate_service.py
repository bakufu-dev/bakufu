"""ExternalReviewGateService — ExternalReviewGate Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from bakufu.application.exceptions.gate_exceptions import (
    GateAlreadyDecidedError,
    GateAuthorizationError,
    GateNotFoundError,
)
from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import (
    AcceptanceCriterion,
    Deliverable,
    GateId,
    OwnerId,
    StageId,
    TaskId,
)


class ExternalReviewGateService:
    """ExternalReviewGate Aggregate 操作の application 層サービス。

    reviewer_id 照合責務の凍結: approve / reject / cancel の各メソッドは
    Service 内で ``gate.reviewer_id != reviewer_id`` を照合し、
    GateAuthorizationError を raise する（basic-design.md §確定 UC4 参照）。
    save() はこのクラスに含めない。呼び出し元 router が UoW 内で管理する
    （detailed-design.md §確定E）。

    criteria 収集責務（§確定 J、R1-J）: create() は Stage.required_deliverables
    に紐づく各 DeliverableTemplate.acceptance_criteria を引き込み、
    ``required_deliverable_criteria`` として Gate に渡す。
    """

    def __init__(
        self,
        repo: ExternalReviewGateRepository,
        template_repo: DeliverableTemplateRepository,
    ) -> None:
        self._repo = repo
        self._template_repo = template_repo

    async def create(
        self,
        *,
        task_id: TaskId,
        stage_id: StageId,
        deliverable_snapshot: Deliverable,
        reviewer_id: OwnerId,
        required_deliverable_template_ids: list[object],
        created_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING の ExternalReviewGate を生成して返す（保存は呼び出し元の責務）。

        Stage.required_deliverables に紐づく各 DeliverableTemplate の
        acceptance_criteria を引き込み、``required_deliverable_criteria`` として
        Gate に snapshot する（§確定 J、R1-J）。

        Args:
            task_id: 対象 Task の ID。
            stage_id: EXTERNAL_REVIEW kind の Stage ID。
            deliverable_snapshot: Gate 生成時の成果物スナップショット（§確定 D）。
            reviewer_id: 人間レビュワー（CEO）の OwnerId。
            required_deliverable_template_ids: Stage.required_deliverables から
                収集した DeliverableTemplateId のリスト。各 template の
                acceptance_criteria を収集するために使用する。
            created_at: Gate 起票時刻（呼び出し元が datetime.now(UTC) で生成）。

        Returns:
            PENDING 状態の新規 ExternalReviewGate。呼び出し元が
            ``async with session.begin():`` 内で ``save()`` する。
        """
        # Stage.required_deliverables から各 DeliverableTemplate の acceptance_criteria
        # を収集する（§確定 J - GateService の責務）。
        # 重複 criterion.id は先頭出現を保持して除去し、tuple 順序は
        # template_ids の順序 × 各 template 内の順序で決まる。
        seen_ids: set[object] = set()
        all_criteria: list[AcceptanceCriterion] = []
        for template_id in required_deliverable_template_ids:
            template = await self._template_repo.find_by_id(template_id)  # type: ignore[arg-type]
            if template is None:
                continue
            for criterion in template.acceptance_criteria:
                if criterion.id not in seen_ids:
                    seen_ids.add(criterion.id)
                    all_criteria.append(criterion)

        return ExternalReviewGate(
            id=GateId(uuid4()),
            task_id=task_id,
            stage_id=stage_id,
            deliverable_snapshot=deliverable_snapshot,
            reviewer_id=reviewer_id,
            required_deliverable_criteria=tuple(all_criteria),
            created_at=created_at,
        )

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
