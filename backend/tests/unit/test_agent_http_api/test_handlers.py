"""agent / http-api ユニットテスト (TC-UT-AGH-001〜009).

Per ``docs/features/agent/http-api/test-design.md`` §ユニットテストケース.

Covers:
  TC-UT-AGH-001  agent_not_found_handler (MSG-AG-HTTP-001)
  TC-UT-AGH-002  agent_name_already_exists_handler (MSG-AG-HTTP-002)
  TC-UT-AGH-003  agent_archived_handler (MSG-AG-HTTP-003)
  TC-UT-AGH-004  agent_invariant_violation_handler (MSG-AG-HTTP-004 / §確定C 前処理ルール)
  TC-UT-AGH-005  AgentCreate スキーマ (§確定A)
  TC-UT-AGH-006  AgentUpdate スキーマ (§確定A)
  TC-UT-AGH-007  PersonaCreate スキーマ (§確定A)
  TC-UT-AGH-008  PersonaResponse field_serializer masking (R1-9 / T4 / A02)
  TC-UT-AGH-009  依存方向 静的解析 (interfaces → domain / infrastructure 直参照禁止)

Issue: #59
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# TC-UT-AGH-001: agent_not_found_handler (MSG-AG-HTTP-001)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentNotFoundHandler:
    """TC-UT-AGH-001: agent_not_found_handler → 404, code=not_found, MSG-AG-HTTP-001。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_404(self) -> None:
        """AgentNotFoundError → HTTP 404。"""
        from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
        from bakufu.interfaces.http.error_handlers import agent_not_found_handler

        exc = AgentNotFoundError(agent_id="test-id")
        resp = await agent_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 404  # type: ignore[union-attr]

    async def test_error_code_is_not_found(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
        from bakufu.interfaces.http.error_handlers import agent_not_found_handler

        exc = AgentNotFoundError(agent_id="test-id")
        resp = await agent_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "not_found"

    async def test_error_message_is_msg_ag_http_001(self) -> None:
        """MSG-AG-HTTP-001: 確定文言 'Agent not found.'"""
        from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError
        from bakufu.interfaces.http.error_handlers import agent_not_found_handler

        exc = AgentNotFoundError(agent_id="test-id")
        resp = await agent_not_found_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent not found."

    async def test_wrong_exception_type_raises_type_error(self) -> None:
        """非 AgentNotFoundError → TypeError (Fail Fast)。"""
        from bakufu.interfaces.http.error_handlers import agent_not_found_handler

        with pytest.raises(TypeError, match="Expected AgentNotFoundError"):
            await agent_not_found_handler(self._make_request(), ValueError("oops"))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TC-UT-AGH-002: agent_name_already_exists_handler (MSG-AG-HTTP-002)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentNameAlreadyExistsHandler:
    """TC-UT-AGH-002: agent_name_already_exists_handler → 409, code=conflict, MSG-AG-HTTP-002。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_409(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError
        from bakufu.interfaces.http.error_handlers import agent_name_already_exists_handler

        exc = AgentNameAlreadyExistsError(empire_id="eid", name="n")
        resp = await agent_name_already_exists_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 409  # type: ignore[union-attr]

    async def test_error_code_is_conflict(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError
        from bakufu.interfaces.http.error_handlers import agent_name_already_exists_handler

        exc = AgentNameAlreadyExistsError(empire_id="eid", name="n")
        resp = await agent_name_already_exists_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "conflict"

    async def test_error_message_is_msg_ag_http_002(self) -> None:
        """MSG-AG-HTTP-002: 確定文言 'Agent with this name already exists in the Empire.'"""
        from bakufu.application.exceptions.agent_exceptions import AgentNameAlreadyExistsError
        from bakufu.interfaces.http.error_handlers import agent_name_already_exists_handler

        exc = AgentNameAlreadyExistsError(empire_id="eid", name="n")
        resp = await agent_name_already_exists_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent with this name already exists in the Empire."


# ---------------------------------------------------------------------------
# TC-UT-AGH-003: agent_archived_handler (MSG-AG-HTTP-003)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentArchivedHandler:
    """TC-UT-AGH-003: agent_archived_handler → 409, code=conflict, MSG-AG-HTTP-003。"""

    def _make_request(self) -> Any:
        return MagicMock()

    async def test_returns_409(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentArchivedError
        from bakufu.interfaces.http.error_handlers import agent_archived_handler

        exc = AgentArchivedError(agent_id="test-id")
        resp = await agent_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 409  # type: ignore[union-attr]

    async def test_error_code_is_conflict(self) -> None:
        from bakufu.application.exceptions.agent_exceptions import AgentArchivedError
        from bakufu.interfaces.http.error_handlers import agent_archived_handler

        exc = AgentArchivedError(agent_id="test-id")
        resp = await agent_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "conflict"

    async def test_error_message_is_msg_ag_http_003(self) -> None:
        """MSG-AG-HTTP-003: 確定文言 'Agent is archived and cannot be modified.'"""
        from bakufu.application.exceptions.agent_exceptions import AgentArchivedError
        from bakufu.interfaces.http.error_handlers import agent_archived_handler

        exc = AgentArchivedError(agent_id="test-id")
        resp = await agent_archived_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Agent is archived and cannot be modified."


# ---------------------------------------------------------------------------
# TC-UT-AGH-004: agent_invariant_violation_handler (MSG-AG-HTTP-004 / §確定C)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAgentInvariantViolationHandler:
    """TC-UT-AGH-004: agent_invariant_violation_handler — §確定C 前処理ルール。"""

    def _make_request(self) -> Any:
        return MagicMock()

    def _make_exc(self, msg: str) -> Any:
        from bakufu.domain.exceptions import AgentInvariantViolation

        return AgentInvariantViolation(
            kind="default_not_unique",
            message=msg,
        )

    async def test_returns_422_with_fail_prefix(self) -> None:
        """(a) [FAIL] プレフィックス付き入力 → HTTP 422。"""
        from bakufu.interfaces.http.error_handlers import agent_invariant_violation_handler

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 422  # type: ignore[union-attr]

    async def test_fail_prefix_removed(self) -> None:
        """[FAIL] プレフィックスが除去されること (§確定C)。"""
        from bakufu.interfaces.http.error_handlers import agent_invariant_violation_handler

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_next_suffix_removed(self) -> None:
        """\\nNext:.* サフィックスが除去されること (§確定C)。"""
        from bakufu.interfaces.http.error_handlers import agent_invariant_violation_handler

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "Next:" not in body["error"]["message"]

    async def test_clean_message_is_business_text_only(self) -> None:
        """前処理後の message が純粋な業務テキストであること (§確定C)。"""
        from bakufu.interfaces.http.error_handlers import agent_invariant_violation_handler

        exc = self._make_exc(
            "[FAIL] providers must have exactly one default provider."
            "\nNext: set is_default=True for exactly one provider."
        )
        resp = await agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "providers must have exactly one default provider."

    async def test_no_fail_prefix_without_next(self) -> None:
        """(b) [FAIL] のみ（Next: なし）でも正しく前処理されること。"""
        from bakufu.interfaces.http.error_handlers import agent_invariant_violation_handler

        exc = self._make_exc("[FAIL] Agent name は 1〜40 文字でなければなりません。")
        resp = await agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_error_code_is_validation_error(self) -> None:
        from bakufu.interfaces.http.error_handlers import agent_invariant_violation_handler

        exc = self._make_exc("[FAIL] Agent name は 1〜40 文字でなければなりません。")
        resp = await agent_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# TC-UT-AGH-005: AgentCreate スキーマ (§確定A)
# ---------------------------------------------------------------------------
class TestAgentCreateSchema:
    """TC-UT-AGH-005: AgentCreate スキーマ バリデーション (§確定A)。"""

    def _valid_payload(self) -> dict[str, Any]:
        return {
            "name": "ダリオ",
            "persona": {
                "display_name": "ダリオ",
                "archetype": "CEO",
                "prompt_body": "You are helpful.",
            },
            "role": "DEVELOPER",
            "providers": [
                {"provider_kind": "CLAUDE_CODE", "model": "claude-sonnet-4-5", "is_default": True}
            ],
            "skills": [],
        }

    def test_valid_payload_passes(self) -> None:
        """(a) 有効 payload → バリデーション通過。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate

        obj = AgentCreate.model_validate(self._valid_payload())
        assert obj.name == "ダリオ"

    def test_empty_name_raises(self) -> None:
        """(b) name='' → min_length 違反 ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["name"] = ""
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_name_too_long_raises(self) -> None:
        """(c) name=41 文字 → max_length 違反 ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["name"] = "x" * 41
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_empty_providers_raises(self) -> None:
        """(d) providers=[] → min_length=1 違反 ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["providers"] = []
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_extra_field_raises(self) -> None:
        """(e) extra フィールド → extra='forbid' ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["extra_field"] = "z"
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_invalid_role_raises(self) -> None:
        """(f) 不正 role → ValueError ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["role"] = "UNKNOWN_ROLE"
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_invalid_provider_kind_raises(self) -> None:
        """(g) 不正 provider_kind → ValueError ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["providers"] = [
            {"provider_kind": "UNKNOWN_PROVIDER", "model": "x", "is_default": True}
        ]
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)


