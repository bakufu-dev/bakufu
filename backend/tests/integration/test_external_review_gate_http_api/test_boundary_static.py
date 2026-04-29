"""ExternalReviewGate HTTP boundary static tests."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _public_top_level_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    ]


def _public_callable_aliases(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Attribute):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                aliases.append(target.id)
    return aliases


def test_http_boundary_does_not_expose_public_top_level_functions() -> None:
    """TC-STATIC-ERG-HTTP-003: HTTP 境界の公開入口は class/classmethod に閉じる。"""
    files = [
        BACKEND_ROOT / "src/bakufu/interfaces/http/app.py",
        BACKEND_ROOT / "src/bakufu/interfaces/http/dependencies.py",
        BACKEND_ROOT / "src/bakufu/interfaces/http/error_handlers.py",
    ]
    files.extend(sorted((BACKEND_ROOT / "src/bakufu/interfaces/http/routers").glob("*.py")))

    violations = {
        str(path): _public_top_level_functions(path)
        for path in files
        if _public_top_level_functions(path)
    }

    assert violations == {}


def test_security_masking_does_not_expose_public_top_level_functions() -> None:
    """TC-STATIC-ERG-HTTP-004: masking ゲートウェイも class/classmethod に閉じる。"""
    paths = [
        BACKEND_ROOT / "src/bakufu/infrastructure/security/masking.py",
        BACKEND_ROOT / "src/bakufu/application/security/masking.py",
    ]
    violations = {
        str(path): _public_top_level_functions(path)
        for path in paths
        if _public_top_level_functions(path)
    }
    assert violations == {}


def test_security_masking_does_not_expose_public_callable_aliases() -> None:
    """TC-STATIC-ERG-HTTP-005: MaskingGateway の公開 alias 再輸出を禁止する。"""
    paths = [
        BACKEND_ROOT / "src/bakufu/infrastructure/security/masking.py",
        BACKEND_ROOT / "src/bakufu/application/security/masking.py",
    ]
    violations = {
        str(path): _public_callable_aliases(path)
        for path in paths
        if _public_callable_aliases(path)
    }
    assert violations == {}
