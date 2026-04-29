"""agent / http-api スキーマと静的解析ユニットテスト (TC-UT-AGH-005〜009)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest


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
        from bakufu.interfaces.http.schemas.agent import AgentCreate

        obj = AgentCreate.model_validate(self._valid_payload())
        assert obj.name == "ダリオ"

    def test_empty_name_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["name"] = ""
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_name_too_long_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["name"] = "x" * 41
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_empty_providers_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["providers"] = []
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_extra_field_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["extra_field"] = "z"
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_invalid_role_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["role"] = "UNKNOWN_ROLE"
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)

    def test_invalid_provider_kind_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentCreate
        from pydantic import ValidationError

        payload = self._valid_payload()
        payload["providers"] = [
            {"provider_kind": "UNKNOWN_PROVIDER", "model": "x", "is_default": True}
        ]
        with pytest.raises(ValidationError):
            AgentCreate.model_validate(payload)


class TestAgentUpdateSchema:
    """TC-UT-AGH-006: AgentUpdate スキーマ バリデーション (§確定A)。"""

    def test_all_none_is_valid_noop(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentUpdate

        obj = AgentUpdate.model_validate({})
        assert obj.name is None

    def test_name_only_update_passes(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentUpdate

        obj = AgentUpdate.model_validate({"name": "更新名"})
        assert obj.name == "更新名"

    def test_providers_only_update_passes(self) -> None:
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
        from bakufu.interfaces.http.schemas.agent import AgentUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentUpdate.model_validate({"name": ""})

    def test_empty_providers_raises(self) -> None:
        from bakufu.interfaces.http.schemas.agent import AgentUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentUpdate.model_validate({"providers": []})


class TestPersonaCreateSchema:
    """TC-UT-AGH-007: PersonaCreate スキーマ バリデーション (§確定A)。"""

    def test_prompt_body_none_passes(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaCreate

        obj = PersonaCreate.model_validate(
            {"display_name": "テスト", "archetype": "CEO", "prompt_body": None}
        )
        assert obj.prompt_body is None

    def test_prompt_body_raw_token_passes_unchanged(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaCreate

        raw = "ANTHROPIC_API_KEY=sk-ant-api03-" + "A" * 40
        obj = PersonaCreate.model_validate(
            {"display_name": "テスト", "archetype": "CEO", "prompt_body": raw}
        )
        assert obj.prompt_body == raw

    def test_archetype_none_passes(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaCreate

        obj = PersonaCreate.model_validate(
            {"display_name": "テスト", "archetype": None, "prompt_body": None}
        )
        assert obj.archetype is None


class TestPersonaResponseMasking:
    """TC-UT-AGH-008: PersonaResponse field_serializer による prompt_body masking。"""

    _RAW_ANTHROPIC_TOKEN: str = "sk-ant-api03-" + "A" * 40

    def test_prompt_body_raw_token_not_in_serialized(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=f"ANTHROPIC_API_KEY={self._RAW_ANTHROPIC_TOKEN}",
        )
        serialized = resp.model_dump()
        assert self._RAW_ANTHROPIC_TOKEN not in serialized["prompt_body"]

    def test_prompt_body_is_redacted(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=f"ANTHROPIC_API_KEY={self._RAW_ANTHROPIC_TOKEN}",
        )
        serialized = resp.model_dump()
        assert "<REDACTED:ANTHROPIC_KEY>" in serialized["prompt_body"]

    def test_already_masked_value_safe_to_re_apply(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body="<REDACTED:ANTHROPIC_KEY>",
        )
        serialized = resp.model_dump()
        assert "ANTHROPIC_KEY" in serialized["prompt_body"]

    def test_github_pat_is_redacted(self) -> None:
        from bakufu.interfaces.http.schemas.agent import PersonaResponse

        raw_pat = "ghp_" + "Z" * 36
        resp = PersonaResponse(
            display_name="テスト",
            archetype="CEO",
            prompt_body=f"GITHUB_PAT={raw_pat}",
        )
        serialized = resp.model_dump()
        assert raw_pat not in serialized["prompt_body"]


class TestStaticDependencyAnalysisAgent:
    """TC-UT-AGH-009: routers/ + schemas/ の直接依存禁止を AST で確認する。"""

    def _interfaces_http_routers_dir(self) -> Path:
        import bakufu.interfaces.http.routers.agents as _mod

        return Path(_mod.__file__).parent  # type: ignore[arg-type]

    def _interfaces_http_schemas_dir(self) -> Path:
        import bakufu.interfaces.http.schemas.agent as _mod

        return Path(_mod.__file__).parent  # type: ignore[arg-type]

    def _collect_all_imports(self, py_file: Path) -> list[tuple[str, int]]:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        results: list[tuple[str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                results.append((node.module or "", node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((alias.name, node.lineno))
        return results

    def test_no_bakufu_domain_import_in_routers(self) -> None:
        routers_dir = self._interfaces_http_routers_dir()
        violations: list[str] = []
        for py_file in sorted(routers_dir.rglob("*.py")):
            for module_name, lineno in self._collect_all_imports(py_file):
                if module_name.startswith("bakufu.domain"):
                    violations.append(f"{py_file.name}:{lineno}: import of {module_name}")
        assert violations == [], "Direct bakufu.domain imports detected in routers/:\n" + "\n".join(
            violations
        )

    def test_no_bakufu_infrastructure_import_in_routers(self) -> None:
        routers_dir = self._interfaces_http_routers_dir()
        violations: list[str] = []
        for py_file in sorted(routers_dir.rglob("*.py")):
            for module_name, lineno in self._collect_all_imports(py_file):
                if module_name.startswith("bakufu.infrastructure"):
                    violations.append(f"{py_file.name}:{lineno}: import of {module_name}")
        assert violations == [], (
            "Direct bakufu.infrastructure imports detected in routers/:\n" + "\n".join(violations)
        )

    def test_no_bakufu_domain_import_in_schemas(self) -> None:
        schemas_dir = self._interfaces_http_schemas_dir()
        violations: list[str] = []
        for py_file in sorted(schemas_dir.rglob("*.py")):
            for module_name, lineno in self._collect_all_imports(py_file):
                if module_name.startswith("bakufu.domain"):
                    violations.append(f"{py_file.name}:{lineno}: import of {module_name}")
        assert violations == [], "Direct bakufu.domain imports detected in schemas/:\n" + "\n".join(
            violations
        )

    def test_no_bakufu_infrastructure_import_in_schemas(self) -> None:
        schemas_dir = self._interfaces_http_schemas_dir()
        violations: list[str] = []
        for py_file in sorted(schemas_dir.rglob("*.py")):
            for module_name, lineno in self._collect_all_imports(py_file):
                if module_name.startswith("bakufu.infrastructure"):
                    violations.append(f"{py_file.name}:{lineno}: import of {module_name}")
        assert violations == [], (
            "Direct bakufu.infrastructure imports detected in schemas/:\n" + "\n".join(violations)
        )
