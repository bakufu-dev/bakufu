"""empire / http-api ユニットテスト (TC-UT-EM-HTTP-001〜005, 010).

Per ``docs/features/empire/http-api/test-design.md`` §ユニットテストケース.

Covers:
  TC-UT-EM-HTTP-001  EmpireCreate スキーマ検証 (Q-3)
  TC-UT-EM-HTTP-002  EmpireUpdate スキーマ検証 (Q-3)
  TC-UT-EM-HTTP-003  EmpireResponse シリアライズ (Q-3)
  TC-UT-EM-HTTP-004  empire_invariant_violation_handler [FAIL]/Next: 除去 (MSG-EM-HTTP-004, Q-3)
  TC-UT-EM-HTTP-005  EmpireService.create mock repo 正常系 (Q-3)
  TC-UT-EM-HTTP-010  interfaces/http/ 依存方向静的解析 — ast モジュール (Q-3)

Issue: #56
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# TC-UT-EM-HTTP-001: EmpireCreate スキーマ検証
# ---------------------------------------------------------------------------
class TestEmpireCreateSchema:
    """TC-UT-EM-HTTP-001: EmpireCreate validates name 1〜80 chars and forbids extras."""

    def test_valid_name_passes(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireCreate

        schema = EmpireCreate(name="山田の幕府")
        assert schema.name == "山田の幕府"

    def test_empty_name_raises(self) -> None:
        """min_length=1 違反 → ValidationError."""
        from bakufu.interfaces.http.schemas.empire import EmpireCreate

        with pytest.raises(ValidationError):
            EmpireCreate(name="")

    def test_name_too_long_raises(self) -> None:
        """max_length=80 違反 (81 文字) → ValidationError."""
        from bakufu.interfaces.http.schemas.empire import EmpireCreate

        with pytest.raises(ValidationError):
            EmpireCreate(name="x" * 81)

    def test_exactly_80_chars_passes(self) -> None:
        """Boundary: 80 文字は上限に等しく通過すべき."""
        from bakufu.interfaces.http.schemas.empire import EmpireCreate

        schema = EmpireCreate(name="a" * 80)
        assert len(schema.name) == 80

    def test_extra_field_raises(self) -> None:
        """extra='forbid': 未知フィールドを含む入力は ValidationError."""
        from bakufu.interfaces.http.schemas.empire import EmpireCreate

        with pytest.raises(ValidationError):
            EmpireCreate.model_validate({"name": "test", "extra_field": "z"})


# ---------------------------------------------------------------------------
# TC-UT-EM-HTTP-002: EmpireUpdate スキーマ検証
# ---------------------------------------------------------------------------
class TestEmpireUpdateSchema:
    """TC-UT-EM-HTTP-002: EmpireUpdate — partial update with optional name."""

    def test_valid_name_passes(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireUpdate

        schema = EmpireUpdate(name="新名前")
        assert schema.name == "新名前"

    def test_name_none_passes(self) -> None:
        """name=None は部分更新(変更なし)として有効."""
        from bakufu.interfaces.http.schemas.empire import EmpireUpdate

        schema = EmpireUpdate(name=None)
        assert schema.name is None

    def test_default_name_is_none(self) -> None:
        """name を省略した場合のデフォルトは None."""
        from bakufu.interfaces.http.schemas.empire import EmpireUpdate

        schema = EmpireUpdate()
        assert schema.name is None

    def test_empty_name_raises(self) -> None:
        """None でなく空文字は min_length=1 違反."""
        from bakufu.interfaces.http.schemas.empire import EmpireUpdate

        with pytest.raises(ValidationError):
            EmpireUpdate(name="")

    def test_extra_field_raises(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireUpdate

        with pytest.raises(ValidationError):
            EmpireUpdate.model_validate({"name": "test", "extra_field": "z"})


# ---------------------------------------------------------------------------
# TC-UT-EM-HTTP-003: EmpireResponse シリアライズ
# ---------------------------------------------------------------------------
class TestEmpireResponseSchema:
    """TC-UT-EM-HTTP-003: EmpireResponse serializes id/name/archived/rooms/agents."""

    def test_id_is_str(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireResponse

        resp = EmpireResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="テスト幕府",
            archived=False,
            rooms=[],
            agents=[],
        )
        assert isinstance(resp.id, str)

    def test_archived_is_bool(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireResponse

        resp = EmpireResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="テスト幕府",
            archived=True,
            rooms=[],
            agents=[],
        )
        assert isinstance(resp.archived, bool)
        assert resp.archived is True

    def test_rooms_is_list(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireResponse

        resp = EmpireResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="テスト幕府",
            archived=False,
            rooms=[],
            agents=[],
        )
        assert isinstance(resp.rooms, list)

    def test_agents_is_list(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireResponse

        resp = EmpireResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="テスト幕府",
            archived=False,
            rooms=[],
            agents=[],
        )
        assert isinstance(resp.agents, list)

    def test_model_dump_structure(self) -> None:
        """model_dump() が id/name/archived/rooms/agents キーを持つ dict を返す."""
        from bakufu.interfaces.http.schemas.empire import EmpireResponse

        resp = EmpireResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="テスト幕府",
            archived=False,
            rooms=[],
            agents=[],
        )
        dumped = resp.model_dump()
        assert set(dumped.keys()) == {"id", "name", "archived", "rooms", "agents"}

    def test_extra_field_raises(self) -> None:
        from bakufu.interfaces.http.schemas.empire import EmpireResponse

        with pytest.raises(ValidationError):
            EmpireResponse.model_validate(
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "test",
                    "archived": False,
                    "rooms": [],
                    "agents": [],
                    "extra": "z",
                }
            )


# ---------------------------------------------------------------------------
# TC-UT-EM-HTTP-004: empire_invariant_violation_handler [FAIL]/Next: 除去
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestEmpireInvariantViolationHandler:
    """TC-UT-EM-HTTP-004: empire_invariant_violation_handler 前処理ルール検証 (確定C).

    入力: EmpireInvariantViolation with "[FAIL]...\\nNext:..." フォーマット
    期待: HTTP 422, message から [FAIL] プレフィックスと \\nNext:.* が除去される
    """

    def _make_request(self) -> object:
        from unittest.mock import MagicMock

        return MagicMock()

    async def test_handler_returns_422(self) -> None:
        from bakufu.domain.exceptions import EmpireInvariantViolation
        from bakufu.interfaces.http.error_handlers import empire_invariant_violation_handler

        exc = EmpireInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Empire name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await empire_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        assert resp.status_code == 422  # type: ignore[union-attr]

    async def test_handler_error_code_is_validation_error(self) -> None:
        import json

        from bakufu.domain.exceptions import EmpireInvariantViolation
        from bakufu.interfaces.http.error_handlers import empire_invariant_violation_handler

        exc = EmpireInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Empire name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await empire_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["code"] == "validation_error"

    async def test_handler_removes_fail_prefix(self) -> None:
        """[FAIL] プレフィックスが除去され HTTP message に含まれないこと (確定C)."""
        import json

        from bakufu.domain.exceptions import EmpireInvariantViolation
        from bakufu.interfaces.http.error_handlers import empire_invariant_violation_handler

        exc = EmpireInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Empire name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await empire_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "[FAIL]" not in body["error"]["message"]

    async def test_handler_removes_next_suffix(self) -> None:
        """\\nNext:.* サフィックスが除去され HTTP message に含まれないこと (確定C)."""
        import json

        from bakufu.domain.exceptions import EmpireInvariantViolation
        from bakufu.interfaces.http.error_handlers import empire_invariant_violation_handler

        exc = EmpireInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Empire name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await empire_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert "Next:" not in body["error"]["message"]

    async def test_handler_message_is_clean_business_text(self) -> None:
        """期待 message: "Empire name は 1〜80 文字でなければなりません。" (前処理後の本文のみ)."""
        import json

        from bakufu.domain.exceptions import EmpireInvariantViolation
        from bakufu.interfaces.http.error_handlers import empire_invariant_violation_handler

        exc = EmpireInvariantViolation(
            kind="name_range",
            message=(
                "[FAIL] Empire name は 1〜80 文字でなければなりません。"
                "\nNext: 1〜80 文字の名前を指定してください。"
            ),
        )
        resp = await empire_invariant_violation_handler(self._make_request(), exc)  # type: ignore[arg-type]
        body = json.loads(resp.body)  # type: ignore[union-attr]
        assert body["error"]["message"] == "Empire name は 1〜80 文字でなければなりません。"

    async def test_handler_wrong_type_raises_type_error(self) -> None:
        """非 EmpireInvariantViolation → TypeError (Fail Fast 確認)."""
        from bakufu.interfaces.http.error_handlers import empire_invariant_violation_handler

        with pytest.raises(TypeError, match="Expected EmpireInvariantViolation"):
            await empire_invariant_violation_handler(self._make_request(), ValueError("oops"))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TC-UT-EM-HTTP-005: EmpireService.create — mock repo 正常系
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestEmpireServiceCreate:
    """TC-UT-EM-HTTP-005: EmpireService.create with mock repo.

    Verifies that:
    - EmpireService(repo=mock, session=mock) constructs successfully
    - create("山田の幕府") returns an Empire without raising
    - _repo.save() is called exactly once
    """

    def _make_mock_session(self) -> object:
        """Return a MagicMock session with async context-manager begin()."""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=None)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.begin = MagicMock(return_value=mock_cm)
        return mock_session

    async def test_service_constructs_successfully(self) -> None:
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        mock_session = self._make_mock_session()
        service = EmpireService(repo=mock_repo, session=mock_session)  # type: ignore[arg-type]
        assert service is not None

    async def test_service_stores_repo(self) -> None:
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        mock_session = self._make_mock_session()
        service = EmpireService(repo=mock_repo, session=mock_session)  # type: ignore[arg-type]
        assert service._repo is mock_repo  # pyright: ignore[reportPrivateUsage]

    async def test_create_returns_empire(self) -> None:
        from bakufu.application.services.empire_service import EmpireService
        from bakufu.domain.empire import Empire

        mock_repo = MagicMock()
        mock_repo.count = AsyncMock(return_value=0)
        mock_repo.save = AsyncMock(return_value=None)
        mock_session = self._make_mock_session()

        service = EmpireService(repo=mock_repo, session=mock_session)  # type: ignore[arg-type]
        result = await service.create("山田の幕府")
        assert isinstance(result, Empire)

    async def test_create_empire_name_matches(self) -> None:
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        mock_repo.count = AsyncMock(return_value=0)
        mock_repo.save = AsyncMock(return_value=None)
        mock_session = self._make_mock_session()

        service = EmpireService(repo=mock_repo, session=mock_session)  # type: ignore[arg-type]
        result = await service.create("山田の幕府")
        assert result.name == "山田の幕府"

    async def test_create_calls_repo_save_once(self) -> None:
        """_repo.save() は 1 回だけ呼ばれる."""
        from bakufu.application.services.empire_service import EmpireService

        mock_repo = MagicMock()
        mock_repo.count = AsyncMock(return_value=0)
        mock_repo.save = AsyncMock(return_value=None)
        mock_session = self._make_mock_session()

        service = EmpireService(repo=mock_repo, session=mock_session)  # type: ignore[arg-type]
        await service.create("山田の幕府")
        mock_repo.save.assert_called_once()


# ---------------------------------------------------------------------------
# TC-UT-EM-HTTP-010: interfaces/http/routers/ + schemas/ 依存方向静的解析
# ---------------------------------------------------------------------------
class TestStaticDependencyAnalysisEmpire:
    """TC-UT-EM-HTTP-010: routers/ と schemas/ の依存方向を ast.walk() で全検査.

    旧実装 (_collect_toplevel_imports) は tree.body のみ走査していたため、
    関数内遅延 import(例: ``_to_empire_response`` 内の
    ``from bakufu.domain.empire import Empire``)を見逃す盲点があった。
    ヘルスバーグ指摘 (PR #95 却下理由) を受け ast.walk() へ拡張し、
    トップレベル・関数内・クラス内を含む全 import 文を検査する。

    スコープを ``routers/`` と ``schemas/`` に絞る理由:
    * ``app.py``        : lifespan・handler 登録のため infra/domain deferred import が設計上正当
    * ``dependencies.py``: DI Factory が infra を deferred import する設計(コメントで明示)
    * ``error_handlers.py``: domain 例外を isinstance チェックするため domain deferred import が正当
    上記ファイルは「例外許可ファイル」であり、routers / schemas は例外なく
    bakufu.domain / bakufu.infrastructure への import が禁止される。
    """

    def _interfaces_http_dir(self) -> Path:
        import bakufu.interfaces.http.app as _app_mod

        return Path(_app_mod.__file__).parent  # type: ignore[arg-type]

    def _collect_all_imports(self, py_file: Path) -> list[tuple[str, int]]:
        """ast.walk() でファイル内の全 import 文(関数内遅延 import 含む)を収集する。

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

    def test_empire_router_has_no_domain_import(self) -> None:
        """routers/ と schemas/ は bakufu.domain を一切 import してはならない(遅延含む).

        ast.walk() で関数内遅延 import も検出する。旧 BUG-EM-002 相当の違反
        (例: router 関数内 ``from bakufu.domain.empire import Empire``)が
        再混入した場合にこのテストが失敗する。
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

    def test_empire_router_has_no_infrastructure_import(self) -> None:
        """routers/ と schemas/ は bakufu.infrastructure を一切 import してはならない(遅延含む).

        ast.walk() で関数内遅延 import も検出する。
        ``dependencies.py`` は DI Factory として infra deferred import が設計上正当なため
        スコープ対象外 (routers/ と schemas/ のみ検査)。
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
