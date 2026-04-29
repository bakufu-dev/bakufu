"""room / http-api ユニットテスト — 依存方向静的解析 (TC-UT-RM-HTTP-010).

Covers:
  TC-UT-RM-HTTP-010  interfaces/http/ 依存方向静的解析 — ast.walk() 全ノード走査 (Q-3)

Issue: #57
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestStaticDependencyAnalysisRoom:
    """TC-UT-RM-HTTP-010: routers/ と schemas/ の依存方向を ast.walk() で全検査.

    TC-UT-EM-HTTP-010 (empire) の同一パターン。
    旧実装 (tree.body のみ走査) は関数内遅延 import を見逃す盲点があった。
    ``ast.walk(ast.parse(src))`` で全 AST ノード (関数内・クラス内・ネスト含む) を
    走査し、``bakufu.domain`` / ``bakufu.infrastructure`` への import が
    存在しないことを確認する。

    スコープ: interfaces/http/routers/ + interfaces/http/schemas/
    除外: app.py / dependencies.py / error_handlers.py (設計上 domain import が正当)
    """

    def _interfaces_http_dir(self) -> Path:
        import bakufu.interfaces.http.app as _app_mod

        return Path(_app_mod.__file__).parent  # type: ignore[arg-type]

    def _collect_all_imports(self, py_file: Path) -> list[tuple[str, int]]:
        """ast.walk() でファイル内の全 import 文 (関数内遅延 import 含む) を収集する.

        旧 ``_collect_toplevel_imports`` は ``tree.body`` のみを走査していたが、
        本メソッドは ``ast.walk(tree)`` で AST 全ノードを走査するため、
        関数本体・クラス本体・ネストされたスコープ内の import も捕捉できる。
        """
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        results: list[tuple[str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                results.append((module, node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((alias.name, node.lineno))
        return results

    def test_room_router_has_no_domain_import(self) -> None:
        """routers/ と schemas/ は bakufu.domain を一切 import してはならない (遅延含む).

        ast.walk() で関数内遅延 import も検出する。
        """
        interfaces_dir = self._interfaces_http_dir()
        violations: list[str] = []
        scan_dirs = [interfaces_dir / "routers", interfaces_dir / "schemas"]
        for scan_dir in scan_dirs:
            for py_file in sorted(scan_dir.rglob("*.py")):
                for module_name, lineno in self._collect_all_imports(py_file):
                    if module_name.startswith("bakufu.domain"):
                        violations.append(f"{py_file.name}:{lineno}: import of {module_name}")
        assert violations == [], (
            "bakufu.domain imports detected in routers/ or schemas/ (including deferred):\n"
            + "\n".join(violations)
        )

    def test_room_router_has_no_infrastructure_import(self) -> None:
        """routers/ と schemas/ は bakufu.infrastructure を一切 import してはならない (遅延含む).

        ast.walk() で関数内遅延 import も検出する。
        """
        interfaces_dir = self._interfaces_http_dir()
        violations: list[str] = []
        scan_dirs = [interfaces_dir / "routers", interfaces_dir / "schemas"]
        for scan_dir in scan_dirs:
            for py_file in sorted(scan_dir.rglob("*.py")):
                for module_name, lineno in self._collect_all_imports(py_file):
                    if module_name.startswith("bakufu.infrastructure"):
                        violations.append(f"{py_file.name}:{lineno}: import of {module_name}")
        assert violations == [], (
            "bakufu.infrastructure imports detected in routers/ or schemas/ (including deferred):\n"
            + "\n".join(violations)
        )
