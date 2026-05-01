"""DeliverableTemplateService ユニットテスト (TC-UT-DTS-001〜009).

Covers:
  TC-UT-DTS-001  find_by_id → repo が None → DeliverableTemplateNotFoundError
  TC-UT-DTS-002  _check_dag 自己参照 → 検出前に domain invariant が発火（integration で検証）
  TC-UT-DTS-003  _check_dag 推移的循環 → CompositionCycleError / transitive_cycle
  TC-UT-DTS-004  _check_dag 深度上限 10 超 → CompositionCycleError / depth_limit (§確定D)
  TC-UT-DTS-005  _check_dag ノード上限 100 超 → CompositionCycleError / node_limit (§確定D)
  TC-UT-DTS-006  update version 降格 → DeliverableTemplateVersionDowngradeError (§確定B)
  TC-UT-DTS-007  update version 同一 → 正常系 (§確定B)
  TC-UT-DTS-008  update version 昇格 → 正常系 (§確定B)
  TC-UT-DTS-009  delete 不在 → DeliverableTemplateNotFoundError (§確定E)

Issue: #122
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _make_mock_session() -> MagicMock:
    """async with session.begin(): をサポートするモック session を生成する。

    ``AsyncMock()`` のまま使うと ``begin()`` が coroutine を返してしまい
    ``async with`` のコンテキストマネージャとして機能しない。
    ``MagicMock().begin.return_value`` に ``__aenter__`` / ``__aexit__`` を設定して
    非同期コンテキストマネージャとして動作させる。
    """
    mock_session = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _make_service(mock_repo: AsyncMock) -> object:
    """DeliverableTemplateService を AsyncMock repo + モック session で構築する。"""
    from bakufu.application.services.deliverable_template_service import (
        DeliverableTemplateService,
    )

    return DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())


# ---------------------------------------------------------------------------
# TC-UT-DTS-001: find_by_id → None → DeliverableTemplateNotFoundError
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-UT-DTS-001: repo が None を返す場合 → DeliverableTemplateNotFoundError。"""

    async def test_find_by_id_raises_when_not_found(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            DeliverableTemplateNotFoundError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        with pytest.raises(DeliverableTemplateNotFoundError) as exc_info:
            await service.find_by_id(uuid4())
        assert exc_info.value.kind == "primary"

    async def test_find_by_id_returns_template_when_found(self) -> None:
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )

        from tests.factories.deliverable_template import make_deliverable_template

        template = make_deliverable_template()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=template)
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        result = await service.find_by_id(template.id)
        assert result is template


# ---------------------------------------------------------------------------
# TC-UT-DTS-003: _check_dag 推移的循環 → CompositionCycleError / transitive_cycle
# ---------------------------------------------------------------------------
class TestCheckDagTransitiveCycle:
    """TC-UT-DTS-003: BFS で推移的循環を検出 → CompositionCycleError (§確定D)。"""

    async def test_check_dag_raises_on_transitive_cycle(self) -> None:
        """A→B→A: B を root_id として BFS すると A が visited に入り循環検出。

        セットアップ:
          - root_id = A (作成中のテンプレート)
          - refs = [ref_to_B]
          - B.composition = [ref_to_A] → visited に A が含まれるため循環
        """
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            CompositionCycleError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        from tests.factories.deliverable_template import make_deliverable_template

        id_a = uuid4()
        id_b = uuid4()
        semver = SemVer(major=1, minor=0, patch=0)

        # B が A を参照（A→B→A 循環の B 側）
        ref_to_a = DeliverableTemplateRef(template_id=id_a, minimum_version=semver)
        template_b = make_deliverable_template(template_id=id_b)

        mock_repo = AsyncMock()

        async def _find_by_id(tid: object) -> object:
            if tid == id_b:
                # B の composition に A への参照を持たせる
                from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef

                b_with_ref = make_deliverable_template(
                    template_id=id_b,
                    composition=(DeliverableTemplateRef(template_id=id_a, minimum_version=semver),),
                )
                return b_with_ref
            return None

        mock_repo.find_by_id = _find_by_id

        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())
        ref_to_b = DeliverableTemplateRef(template_id=id_b, minimum_version=semver)

        with pytest.raises(CompositionCycleError) as exc_info:
            await service._check_dag(refs=(ref_to_b,), root_id=id_a)
        assert exc_info.value.reason == "transitive_cycle"

    async def test_transitive_cycle_path_is_non_empty(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            CompositionCycleError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        from tests.factories.deliverable_template import make_deliverable_template

        id_a = uuid4()
        id_b = uuid4()
        semver = SemVer(major=1, minor=0, patch=0)

        async def _find_by_id(tid: object) -> object:
            if tid == id_b:
                return make_deliverable_template(
                    template_id=id_b,
                    composition=(DeliverableTemplateRef(template_id=id_a, minimum_version=semver),),
                )
            return None

        mock_repo = AsyncMock()
        mock_repo.find_by_id = _find_by_id

        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())
        ref_to_b = DeliverableTemplateRef(template_id=id_b, minimum_version=semver)

        with pytest.raises(CompositionCycleError) as exc_info:
            await service._check_dag(refs=(ref_to_b,), root_id=id_a)
        assert len(exc_info.value.cycle_path) > 0


