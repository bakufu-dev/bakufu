"""http-api-foundation / http-api ユニットテスト (TC-UT-HAF-001, 002, 003, 010).

Per ``docs/features/http-api-foundation/http-api/test-design.md`` §ユニットテストケース.

Covers:
  TC-UT-HAF-001  ErrorResponse 正常構築・シリアライズ (REQ-HAF-005, Q-3)
  TC-UT-HAF-002  ErrorResponse extra フィールド拒否 (REQ-HAF-005, Q-3)
  TC-UT-HAF-003  EmpireService.__init__ 骨格 (REQ-HAF-006, Q-3)
  TC-UT-HAF-010  interfaces/http/ 依存方向静的解析 — ast モジュール (Q-3)

Issue: #55
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bakufu.interfaces.http.schemas.common import ErrorDetail, ErrorResponse
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# TC-UT-HAF-001: ErrorResponse 正常構築・シリアライズ (REQ-HAF-005, Q-3)
# ---------------------------------------------------------------------------
class TestErrorResponseModel:
    """TC-UT-HAF-001: valid ErrorResponse serializes to expected dict structure."""

    def test_error_response_serializes_to_nested_dict(self) -> None:
        """ErrorResponse.model_dump() produces {"error": {"code": ..., "message": ...}}."""
        response = ErrorResponse(
            error=ErrorDetail(code="not_found", message="Resource not found.")
        )
        assert response.model_dump() == {
            "error": {"code": "not_found", "message": "Resource not found."}
        }

    def test_error_detail_code_is_accessible(self) -> None:
        """ErrorDetail.code is readable after construction."""
        detail = ErrorDetail(code="validation_error", message="bad input")
        assert detail.code == "validation_error"

    def test_error_detail_message_is_accessible(self) -> None:
        """ErrorDetail.message is readable after construction."""
        detail = ErrorDetail(code="internal_error", message="An internal server error occurred.")
        assert detail.message == "An internal server error occurred."

    def test_error_response_error_attribute_is_error_detail(self) -> None:
        """ErrorResponse.error is an ErrorDetail instance."""
        detail = ErrorDetail(code="forbidden", message="CSRF check failed: Origin not allowed.")
        response = ErrorResponse(error=detail)
        assert response.error is detail


# ---------------------------------------------------------------------------
# TC-UT-HAF-002: ErrorResponse extra フィールド拒否 (REQ-HAF-005, Q-3)
# ---------------------------------------------------------------------------
class TestErrorResponseExtraForbid:
    """TC-UT-HAF-002: unknown field raises ValidationError (extra='forbid')."""

    def test_error_response_with_extra_field_raises(self) -> None:
        """ErrorResponse with unexpected_field raises ValidationError."""
        with pytest.raises(ValidationError):
            ErrorResponse.model_validate(
                {
                    "error": {"code": "x", "message": "y"},
                    "unexpected_field": "z",
                }
            )

    def test_error_detail_with_extra_field_raises(self) -> None:
        """ErrorDetail with unexpected_field raises ValidationError."""
        with pytest.raises(ValidationError):
            ErrorDetail.model_validate(
                {
                    "code": "x",
                    "message": "y",
                    "unexpected_field": "z",
                }
            )


# ---------------------------------------------------------------------------
# TC-UT-HAF-003: EmpireService.__init__ 骨格 (REQ-HAF-006, Q-3)
# ---------------------------------------------------------------------------
class TestEmpireServiceSkeleton:
    """TC-UT-HAF-003: EmpireService.__init__ stores repo in _repo."""

    def test_empire_service_stores_repo_in_private_field(self) -> None:
        """EmpireService(repo=mock) stores mock in _repo."""
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        service = EmpireService(repo=mock_repo)
        assert service._repo is mock_repo  # pyright: ignore[reportPrivateUsage]

    def test_empire_service_instantiation_succeeds(self) -> None:
        """EmpireService construction with mock repo does not raise."""
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        service = EmpireService(repo=mock_repo)
        assert service is not None


# ---------------------------------------------------------------------------
# TC-UT-HAF-010: 依存方向静的解析 — ast モジュール (Q-3)
# ---------------------------------------------------------------------------
class TestStaticDependencyAnalysis:
    """TC-UT-HAF-010: interfaces/http/ must not have top-level bakufu.domain / .infrastructure imports.

    Uses ast.parse() to extract module-level (top-level) import/from-import statements
    from every .py file under interfaces/http/.
    Local (inside-function) imports are not restricted by this rule.
    """

    def _interfaces_http_dir(self) -> Path:
        """Resolve the interfaces/http source directory from the installed package."""
        import bakufu.interfaces.http.app as _app_mod

        return Path(_app_mod.__file__).parent  # type: ignore[arg-type]

    def _collect_toplevel_imports(self, py_file: Path) -> list[tuple[str, int]]:
        """Return [(module_name, lineno)] for every top-level import in py_file."""
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        results: list[tuple[str, int]] = []
        for node in tree.body:  # Module.body = top-level statements only
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                results.append((module, node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((alias.name, node.lineno))
        return results

    def test_no_toplevel_bakufu_domain_import(self) -> None:
        """interfaces/http/ must not directly import bakufu.domain at module level."""
        interfaces_dir = self._interfaces_http_dir()
        violations: list[str] = []
        for py_file in sorted(interfaces_dir.rglob("*.py")):
            for module_name, lineno in self._collect_toplevel_imports(py_file):
                if module_name.startswith("bakufu.domain"):
                    violations.append(
                        f"{py_file.name}:{lineno}: top-level import of {module_name}"
                    )
        assert violations == [], (
            "Direct bakufu.domain imports detected at module level:\n"
            + "\n".join(violations)
        )

    def test_no_toplevel_bakufu_infrastructure_import(self) -> None:
        """interfaces/http/ must not directly import bakufu.infrastructure at module level."""
        interfaces_dir = self._interfaces_http_dir()
        violations: list[str] = []
        for py_file in sorted(interfaces_dir.rglob("*.py")):
            for module_name, lineno in self._collect_toplevel_imports(py_file):
                if module_name.startswith("bakufu.infrastructure"):
                    violations.append(
                        f"{py_file.name}:{lineno}: top-level import of {module_name}"
                    )
        assert violations == [], (
            "Direct bakufu.infrastructure imports detected at module level:\n"
            + "\n".join(violations)
        )
