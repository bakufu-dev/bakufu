"""Directive HTTP API unit tests for Issue #60."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError


def _body(response: Any) -> dict[str, Any]:
    return json.loads(response.body)


@pytest.mark.asyncio
class TestDirectiveInvariantViolationHandler:
    async def test_fail_prefix_and_next_suffix_are_removed(self) -> None:
        """TC-UT-DRH-001: MSG-DR-HTTP-001 前処理."""
        from bakufu.domain.exceptions import DirectiveInvariantViolation
        from bakufu.interfaces.http.error_handlers import directive_invariant_violation_handler

        exc = DirectiveInvariantViolation(
            kind="text_range",
            message="[FAIL] text must not be empty.\nNext: provide non-empty text.",
        )

        response = await directive_invariant_violation_handler(MagicMock(), exc)

        assert response.status_code == 422
        assert _body(response)["error"]["message"] == "text must not be empty."

    async def test_error_code_is_validation_error(self) -> None:
        """TC-UT-DRH-002: error.code."""
        from bakufu.domain.exceptions import DirectiveInvariantViolation
        from bakufu.interfaces.http.error_handlers import directive_invariant_violation_handler

        exc = DirectiveInvariantViolation(kind="text_range", message="bad directive")

        response = await directive_invariant_violation_handler(MagicMock(), exc)

        assert _body(response)["error"]["code"] == "validation_error"


class TestDirectiveSchemas:
    def test_create_accepts_non_empty_text(self) -> None:
        """TC-UT-DRH-003: DirectiveCreate 正常系."""
        from bakufu.interfaces.http.schemas.directive import DirectiveCreate

        assert DirectiveCreate(text="ブログ分析機能を実装してください").text

    def test_create_rejects_empty_text(self) -> None:
        """TC-UT-DRH-004: DirectiveCreate min_length."""
        from bakufu.interfaces.http.schemas.directive import DirectiveCreate

        with pytest.raises(ValidationError):
            DirectiveCreate(text="")

    def test_response_masks_text(self) -> None:
        """TC-UT-DRH-005: DirectiveResponse.text masking."""
        from bakufu.interfaces.http.schemas.directive import DirectiveResponse

        from tests.factories.directive import make_directive

        raw = "ANTHROPIC_API_KEY=sk-ant-api03-" + "A" * 40
        directive = make_directive(text=raw)

        dumped = DirectiveResponse.model_validate(directive).model_dump()

        assert raw not in dumped["text"]


class TestStaticDependencyAnalysisDirective:
    """TC-UT-DRH-006: routers/schemas の domain/infrastructure 直参照禁止."""

    targets = (
        Path("src/bakufu/interfaces/http/routers/directives.py"),
        Path("src/bakufu/interfaces/http/schemas/directive.py"),
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