# ---------------------------------------------------------------------------
# TC-UT-AGH-006: AgentUpdate スキーマ (§確定A)
# ---------------------------------------------------------------------------
class TestAgentUpdateSchema:
    """TC-UT-AGH-006: AgentUpdate スキーマ バリデーション (§確定A)。"""

    def test_all_none_is_valid_noop(self) -> None:
        """(a) 全フィールド None → no-op として有効。"""
        from bakufu.interfaces.http.schemas.agent import AgentUpdate

        obj = AgentUpdate.model_validate({})
        assert obj.name is None

    def test_name_only_update_passes(self) -> None:
        """(b) name のみ指定 → バリデーション通過。"""
        from bakufu.interfaces.http.schemas.agent import AgentUpdate

        obj = AgentUpdate.model_validate({"name": "更新名"})
        assert obj.name == "更新名"

    def test_providers_only_update_passes(self) -> None:
        """(c) providers のみ指定 → バリデーション通過。"""
        from bakufu.interfaces.http.schemas.agent import AgentUpdate

        obj = AgentUpdate.model_validate(
            {
                "providers": [
                    {
                        "provider_kind": "CLAUDE_CODE",
                        "model": "claude-sonnet-4-5",
                        "is_default": True,
                    }
                ]
            }
        )
        assert obj.providers is not None
        assert len(obj.providers) == 1

    def test_empty_name_raises(self) -> None:
        """(d) name='' → min_length 違反 ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentUpdate.model_validate({"name": ""})

    def test_empty_providers_raises(self) -> None:
        """(e) providers=[] → min_length=1 違反 ValidationError。"""
        from bakufu.interfaces.http.schemas.agent import AgentUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentUpdate.model_validate({"providers": []})


# ---------------------------------------------------------------------------
# TC-UT-AGH-007: PersonaCreate スキーマ (§確定A)
# ---------------------------------------------------------------------------
class TestPersonaCreateSchema:
    """TC-UT-AGH-007: PersonaCreate スキーマ バリデーション (§確定A)。"""

    def test_prompt_body_none_passes(self) -> None:
        """(a) prompt_body=None → None のまま通過（masking はレスポンス層で実施）。"""
        from bakufu.interfaces.http.schemas.agent import PersonaCreate

        obj = PersonaCreate.model_validate(
            {"display_name": "テスト", "archetype": "CEO", "prompt_body": None}
        )
        assert obj.prompt_body is None

    def test_prompt_body_raw_token_passes_unchanged(self) -> None:
        """(b) prompt_body に raw token → raw 値のまま通過（domain / レスポンス層に委譲）。"""
        from bakufu.interfaces.http.schemas.agent import PersonaCreate

        raw = "ANTHROPIC_API_KEY=sk-ant-api03-" + "A" * 40
        obj = PersonaCreate.model_validate(
            {"display_name": "テスト", "archetype": "CEO", "prompt_body": raw}
        )
        assert obj.prompt_body == raw

    def test_archetype_none_passes(self) -> None:
        """(c) archetype=None → None のまま通過。"""
        from bakufu.interfaces.http.schemas.agent import PersonaCreate

        obj = PersonaCreate.model_validate(
            {"display_name": "テスト", "archetype": None, "prompt_body": None}
        )
        assert obj.archetype is None


# ---------------------------------------------------------------------------
# TC-UT-AGH-008: PersonaResponse field_serializer masking (R1-9 / T4 / A02)
# ---------------------------------------------------------------------------
class TestPersonaResponseMasking:
    """TC-UT-AGH-008: PersonaResponse field_serializer による prompt_body masking。"""

    _RAW_ANTHROPIC_TOKEN: str = "sk-ant-api03-" + "A" * 40

    def test_prompt_body_raw_token_not_in_serialized(self) -> None:
        """シリアライズ後の prompt_body に raw token が含まれないこと。"""
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=f"ANTHROPIC_API_KEY={self._RAW_ANTHROPIC_TOKEN}",
        )
        serialized = resp.model_dump()
        assert self._RAW_ANTHROPIC_TOKEN not in serialized["prompt_body"]

    def test_prompt_body_is_redacted(self) -> None:
        """シリアライズ後の prompt_body が <REDACTED:ANTHROPIC_KEY> 形式であること。"""
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=f"ANTHROPIC_API_KEY={self._RAW_ANTHROPIC_TOKEN}",
        )
        serialized = resp.model_dump()
        assert "<REDACTED:ANTHROPIC_KEY>" in serialized["prompt_body"]

    def test_already_masked_value_safe_to_re_apply(self) -> None:
        """冪等: 既に masked された値 (<REDACTED:*>) を再適用しても安全であること。"""
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        already_masked = "<REDACTED:ANTHROPIC_KEY>"
        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=already_masked,
        )
        serialized = resp.model_dump()
        # <REDACTED:*> は masking 関数が再適用されても形が変わらないこと
        assert "ANTHROPIC_KEY" in serialized["prompt_body"]

    def test_github_pat_is_redacted(self) -> None:
        """GitHub PAT も <REDACTED:GITHUB_PAT> 形式に masking されること。"""
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        raw_pat = "ghp_" + "Z" * 36
        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=f"GITHUB_PAT={raw_pat}",
        )
        serialized = resp.model_dump()
        assert raw_pat not in serialized["prompt_body"]


# ---------------------------------------------------------------------------
# TC-UT-AGH-009: 依存方向 静的解析 (interfaces → domain / infrastructure 直参照禁止)
# ---------------------------------------------------------------------------
class TestStaticDependencyAnalysis:
    """TC-UT-AGH-009: interfaces/http/ 配下が bakufu.domain / bakufu.infrastructure を
    モジュールトップレベルで直接 import していないこと。

    http-api-foundation TC-UT-HAF-010 と同一検証パターン。
    """

    def _interfaces_http_dir(self) -> Path:
        """interfaces/http ソースディレクトリを取得する。"""
        import bakufu.interfaces.http.app as _app_mod

        return Path(_app_mod.__file__).parent  # type: ignore[arg-type]

    def _collect_toplevel_imports(self, py_file: Path) -> list[tuple[str, int]]:
        """トップレベルの import/from-import を [(module_name, lineno)] で返す。"""
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        results: list[tuple[str, int]] = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                results.append((module, node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((alias.name, node.lineno))
        return results

    def test_no_toplevel_bakufu_domain_import(self) -> None:
        """interfaces/http/ が bakufu.domain をモジュールトップレベルで import しないこと。"""
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
        """interfaces/http/ が bakufu.infrastructure をトップレベルで import しないこと。"""
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
