"""ExternalReviewGate HTTP boundary static tests."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _top_level_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def test_http_app_and_di_do_not_expose_top_level_functions() -> None:
    """TC-STATIC-ERG-HTTP-003: HTTP app / DI の入口は classmethod に閉じる。"""
    files = [
        BACKEND_ROOT / "src/bakufu/interfaces/http/app.py",
        BACKEND_ROOT / "src/bakufu/interfaces/http/dependencies.py",
    ]

    violations = {
        str(path): _top_level_functions(path) for path in files if _top_level_functions(path)
    }

    assert violations == {}