# ---------------------------------------------------------------------------
# TC-UT-DTS-004: _check_dag 深度上限 10 超 → CompositionCycleError / depth_limit (§確定D)
# ---------------------------------------------------------------------------
class TestCheckDagDepthLimit:
    """TC-UT-DTS-004: depth 11 で depth_limit (§確定D)。"""

    async def test_check_dag_raises_on_depth_limit(self) -> None:
        """11 段のチェーン: root→T1→T2→...→T11 で depth=11>10 → depth_limit。"""
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            CompositionCycleError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        from tests.factories.deliverable_template import make_deliverable_template

        semver = SemVer(major=1, minor=0, patch=0)
        # 11 段のリニアチェーン: ids[0] は root の直接子、ids[10] は末端
        ids = [uuid4() for _ in range(11)]

        def _make_chain_template(idx: int) -> object:
            """ids[idx] が ids[idx+1] を参照するテンプレートを返す。末端は refs なし。"""
            if idx + 1 < len(ids):
                child_ref = DeliverableTemplateRef(template_id=ids[idx + 1], minimum_version=semver)
                return make_deliverable_template(template_id=ids[idx], composition=(child_ref,))
            return make_deliverable_template(template_id=ids[idx])

        async def _find_by_id(tid: object) -> object:
            for i, eid in enumerate(ids):
                if tid == eid:
                    return _make_chain_template(i)
            return None

        mock_repo = AsyncMock()
        mock_repo.find_by_id = _find_by_id

        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())
        root_ref = DeliverableTemplateRef(template_id=ids[0], minimum_version=semver)

        with pytest.raises(CompositionCycleError) as exc_info:
            await service._check_dag(refs=(root_ref,), root_id=uuid4())
        assert exc_info.value.reason == "depth_limit"

    async def test_depth_limit_cycle_path_is_empty(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            CompositionCycleError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        from tests.factories.deliverable_template import make_deliverable_template

        semver = SemVer(major=1, minor=0, patch=0)
        ids = [uuid4() for _ in range(11)]

        def _make_chain_template(idx: int) -> object:
            if idx + 1 < len(ids):
                child_ref = DeliverableTemplateRef(template_id=ids[idx + 1], minimum_version=semver)
                return make_deliverable_template(template_id=ids[idx], composition=(child_ref,))
            return make_deliverable_template(template_id=ids[idx])

        async def _find_by_id(tid: object) -> object:
            for i, eid in enumerate(ids):
                if tid == eid:
                    return _make_chain_template(i)
            return None

        mock_repo = AsyncMock()
        mock_repo.find_by_id = _find_by_id
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())
        root_ref = DeliverableTemplateRef(template_id=ids[0], minimum_version=semver)

        with pytest.raises(CompositionCycleError) as exc_info:
            await service._check_dag(refs=(root_ref,), root_id=uuid4())
        assert exc_info.value.cycle_path == []


