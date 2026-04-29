"""bakufu ドメインの ID 型エイリアス。

全ての識別子は ``UUID``（本番では UUIDv4）上の PEP 695 ``type`` エイリアス。
呼び出し箇所が明確に読めるよう概念的に区別されており、将来 ``NewType`` への
refinement を行っても破壊的変更にならない。
"""

from __future__ import annotations

from uuid import UUID

# ---------------------------------------------------------------------------
# 識別子型
# ---------------------------------------------------------------------------
type EmpireId = UUID
"""Empire Aggregate 識別子（domain-model/value-objects.md に従い UUIDv4）。"""

type RoomId = UUID
"""Room Aggregate 識別子（UUIDv4）。"""

type AgentId = UUID
"""Agent Aggregate 識別子（UUIDv4）。"""

type WorkflowId = UUID
"""Workflow Aggregate 識別子（UUIDv4）。"""

type StageId = UUID
"""Stage Entity 識別子（Workflow Aggregate 内）。"""

type TransitionId = UUID
"""Transition Entity 識別子（Workflow Aggregate 内）。"""

type SkillId = UUID
"""Skill 識別子（Agent Aggregate 内の :class:`SkillRef` から参照）。"""

type DirectiveId = UUID
"""Directive Aggregate 識別子（UUIDv4）。"""

type TaskId = UUID
"""Task Aggregate 識別子（UUIDv4）。:class:`Directive` から ``task_id`` で参照
される。Task Aggregate 本体は :mod:`bakufu.domain.task` に存在する。"""

type OwnerId = UUID
"""Owner / Reviewer 識別子（domain-model/value-objects.md に従い UUIDv4）。

外部レビュー アクタを記録する Task Aggregate の振る舞い（``approve_review`` /
``reject_review`` / ``advance_to_next`` / ``complete`` / ``cancel``）が使用する。
``OwnerId`` はドメインから見て不透明として扱う。ユーザ アカウントへの紐付けは
アプリケーション層の責務。"""

type GateId = UUID
"""ExternalReviewGate Aggregate 識別子（UUIDv4）。

Gate は Task から独立している（独自のライフサイクル、Tx 境界を持ち、複数の
レビュー ラウンドをサポートする）ため、親の ``TaskId`` を継承せず独自の UUID
を持つ — external-review-gate detailed-design §確定 R1-A。"""

type InternalGateId = UUID
"""InternalReviewGate Aggregate 識別子（UUIDv4）。

``INTERNAL_REVIEW`` Stage の完了をゲートする内部（エージェント間）レビュー Gate
用で、:data:`GateId` と並列。"""


__all__ = [
    "AgentId",
    "DirectiveId",
    "EmpireId",
    "GateId",
    "InternalGateId",
    "OwnerId",
    "RoomId",
    "SkillId",
    "StageId",
    "TaskId",
    "TransitionId",
    "WorkflowId",
]
