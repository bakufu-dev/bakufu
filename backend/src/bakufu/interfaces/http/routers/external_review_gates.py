"""ExternalReviewGate HTTP API エンドポイント（REQ-ERG-HTTP-001〜006）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from bakufu.interfaces.http.dependencies import GateServiceDep, SessionDep
from bakufu.interfaces.http.schemas.external_review_gate import (
    GateApprove,
    GateCancel,
    GateDetailResponse,
    GateListResponse,
    GateReject,
    GateResponse,
)

# MSG-ERG-HTTP-004 の確定文言（detailed-design.md §MSG 確定文言表）
_MSG_INVALID_AUTH_HEADER = (
    "[FAIL] Invalid or missing Authorization header.\n"
    "Next: Set the header as: Authorization: Bearer <owner-id> (UUID format)."
)

gates_router = APIRouter(prefix="/api/gates", tags=["external-review-gate"])
task_gates_router = APIRouter(prefix="/api/tasks", tags=["external-review-gate"])


def get_reviewer_id(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> UUID:
    """Authorization: Bearer <owner-id> ヘッダーから OwnerId を抽出する。

    ヘッダー不在 / 形式不正 / UUID 不正の場合は 422 を返す
    （basic-design.md §get_reviewer_id() Depends、detailed-design.md §確定F）。
    公開関数とする根拠: FastAPI Depends() は callable を受け取る標準パターン。
    状態を持たないため MVP スコープでは公開関数で十分（KISS）。
    参照: https://fastapi.tiangolo.com/tutorial/dependencies/
    """
    if authorization is None:
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AUTH_HEADER)
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AUTH_HEADER)
    token = authorization[len("Bearer ") :]
    try:
        return UUID(token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AUTH_HEADER) from exc


ReviewerIdDep = Annotated[UUID, Depends(get_reviewer_id)]


@gates_router.get(
    "",
    response_model=GateListResponse,
    status_code=200,
    summary="PENDING Gate 一覧取得（REQ-ERG-HTTP-001）",
)
async def list_pending_gates(
    reviewer_id: UUID,
    service: GateServiceDep,
    decision: str = "PENDING",
) -> GateListResponse:
    """reviewer_id の PENDING Gate 一覧を返す。

    decision != PENDING の場合は空リストを返す（detailed-design.md §確定A）。
    """
    # NOTE: MVP では decision=PENDING のみ実装。その他は空リスト（§確定A / YAGNI）
    if decision != "PENDING":
        return GateListResponse(items=[], total=0)
    gates = await service.find_pending_for_reviewer(reviewer_id)
    items = [GateResponse.model_validate(gate) for gate in gates]
    return GateListResponse(items=items, total=len(items))


@task_gates_router.get(
    "/{task_id}/gates",
    response_model=GateListResponse,
    status_code=200,
    summary="Task の Gate 履歴取得（REQ-ERG-HTTP-002）",
)
async def list_gates_by_task(
    task_id: UUID,
    service: GateServiceDep,
) -> GateListResponse:
    """task_id の Gate 履歴を時系列昇順で返す。Task 不在でも空リスト。"""
    gates = await service.find_by_task(task_id)
    items = [GateResponse.model_validate(gate) for gate in gates]
    return GateListResponse(items=items, total=len(items))


@gates_router.get(
    "/{gate_id}",
    response_model=GateDetailResponse,
    status_code=200,
    summary="Gate 単件取得（REQ-ERG-HTTP-003）",
)
async def get_gate(
    gate_id: UUID,
    service: GateServiceDep,
) -> GateDetailResponse:
    """Gate 単件を返す（deliverable_snapshot + audit_trail 含む）。

    副作用なし（RFC 9110 §9.3.1 / detailed-design.md §確定D）。
    """
    gate = await service.find_by_id_or_raise(gate_id)
    return GateDetailResponse.model_validate(gate)


@gates_router.post(
    "/{gate_id}/approve",
    response_model=GateDetailResponse,
    status_code=200,
    summary="Gate 承認（REQ-ERG-HTTP-004）",
)
async def approve_gate(
    gate_id: UUID,
    body: GateApprove,
    reviewer_owner_id: ReviewerIdDep,
    service: GateServiceDep,
    session: SessionDep,
) -> GateDetailResponse:
    """Gate を承認する。承認後に Task の状態を更新する。

    reviewer_id 照合は Service 内で実施（basic-design.md §確定 UC4）。
    find_by_id_or_raise と save() の両方を同一 UoW 内で呼ぶ（detailed-design.md §確定E）。
    autobegin 問題回避: SELECT が autobegin を起動する前に begin() を呼ぶ。

    Gate 承認後フロー（§暫定実装: Outbox Dispatcher 未実装のため直接処理）:
    - Workflow の Transition を確認して承認後の次 Stage を決定する
    - 次 Stage がなければ Task を DONE に（task.complete()）
    - 次 Stage があれば Task を IN_PROGRESS に（task.approve_review()）
    """
    from bakufu.domain.value_objects import TaskStatus, TransitionCondition
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    now = datetime.now(UTC)
    async with session.begin():
        gate = await service.find_by_id_or_raise(gate_id)
        updated_gate = await service.approve(
            gate=gate,
            reviewer_id=reviewer_owner_id,
            comment=body.comment,
            decided_at=now,
        )
        await service.save(updated_gate)

        # Task の状態を更新する（§暫定実装）
        from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
            SqliteRoomRepository,
        )

        task_repo = SqliteTaskRepository(session)
        task = await task_repo.find_by_id(gate.task_id)
        if task is not None and task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW:
            # Room → Workflow → Transition を辿って承認後の次 Stage を決定する
            room_repo = SqliteRoomRepository(session)
            room = await room_repo.find_by_id(task.room_id)
            next_stage_id = None
            if room is not None:
                workflow_repo = SqliteWorkflowRepository(session)
                workflow = await workflow_repo.find_by_id(room.workflow_id)
                if workflow is not None:
                    for transition in workflow.transitions:
                        if (
                            transition.from_stage_id == gate.stage_id
                            and transition.condition == TransitionCondition.APPROVED
                        ):
                            next_stage_id = transition.to_stage_id
                            break
            from uuid import uuid4

            if next_stage_id is None:
                # 次 Stage なし → AWAITING_EXTERNAL_REVIEW → IN_PROGRESS → DONE
                # gate.stage_id（EXTERNAL_REVIEW Stage）を current_stage_id として保持し、
                # Task が最後に完了した Stage を記録する（§確定 K）。
                in_progress_task = task.approve_review(
                    transition_id=uuid4(),
                    by_owner_id=reviewer_owner_id,
                    next_stage_id=gate.stage_id,
                    updated_at=now,
                )
                completed_task = in_progress_task.complete(
                    transition_id=uuid4(),
                    by_owner_id=reviewer_owner_id,
                    updated_at=now,
                )
                await task_repo.save(completed_task)
            else:
                # 次 Stage あり → Task を IN_PROGRESS に（StageWorker が別途処理）
                advanced_task = task.approve_review(
                    transition_id=uuid4(),
                    by_owner_id=reviewer_owner_id,
                    next_stage_id=next_stage_id,
                    updated_at=now,
                )
                await task_repo.save(advanced_task)

    return GateDetailResponse.model_validate(updated_gate)


@gates_router.post(
    "/{gate_id}/reject",
    response_model=GateDetailResponse,
    status_code=200,
    summary="Gate 差し戻し（REQ-ERG-HTTP-005）",
)
async def reject_gate(
    gate_id: UUID,
    body: GateReject,
    reviewer_owner_id: ReviewerIdDep,
    service: GateServiceDep,
    session: SessionDep,
) -> GateDetailResponse:
    """Gate を差し戻す。feedback_text は 1 文字以上必須（Pydantic で検証済み）。"""
    async with session.begin():
        gate = await service.find_by_id_or_raise(gate_id)
        updated_gate = await service.reject(
            gate=gate,
            reviewer_id=reviewer_owner_id,
            feedback_text=body.feedback_text,
            decided_at=datetime.now(UTC),
        )
        await service.save(updated_gate)
    return GateDetailResponse.model_validate(updated_gate)


@gates_router.post(
    "/{gate_id}/cancel",
    response_model=GateDetailResponse,
    status_code=200,
    summary="Gate キャンセル（REQ-ERG-HTTP-006）",
)
async def cancel_gate(
    gate_id: UUID,
    body: GateCancel,
    reviewer_owner_id: ReviewerIdDep,
    service: GateServiceDep,
    session: SessionDep,
) -> GateDetailResponse:
    """Gate をキャンセルする。"""
    async with session.begin():
        gate = await service.find_by_id_or_raise(gate_id)
        updated_gate = await service.cancel(
            gate=gate,
            reviewer_id=reviewer_owner_id,
            reason=body.reason,
            decided_at=datetime.now(UTC),
        )
        await service.save(updated_gate)
    return GateDetailResponse.model_validate(updated_gate)


__all__ = ["gates_router", "task_gates_router"]