# ---------------------------------------------------------------------------
# TC-UT-DTS-005: _check_dag ノード上限 100 超 → CompositionCycleError / node_limit (§確定D)
# ---------------------------------------------------------------------------
class TestCheckDagNodeLimit:
    """TC-UT-DTS-005: 101 ノード（root + 100 子）で node_limit (§確定D)。

    visited = {root_id} + 100 子 = 101 > 100 → node_limit
    """

    async def test_check_dag_raises_on_node_limit(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            CompositionCycleError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        from tests.factories.deliverable_template import make_deliverable_template

        semver = SemVer(major=1, minor=0, patch=0)
        # 100 子ノードを生成（各々 leaf テンプレート）
        child_ids = [uuid4() for _ in range(100)]

        async def _find_by_id(tid: object) -> object:
            # 子ノードは全て leaf（composition なし）
            if tid in child_ids:
                return make_deliverable_template(template_id=tid)  # type: ignore[arg-type]
            return None

        mock_repo = AsyncMock()
        mock_repo.find_by_id = _find_by_id

        # 100 refs を root の直接子として渡す
        refs = tuple(
            DeliverableTemplateRef(template_id=cid, minimum_version=semver)
            for cid in child_ids
        )
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        with pytest.raises(CompositionCycleError) as exc_info:
            await service._check_dag(refs=refs, root_id=uuid4())
        assert exc_info.value.reason == "node_limit"

    async def test_node_limit_cycle_path_is_empty(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            CompositionCycleError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        from tests.factories.deliverable_template import make_deliverable_template

        semver = SemVer(major=1, minor=0, patch=0)
        child_ids = [uuid4() for _ in range(100)]

        async def _find_by_id(tid: object) -> object:
            if tid in child_ids:
                return make_deliverable_template(template_id=tid)  # type: ignore[arg-type]
            return None

        mock_repo = AsyncMock()
        mock_repo.find_by_id = _find_by_id

        refs = tuple(
            DeliverableTemplateRef(template_id=cid, minimum_version=semver)
            for cid in child_ids
        )
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        with pytest.raises(CompositionCycleError) as exc_info:
            await service._check_dag(refs=refs, root_id=uuid4())
        assert exc_info.value.cycle_path == []


# ---------------------------------------------------------------------------
# TC-UT-DTS-006: update — version 降格 → DeliverableTemplateVersionDowngradeError (§確定B)
# ---------------------------------------------------------------------------
class TestUpdateVersionDowngrade:
    """TC-UT-DTS-006: version 降格 → DeliverableTemplateVersionDowngradeError (§確定B)。"""

    async def test_update_raises_on_version_downgrade(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            DeliverableTemplateVersionDowngradeError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )

        from tests.factories.deliverable_template import make_deliverable_template, make_semver

        # version 2.0.0 のテンプレートをモック
        existing = make_deliverable_template(version=make_semver(major=2, minor=0, patch=0))
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=existing)
        mock_repo.find_all = AsyncMock(return_value=[])
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        with pytest.raises(DeliverableTemplateVersionDowngradeError) as exc_info:
            await service.update(
                template_id=existing.id,
                name="updated",
                description="",
                type_="MARKDOWN",
                schema="## guide",
                acceptance_criteria=[],
                version={"major": 1, "minor": 0, "patch": 0},
                composition=[],
            )
        assert exc_info.value.current_version == "2.0.0"
        assert exc_info.value.provided_version == "1.0.0"


# ---------------------------------------------------------------------------
# TC-UT-DTS-007: update — version 同一 → 正常系（create_new_version 呼ばれない）(§確定B)
# ---------------------------------------------------------------------------
class TestUpdateSameVersion:
    """TC-UT-DTS-007: version 同一 → 例外なし (§確定B)。"""

    async def test_update_same_version_does_not_raise(self) -> None:
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )

        from tests.factories.deliverable_template import make_deliverable_template, make_semver

        existing = make_deliverable_template(version=make_semver(major=1, minor=0, patch=0))
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=existing)
        mock_repo.save = AsyncMock()
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        # 例外なく完了することを確認
        result = await service.update(
            template_id=existing.id,
            name="updated",
            description="",
            type_="MARKDOWN",
            schema="## guide",
            acceptance_criteria=[],
            version={"major": 1, "minor": 0, "patch": 0},
            composition=[],
        )
        assert result is not None
        assert result.version.major == 1
        assert result.version.minor == 0
        assert result.version.patch == 0


# ---------------------------------------------------------------------------
# TC-UT-DTS-008: update — version 昇格 → 正常系 (§確定B)
# ---------------------------------------------------------------------------
class TestUpdateHigherVersion:
    """TC-UT-DTS-008: version 昇格 → 例外なし・新 version が返る (§確定B)。"""

    async def test_update_higher_version_does_not_raise(self) -> None:
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )

        from tests.factories.deliverable_template import make_deliverable_template, make_semver

        existing = make_deliverable_template(version=make_semver(major=1, minor=0, patch=0))
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=existing)
        mock_repo.save = AsyncMock()
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        result = await service.update(
            template_id=existing.id,
            name="updated",
            description="",
            type_="MARKDOWN",
            schema="## guide",
            acceptance_criteria=[],
            version={"major": 2, "minor": 0, "patch": 0},
            composition=[],
        )
        assert result.version.major == 2


# ---------------------------------------------------------------------------
# TC-UT-DTS-009: delete — 不在 → DeliverableTemplateNotFoundError (§確定E)
# ---------------------------------------------------------------------------
class TestDelete:
    """TC-UT-DTS-009: repo が None → DeliverableTemplateNotFoundError (§確定E)。"""

    async def test_delete_raises_when_not_found(self) -> None:
        from bakufu.application.exceptions.deliverable_template_exceptions import (
            DeliverableTemplateNotFoundError,
        )
        from bakufu.application.services.deliverable_template_service import (
            DeliverableTemplateService,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)
        service = DeliverableTemplateService(dt_repo=mock_repo, session=_make_mock_session())

        with pytest.raises(DeliverableTemplateNotFoundError):
            await service.delete(uuid4())
