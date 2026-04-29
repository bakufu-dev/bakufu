"""Task HTTP API unit tests for Issue #60."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError


def _body(response: Any) -> dict[str, Any]:
    return json.loads(response.body)


@pytest.mark.asyncio
class TestTaskHandlers:
    async def test_not_found_handler_returns_msg(self) -> None:
        """TC-UT-TSH-001〜003: TaskNotFoundError."""
        from bakufu.application.exceptions.task_exceptions import TaskNotFoundError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        response = await HttpErrorHandlers.task_not_found_handler(
            MagicMock(), TaskNotFoundError("task-id")
        )

        assert response.status_code == 404
        assert _body(response)["error"] == {
            "code": "not_found",
            "message": "Task not found.",
        }

    async def test_state_conflict_handler_cleans_message(self) -> None:
        """TC-UT-TSH-004〜005: TaskStateConflictError 前処理."""
        from bakufu.application.exceptions.task_exceptions import TaskStateConflictError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        exc = TaskStateConflictError(
            task_id="task-id",
            current_status="DONE",
            action="assign",
            message="[FAIL] Cannot assign to terminal task.\nNext: stop.",
        )

        response = await HttpErrorHandlers.task_state_conflict_handler(MagicMock(), exc)

        assert response.status_code == 409
        assert _body(response)["error"] == {
            "code": "conflict",
            "message": "Cannot assign to terminal task.",
        }

    async def test_authorization_handler_returns_403(self) -> None:
        """MSG-TS-HTTP-004: TaskAuthorizationError."""
        from bakufu.application.exceptions.task_exceptions import TaskAuthorizationError
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        response = await HttpErrorHandlers.task_authorization_error_handler(
            MagicMock(),
            TaskAuthorizationError("task-id", "assign", "Agent is not a member."),
        )

        assert response.status_code == 403
        assert _body(response)["error"]["code"] == "forbidden"


class TestTaskSchemas:
    def test_assign_accepts_one_agent(self) -> None:
        """TC-UT-TSH-006: TaskAssign 正常系."""
        from bakufu.interfaces.http.schemas.task import TaskAssign

        assert TaskAssign(agent_ids=[uuid4()]).agent_ids

    def test_assign_rejects_empty_agents(self) -> None:
        """TC-UT-TSH-007: TaskAssign min_length."""
        from bakufu.interfaces.http.schemas.task import TaskAssign

        with pytest.raises(ValidationError):
            TaskAssign(agent_ids=[])

    def test_deliverable_create_accepts_valid_body(self) -> None:
        """TC-UT-TSH-008: DeliverableCreate 正常系."""
        from bakufu.interfaces.http.schemas.task import DeliverableCreate

        assert DeliverableCreate(body_markdown="成果物", submitted_by=uuid4(), attachments=[])

    def test_task_response_masks_last_error(self) -> None:
        """TC-UT-TSH-009: TaskResponse.last_error masking."""
        from bakufu.interfaces.http.schemas.task import TaskResponse

        from tests.factories.task import make_blocked_task

        raw = "GITHUB_PAT=ghp_" + "B" * 36
        task = make_blocked_task(last_error=raw)

        dumped = TaskResponse.model_validate(task).model_dump()

        assert raw not in dumped["last_error"]

    def test_deliverable_response_masks_body_markdown(self) -> None:
        """TC-UT-TSH-010: DeliverableResponse.body_markdown masking."""
        from bakufu.interfaces.http.schemas.task import DeliverableResponse

        from tests.factories.task import make_deliverable

        raw = "ANTHROPIC_API_KEY=sk-ant-api03-" + "A" * 40
        deliverable = make_deliverable(body_markdown=raw)

        dumped = DeliverableResponse.model_validate(deliverable).model_dump()

        assert raw not in dumped["body_markdown"]


class TestStaticDependencyAnalysisTask:
    """TC-UT-TSH-011: routers/schemas の domain/infrastructure 直参照禁止."""

    backend_root = Path(__file__).resolve().parents[3]
    targets = (
        backend_root / "src/bakufu/interfaces/http/routers/tasks.py",
        backend_root / "src/bakufu/interfaces/http/schemas/task.py",
    )

    def _imports(self, path: Path) -> list[tuple[str, int]]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: list[tuple[str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.extend((alias.name, node.lineno) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append((node.module, node.lineno))
        return found

    def test_no_domain_or_infrastructure_imports(self) -> None:
        violations = [
            f"{path}:{lineno}:{module}"
            for path in self.targets
            for module, lineno in self._imports(path)
            if module.startswith(("bakufu.domain", "bakufu.infrastructure"))
        ]

        assert violations == []
