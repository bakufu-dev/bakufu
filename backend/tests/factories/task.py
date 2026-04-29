"""Task アグリゲートと VO のファクトリ群.

``docs/features/task/test-design.md`` §外部 I/O 依存マップ 準拠。
各ファクトリは本番コンストラクタ経由で *妥当* なデフォルトインスタンスを返し、
結果を :data:`_SYNTHETIC_REGISTRY` に登録する。これにより :func:`is_synthetic`
が後から「ファクトリ由来か」を確認できる ── M1 の 5 兄弟ファクトリ
(empire / workflow / agent / room / directive) で確立された WeakValueDictionary
パターン。

8 つのファクトリを公開する (status ごと + DeliverableFactory + AttachmentFactory)。
これによりセットアップでステートマシンを歩かずに任意のライフサイクル位置へ
到達できる。ファクトリは ``Task.model_validate`` で直接構築する ──
behavior メソッドは呼ばない ── behavior メソッドのテストには、メソッド駆動の
事前変更なしのクリーンな入口状態が必要なため。

本モジュールを本番コードから import してはならない ── 合成データ境界を
監査可能に保つため ``tests/`` 配下に配置されている。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.task import Task
from bakufu.domain.value_objects import (
    Attachment,
    Deliverable,
    TaskStatus,
)
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# モジュールスコープのレジストリ。値は弱参照で保持するので GC 圧は中立 ──
# 「このオブジェクトはファクトリ由来か」をオブジェクト生存中だけ知ればよい。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。

    検査は構造的ではなく ID ベース (``id``)。これにより独立に生成された
    等値の 2 インスタンスは区別される ── ファクトリが返した実オブジェクトのみ
    合成印が付く。
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# AttachmentFactory のデフォルトで使う canonical な 64 桁 hex sha256。
_DEFAULT_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


# ---------------------------------------------------------------------------
# Attachment ファクトリ
# ---------------------------------------------------------------------------
def make_attachment(
    *,
    sha256: str = _DEFAULT_SHA256,
    filename: str = "deliverable.png",
    mime_type: str = "image/png",
    size_bytes: int = 1024,
) -> Attachment:
    """妥当な :class:`Attachment` を構築し合成印を付ける。"""
    attachment = Attachment(
        sha256=sha256,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
    )
    _register(attachment)
    return attachment


# ---------------------------------------------------------------------------
# Deliverable ファクトリ
# ---------------------------------------------------------------------------
def make_deliverable(
    *,
    stage_id: UUID | None = None,
    body_markdown: str = "# Test deliverable",
    attachments: Sequence[Attachment] | None = None,
    committed_by: UUID | None = None,
    committed_at: datetime | None = None,
) -> Deliverable:
    """妥当な :class:`Deliverable` を構築し合成印を付ける。"""
    deliverable = Deliverable(
        stage_id=stage_id if stage_id is not None else uuid4(),
        body_markdown=body_markdown,
        attachments=list(attachments) if attachments is not None else [],
        committed_by=committed_by if committed_by is not None else uuid4(),
        committed_at=committed_at if committed_at is not None else datetime.now(UTC),
    )
    _register(deliverable)
    return deliverable


# ---------------------------------------------------------------------------
# Task ファクトリ ── status ごと + 汎用 make_task
# ---------------------------------------------------------------------------
def make_task(
    *,
    task_id: UUID | None = None,
    room_id: UUID | None = None,
    directive_id: UUID | None = None,
    current_stage_id: UUID | None = None,
    status: TaskStatus = TaskStatus.PENDING,
    assigned_agent_ids: Sequence[UUID] | None = None,
    deliverables: dict[UUID, Deliverable] | None = None,
    last_error: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Task:
    """妥当な :class:`Task` を ``model_validate`` 経由で直接構築する。

    デフォルトは agent 未割り当て、deliverable なし、``last_error=None``
    の PENDING Task ── ``DirectiveService.issue()`` 直後の canonical な
    入口状態。

    注意: ``status=BLOCKED`` は consistency invariant により非空の
    ``last_error`` を要する。BLOCKED Task が要るテストは
    :func:`make_blocked_task` を使うか、``last_error`` を自前で渡すこと。
    """
    now = datetime.now(UTC)
    task = Task.model_validate(
        {
            "id": task_id if task_id is not None else uuid4(),
            "room_id": room_id if room_id is not None else uuid4(),
            "directive_id": directive_id if directive_id is not None else uuid4(),
            "current_stage_id": current_stage_id if current_stage_id is not None else uuid4(),
            "status": status,
            "assigned_agent_ids": (
                list(assigned_agent_ids) if assigned_agent_ids is not None else []
            ),
            "deliverables": dict(deliverables) if deliverables is not None else {},
            "last_error": last_error,
            "created_at": created_at if created_at is not None else now,
            "updated_at": updated_at if updated_at is not None else now,
        }
    )
    _register(task)
    return task


def make_in_progress_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    **overrides: object,
) -> Task:
    """少なくとも 1 件の agent を割り当てた IN_PROGRESS Task を構築する。"""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.IN_PROGRESS,
        assigned_agent_ids=assigned_agent_ids,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_awaiting_review_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    **overrides: object,
) -> Task:
    """AWAITING_EXTERNAL_REVIEW Task を構築する。"""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.AWAITING_EXTERNAL_REVIEW,
        assigned_agent_ids=assigned_agent_ids,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_blocked_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    last_error: str = "AuthExpired: synthetic blocking error",
    **overrides: object,
) -> Task:
    """BLOCKED Task を構築する。consistency のため ``last_error`` 必須。"""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.BLOCKED,
        assigned_agent_ids=assigned_agent_ids,
        last_error=last_error,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_done_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    deliverables: dict[UUID, Deliverable] | None = None,
    **overrides: object,
) -> Task:
    """少なくとも 1 件の deliverable が積まれた DONE Task を構築する。"""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    if deliverables is None:
        d = make_deliverable()
        deliverables = {d.stage_id: d}
    return make_task(
        status=TaskStatus.DONE,
        assigned_agent_ids=assigned_agent_ids,
        deliverables=deliverables,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_cancelled_task(
    *,
    assigned_agent_ids: Sequence[UUID] | None = None,
    **overrides: object,
) -> Task:
    """CANCELLED Task を構築する。``last_error`` は None でなければならない。"""
    if assigned_agent_ids is None:
        assigned_agent_ids = [uuid4()]
    return make_task(
        status=TaskStatus.CANCELLED,
        assigned_agent_ids=assigned_agent_ids,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


__all__ = [
    "is_synthetic",
    "make_attachment",
    "make_awaiting_review_task",
    "make_blocked_task",
    "make_cancelled_task",
    "make_deliverable",
    "make_done_task",
    "make_in_progress_task",
    "make_task",
]
