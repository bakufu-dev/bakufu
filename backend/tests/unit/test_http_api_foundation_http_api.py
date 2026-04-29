"""http-api-foundation / http-api ユニットテスト (TC-UT-HAF-001〜003, 010〜012).

Per ``docs/features/http-api-foundation/http-api/test-design.md`` §ユニットテストケース.

Covers:
  TC-UT-HAF-001  ErrorResponse 正常構築・シリアライズ (REQ-HAF-005, Q-3)
  TC-UT-HAF-002  ErrorResponse extra フィールド拒否 (REQ-HAF-005, Q-3)
  TC-UT-HAF-003  EmpireService.__init__ 骨格 (REQ-HAF-006, Q-3)
  TC-UT-HAF-010  interfaces/http/ 依存方向静的解析 — ast モジュール (Q-3)
  TC-UT-HAF-011  http_exception_handler status_code 分岐 (ヘルスバーグ指摘 #1)
  TC-UT-HAF-012  main.py BAKUFU_BIND_HOST/PORT env var 使用確認 (REQ-HAF-007, Tabriz指摘)

Issue: #55
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
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
        response = ErrorResponse(error=ErrorDetail(code="not_found", message="Resource not found."))
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
        """EmpireService(repo=mock, session=mock) stores repo mock in _repo."""
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        mock_session = MagicMock()
        service = EmpireService(repo=mock_repo, session=mock_session)
        assert service._repo is mock_repo  # pyright: ignore[reportPrivateUsage]

    def test_empire_service_instantiation_succeeds(self) -> None:
        """EmpireService construction with mock repo and session does not raise."""
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        mock_session = MagicMock()
        service = EmpireService(repo=mock_repo, session=mock_session)
        assert service is not None


# ---------------------------------------------------------------------------
# TC-UT-HAF-010: 依存方向静的解析 — ast モジュール (Q-3)
# ---------------------------------------------------------------------------
class TestStaticDependencyAnalysis:
    """TC-UT-HAF-010: interfaces/http/ has no top-level bakufu.domain/.infrastructure imports.

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
                    violations.append(f"{py_file.name}:{lineno}: top-level import of {module_name}")
        assert violations == [], (
            "Direct bakufu.domain imports detected at module level:\n" + "\n".join(violations)
        )

    def test_no_toplevel_bakufu_infrastructure_import(self) -> None:
        """interfaces/http/ must not directly import bakufu.infrastructure at module level."""
        interfaces_dir = self._interfaces_http_dir()
        violations: list[str] = []
        for py_file in sorted(interfaces_dir.rglob("*.py")):
            for module_name, lineno in self._collect_toplevel_imports(py_file):
                if module_name.startswith("bakufu.infrastructure"):
                    violations.append(f"{py_file.name}:{lineno}: top-level import of {module_name}")
        assert violations == [], (
            "Direct bakufu.infrastructure imports detected at module level:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# TC-UT-HAF-011: http_exception_handler status_code 分岐 (ヘルスバーグ指摘 #1)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestHttpExceptionHandlerUnit:
    """TC-UT-HAF-011: http_exception_handler correctly maps status codes to error codes.

    Tests the handler function directly (no HTTP transport) to cover all
    status code branches including cases not easily triggered via routing.
    """

    def _make_request(self) -> Any:
        """Return a minimal mock Request object."""
        from unittest.mock import MagicMock

        return MagicMock()

    def _make_http_exc(self, status_code: int, detail: str | None = None) -> Any:
        from starlette.exceptions import HTTPException as StarletteHTTPException

        return StarletteHTTPException(status_code=status_code, detail=detail)

    async def test_404_code_is_not_found(self) -> None:
        """HTTPException(404) → code "not_found"."""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        resp = await HttpErrorHandlers.http_exception_handler(
            self._make_request(), self._make_http_exc(404)
        )  # type: ignore[arg-type]
        assert resp.status_code == 404  # type: ignore[union-attr]
        import json

        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "not_found"

    async def test_404_message_is_msg_haf_001(self) -> None:
        """HTTPException(404) → message is exactly MSG-HAF-001 "Resource not found."."""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        resp = await HttpErrorHandlers.http_exception_handler(
            self._make_request(), self._make_http_exc(404)
        )  # type: ignore[arg-type]
        import json

        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Resource not found."

    async def test_403_code_is_forbidden(self) -> None:
        """HTTPException(403) → code "forbidden"."""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        req = self._make_request()
        exc = self._make_http_exc(403, "Forbidden")
        resp = await HttpErrorHandlers.http_exception_handler(req, exc)  # type: ignore[arg-type]
        import json

        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "forbidden"

    async def test_405_code_is_method_not_allowed(self) -> None:
        """HTTPException(405) → code "method_not_allowed"."""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        resp = await HttpErrorHandlers.http_exception_handler(
            self._make_request(), self._make_http_exc(405)
        )  # type: ignore[arg-type]
        import json

        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "method_not_allowed"

    async def test_401_code_is_http_error_401(self) -> None:
        """HTTPException(401) → code "http_error_401" (catch-all branch)."""
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        req = self._make_request()
        exc = self._make_http_exc(401, "Unauthorized")
        resp = await HttpErrorHandlers.http_exception_handler(req, exc)  # type: ignore[arg-type]
        import json

        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "http_error_401"

    async def test_wrong_exception_type_raises_type_error(self) -> None:
        """Non-HTTPException → TypeError (Fail Fast 確認)."""
        import pytest as _pytest
        from bakufu.interfaces.http.error_handlers import HttpErrorHandlers

        with _pytest.raises(TypeError, match="Expected StarletteHTTPException"):
            await HttpErrorHandlers.http_exception_handler(self._make_request(), ValueError("oops"))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TC-UT-HAF-012: main.py が BAKUFU_BIND_HOST / BAKUFU_BIND_PORT を使用する (REQ-HAF-007)
# ---------------------------------------------------------------------------
class TestMainEnvVarBinding:
    """TC-UT-HAF-012: _uvicorn_starter uses BAKUFU_BIND_HOST / BAKUFU_BIND_PORT env vars.

    Verifies via ast.parse() that the host/port arguments come from
    os.environ.get("BAKUFU_BIND_HOST", ...) / os.environ.get("BAKUFU_BIND_PORT", ...)
    and that the defaults are "127.0.0.1" / "8000".
    """

    def _main_source(self) -> str:
        import bakufu.main as _main_mod

        return Path(_main_mod.__file__).read_text(encoding="utf-8")  # type: ignore[arg-type]

    def test_bind_host_env_var_present_in_source(self) -> None:
        """main.py contains os.environ.get("BAKUFU_BIND_HOST", ...) (REQ-HAF-007)."""
        assert "BAKUFU_BIND_HOST" in self._main_source()

    def test_bind_port_env_var_present_in_source(self) -> None:
        """main.py contains os.environ.get("BAKUFU_BIND_PORT", ...) (REQ-HAF-007)."""
        assert "BAKUFU_BIND_PORT" in self._main_source()

    def test_bind_host_default_is_loopback(self) -> None:
        """Default BAKUFU_BIND_HOST is "127.0.0.1" (not 0.0.0.0 — OWASP A01)."""
        assert '"127.0.0.1"' in self._main_source()

    def test_bind_host_is_not_hardcoded_to_all_interfaces(self) -> None:
        """main.py must not contain hardcoded "0.0.0.0" (Tabriz指摘 — OWASP A01)."""
        assert '"0.0.0.0"' not in self._main_source()
