"""例外ハンドラと CSRF Origin 検証ミドルウェア。

``app.py`` は本パッケージから全ハンドラをインポートする。
サブモジュールは責務単位に分割されている:

* ``_common``: 定数 / ``error_response`` / ``clean_domain_message`` （パッケージ内共有）
* ``core``: HTTP / RequestValidation / Internal / Pydantic ValidationError
* ``empire``: Empire / Room / Workflow / Agent / Directive
* ``task``: Task / Gate
* ``deliverable_template``: DeliverableTemplate / RoleProfile / InvalidRole
* ``middleware``: CsrfOriginMiddleware
"""

from __future__ import annotations

from bakufu.interfaces.http.error_handlers.core import (
    http_exception_handler,
    internal_error_handler,
    pydantic_validation_error_handler,
    validation_error_handler,
)
from bakufu.interfaces.http.error_handlers.deliverable_template import (
    composition_cycle_handler,
    deliverable_template_invariant_violation_handler,
    deliverable_template_not_found_handler,
    deliverable_template_version_downgrade_handler,
    invalid_role_handler,
    role_profile_invariant_violation_handler,
    role_profile_not_found_handler,
)
from bakufu.interfaces.http.error_handlers.empire import (
    agent_archived_handler,
    agent_invariant_violation_handler,
    agent_name_already_exists_handler,
    agent_not_found_handler,
    directive_invariant_violation_handler,
    empire_already_exists_handler,
    empire_archived_handler,
    empire_invariant_violation_handler,
    empire_not_found_handler,
    room_archived_handler,
    room_deliverable_matching_error_handler,
    room_invariant_violation_handler,
    room_name_already_exists_handler,
    room_not_found_handler,
    room_role_override_invariant_violation_handler,
    workflow_archived_handler,
    workflow_invariant_violation_handler,
    workflow_irreversible_handler,
    workflow_not_found_handler,
    workflow_preset_not_found_handler,
)
from bakufu.interfaces.http.error_handlers.middleware import CsrfOriginMiddleware
from bakufu.interfaces.http.error_handlers.task import (
    gate_already_decided_handler,
    gate_authorization_error_handler,
    gate_not_found_handler,
    task_authorization_error_handler,
    task_invariant_violation_handler,
    task_not_found_handler,
    task_state_conflict_handler,
)

__all__ = [
    "CsrfOriginMiddleware",
    "agent_archived_handler",
    "agent_invariant_violation_handler",
    "agent_name_already_exists_handler",
    "agent_not_found_handler",
    "composition_cycle_handler",
    "deliverable_template_invariant_violation_handler",
    "deliverable_template_not_found_handler",
    "deliverable_template_version_downgrade_handler",
    "directive_invariant_violation_handler",
    "empire_already_exists_handler",
    "empire_archived_handler",
    "empire_invariant_violation_handler",
    "empire_not_found_handler",
    "gate_already_decided_handler",
    "gate_authorization_error_handler",
    "gate_not_found_handler",
    "http_exception_handler",
    "internal_error_handler",
    "invalid_role_handler",
    "pydantic_validation_error_handler",
    "role_profile_invariant_violation_handler",
    "role_profile_not_found_handler",
    "room_archived_handler",
    "room_deliverable_matching_error_handler",
    "room_invariant_violation_handler",
    "room_name_already_exists_handler",
    "room_not_found_handler",
    "room_role_override_invariant_violation_handler",
    "task_authorization_error_handler",
    "task_invariant_violation_handler",
    "task_not_found_handler",
    "task_state_conflict_handler",
    "validation_error_handler",
    "workflow_archived_handler",
    "workflow_invariant_violation_handler",
    "workflow_irreversible_handler",
    "workflow_not_found_handler",
    "workflow_preset_not_found_handler",
]
