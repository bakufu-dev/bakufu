"""bakufu ドメイン層のドメイン例外。

各違反は、人間可読な ``message`` と機械処理用の ``detail`` dict
（HTTP API マッパーやテストで利用）に加え、構造化された ``kind`` 判別子を持つ。

各集約別の例外は責務モジュールに分割されている:
* :mod:`.empire` — :class:`EmpireInvariantViolation`
* :mod:`.workflow` — :class:`WorkflowInvariantViolation`, :class:`StageInvariantViolation`
* :mod:`.agent` — :class:`AgentInvariantViolation`
* :mod:`.room` — :class:`RoomInvariantViolation`, :class:`RoomRoleOverrideInvariantViolation`
* :mod:`.directive` — :class:`DirectiveInvariantViolation`
* :mod:`.task` — :class:`TaskInvariantViolation`
* :mod:`.review_gate` — :class:`InternalReviewGateInvariantViolation`,
  :class:`ExternalReviewGateInvariantViolation`
* :mod:`.deliverable_template` — :class:`DeliverableTemplateInvariantViolation`,
  :class:`RoleProfileInvariantViolation`

すべてのシンボルはここから ``from bakufu.domain.exceptions import XYZ`` で
インポートできる（後方互換維持）。
"""

from bakufu.domain.exceptions.agent import AgentInvariantViolation, AgentViolationKind
from bakufu.domain.exceptions.deliverable_template import (
    DeliverableTemplateInvariantViolation,
    DeliverableTemplateViolationKind,
    RoleProfileInvariantViolation,
    RoleProfileViolationKind,
)
from bakufu.domain.exceptions.directive import DirectiveInvariantViolation, DirectiveViolationKind
from bakufu.domain.exceptions.empire import EmpireInvariantViolation, EmpireViolationKind
from bakufu.domain.exceptions.review_gate import (
    ExternalReviewGateInvariantViolation,
    ExternalReviewGateViolationKind,
    InternalReviewGateInvariantViolation,
    InternalReviewGateViolationKind,
)
from bakufu.domain.exceptions.room import (
    RoomInvariantViolation,
    RoomRoleOverrideInvariantViolation,
    RoomRoleOverrideViolationKind,
    RoomViolationKind,
)
from bakufu.domain.exceptions.task import TaskInvariantViolation, TaskViolationKind
from bakufu.domain.exceptions.workflow import (
    StageInvariantViolation,
    StageViolationKind,
    WorkflowInvariantViolation,
    WorkflowViolationKind,
)

__all__ = [
    "AgentInvariantViolation",
    "AgentViolationKind",
    "DeliverableTemplateInvariantViolation",
    "DeliverableTemplateViolationKind",
    "DirectiveInvariantViolation",
    "DirectiveViolationKind",
    "EmpireInvariantViolation",
    "EmpireViolationKind",
    "ExternalReviewGateInvariantViolation",
    "ExternalReviewGateViolationKind",
    "InternalReviewGateInvariantViolation",
    "InternalReviewGateViolationKind",
    "RoleProfileInvariantViolation",
    "RoleProfileViolationKind",
    "RoomInvariantViolation",
    "RoomRoleOverrideInvariantViolation",
    "RoomRoleOverrideViolationKind",
    "RoomViolationKind",
    "StageInvariantViolation",
    "StageViolationKind",
    "TaskInvariantViolation",
    "TaskViolationKind",
    "WorkflowInvariantViolation",
    "WorkflowViolationKind",
]
