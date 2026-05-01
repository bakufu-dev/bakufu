"""DeliverableTemplateService — DeliverableTemplate Aggregate 操作の application 層サービス。

``docs/features/deliverable-template/http-api/detailed-design.md`` に従って実装する。

設計メモ:

* **UoW 境界**: write 操作（``create`` / ``update`` / ``delete``）は
  単一の ``async with self._session.begin():`` ブロック内で完結させる。
* ``find_all`` / ``find_by_id`` は read-only。明示的な ``begin()`` は不要。
* **DAG 走査**: ``_check_dag`` は BFS で composition refs を走査し、
  循環参照・深度上限（10）・ノード数上限（100）を検出する（§確定 D）。
* **version チェック**: PUT で提供 version < 現 version なら
  ``DeliverableTemplateVersionDowngradeError`` を raise（§確定 B）。
* **interfaces 層との境界**: router が domain 型を import しないよう、
  ``create`` / ``update`` はシリアライズ可能な dict 形式（``SemVerDict``,
  ``AcceptanceCriterionDict``, ``DeliverableTemplateRefDict``）で受け取り、
  service 内部で domain VO へ変換する。
"""

from __future__ import annotations

from collections import deque
from typing import TypedDict
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.deliverable_template_exceptions import (
    CompositionCycleError,
    DeliverableTemplateNotFoundError,
    DeliverableTemplateVersionDowngradeError,
)
from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.domain.deliverable_template import DeliverableTemplate
from bakufu.domain.value_objects import DeliverableTemplateId
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)

# DAG 走査上限（§確定 D）
_DAG_MAX_DEPTH: int = 10
_DAG_MAX_NODES: int = 100


class SemVerDict(TypedDict):
    """SemVer を dict 形式で表現する。router から service への受け渡しに使用する。"""

    major: int
    minor: int
    patch: int


class AcceptanceCriterionDict(TypedDict):
    """AcceptanceCriterion を dict 形式で表現する。"""

    id: UUID
    description: str
    required: bool


class DeliverableTemplateRefDict(TypedDict):
    """DeliverableTemplateRef を dict 形式で表現する。"""

    template_id: UUID
    minimum_version: SemVerDict


def _build_semver(d: SemVerDict) -> SemVer:
    return SemVer(major=d["major"], minor=d["minor"], patch=d["patch"])


def _build_acceptance_criterion(d: AcceptanceCriterionDict) -> AcceptanceCriterion:
    return AcceptanceCriterion.model_validate(
        {"id": d["id"], "description": d["description"], "required": d["required"]}
    )


def _build_ref(d: DeliverableTemplateRefDict) -> DeliverableTemplateRef:
    mv = d["minimum_version"]
    return DeliverableTemplateRef.model_validate(
        {
            "template_id": d["template_id"],
            "minimum_version": {
                "major": mv["major"],
                "minor": mv["minor"],
                "patch": mv["patch"],
            },
        }
    )


class DeliverableTemplateService:
    """DeliverableTemplate Aggregate 操作の thin CRUD サービス。

    session は repository とともに注入され、サービスが write 操作向けに自前の
    Unit-of-Work トランザクションを開いて commit できるようにする。read-only 操作
    （``find_all`` / ``find_by_id``）は明示的な ``begin()`` なしで session 上で
    直接実行する。
    """

    def __init__(
        self,
        dt_repo: DeliverableTemplateRepository,
        session: AsyncSession,
    ) -> None:
        self._dt_repo = dt_repo
        self._session = session

    async def create(
        self,
        name: str,
        description: str,
        type_: str,
        schema: dict[str, object] | str,
        acceptance_criteria: list[AcceptanceCriterionDict],
        version: SemVerDict,
        composition: list[DeliverableTemplateRefDict],
    ) -> DeliverableTemplate:
        """新しい DeliverableTemplate を構築して永続化する（REQ-DT-HTTP-001）。

        Args:
            name: テンプレート名（1〜80 文字）。
            description: テンプレート説明（0〜500 文字）。
            type_: テンプレート種別文字列（``TemplateType`` 値）。
            schema: JSON Schema または自然言語ガイドライン。
            acceptance_criteria: 受入基準のリスト（dict 形式）。
            version: SemVer（dict 形式）。
            composition: 合成参照リスト（dict 形式）。

        Returns:
            新たに永続化された DeliverableTemplate。

        Raises:
            DeliverableTemplateNotFoundError: composition に存在しない ref が含まれる場合。
            CompositionCycleError: DAG 走査で循環参照または上限超過を検出した場合。
            DeliverableTemplateInvariantViolation: ドメイン不変条件違反の場合。
        """
        new_id: DeliverableTemplateId = uuid4()
        template_type = TemplateType(type_)
        semver = _build_semver(version)
        ac_tuple = tuple(_build_acceptance_criterion(ac) for ac in acceptance_criteria)
        ref_tuple = tuple(_build_ref(r) for r in composition)

        # BUG-001: read も含め全操作を単一の begin() 内で完結させる (EmpireService パターン)。
        # composition ref の存在確認 / _check_dag が autobegin を起動したあとに
        # begin() を呼ぶと "InvalidRequestError: A transaction is already begun" が発生するため。
        async with self._session.begin():
            # composition ref の存在確認
            for ref in ref_tuple:
                existing = await self._dt_repo.find_by_id(ref.template_id)
                if existing is None:
                    raise DeliverableTemplateNotFoundError(
                        str(ref.template_id), kind="composition_ref"
                    )

            # DAG 走査
            await self._check_dag(ref_tuple, root_id=new_id)

            template = DeliverableTemplate.model_validate(
                {
                    "id": new_id,
                    "name": name,
                    "description": description,
                    "type": template_type,
                    "schema": schema,
                    "acceptance_criteria": [
                        {
                            "id": ac.id,
                            "description": ac.description,
                            "required": ac.required,
                        }
                        for ac in ac_tuple
                    ],
                    "version": {
                        "major": semver.major,
                        "minor": semver.minor,
                        "patch": semver.patch,
                    },
                    "composition": [
                        {
                            "template_id": ref.template_id,
                            "minimum_version": {
                                "major": ref.minimum_version.major,
                                "minor": ref.minimum_version.minor,
                                "patch": ref.minimum_version.patch,
                            },
                        }
                        for ref in ref_tuple
                    ],
                }
            )
            await self._dt_repo.save(template)
        return template

    async def find_all(self) -> list[DeliverableTemplate]:
        """全 DeliverableTemplate を返す（REQ-DT-HTTP-002）。

        Returns:
            0 件以上の DeliverableTemplate リスト。
        """
        return await self._dt_repo.find_all()

    async def find_by_id(self, template_id: DeliverableTemplateId) -> DeliverableTemplate:
        """主キーで単一の DeliverableTemplate をハイドレートする（REQ-DT-HTTP-003）。

        Args:
            template_id: 対象の UUID。

        Returns:
            ハイドレートされた DeliverableTemplate。

        Raises:
            DeliverableTemplateNotFoundError: ``template_id`` の DeliverableTemplate が
                存在しない場合。
        """
        result = await self._dt_repo.find_by_id(template_id)
        if result is None:
            raise DeliverableTemplateNotFoundError(str(template_id), kind="primary")
        return result

    async def update(
        self,
        template_id: DeliverableTemplateId,
        name: str,
        description: str,
        type_: str,
        schema: dict[str, object] | str,
        acceptance_criteria: list[AcceptanceCriterionDict],
        version: SemVerDict,
        composition: list[DeliverableTemplateRefDict],
    ) -> DeliverableTemplate:
        """DeliverableTemplate を全フィールド更新する（REQ-DT-HTTP-004）。

        Args:
            template_id: 対象の UUID。
            name: 新しいテンプレート名。
            description: 新しいテンプレート説明。
            type_: 新しいテンプレート種別文字列。
            schema: 新しい JSON Schema または自然言語ガイドライン。
            acceptance_criteria: 新しい受入基準リスト（dict 形式）。
            version: 新しい SemVer（dict 形式）。
            composition: 新しい合成参照リスト（dict 形式）。

        Returns:
            更新後の DeliverableTemplate。

        Raises:
            DeliverableTemplateNotFoundError: ``template_id`` の DeliverableTemplate が
                存在しない場合。
            DeliverableTemplateVersionDowngradeError: version が現 version より小さい場合。
            DeliverableTemplateNotFoundError: composition に存在しない ref が含まれる場合。
            CompositionCycleError: DAG 走査で循環参照または上限超過を検出した場合。
            DeliverableTemplateInvariantViolation: ドメイン不変条件違反の場合。
        """
        template_type = TemplateType(type_)
        new_semver = _build_semver(version)
        ac_tuple = tuple(_build_acceptance_criterion(ac) for ac in acceptance_criteria)
        ref_tuple = tuple(_build_ref(r) for r in composition)

        # BUG-001: read も含め全操作を単一の begin() 内で完結させる (EmpireService パターン)。
        async with self._session.begin():
            existing = await self._dt_repo.find_by_id(template_id)
            if existing is None:
                raise DeliverableTemplateNotFoundError(str(template_id), kind="primary")

            # §確定 B: version チェック
            current_tuple = (
                existing.version.major,
                existing.version.minor,
                existing.version.patch,
            )
            new_tuple = (new_semver.major, new_semver.minor, new_semver.patch)
            if new_tuple < current_tuple:
                raise DeliverableTemplateVersionDowngradeError(
                    current_version=str(existing.version),
                    provided_version=str(new_semver),
                )

            # composition ref の存在確認
            for ref in ref_tuple:
                ref_template = await self._dt_repo.find_by_id(ref.template_id)
                if ref_template is None:
                    raise DeliverableTemplateNotFoundError(
                        str(ref.template_id), kind="composition_ref"
                    )

            # DAG 走査（既存 id を root として循環検出）
            await self._check_dag(ref_tuple, root_id=template_id)

            # version が現 version より大きい場合は create_new_version 経由でドメイン不変条件を通す
            if new_tuple > current_tuple:
                existing = existing.create_new_version(new_semver)

            # 全フィールド再構築
            template = DeliverableTemplate.model_validate(
                {
                    "id": template_id,
                    "name": name,
                    "description": description,
                    "type": template_type,
                    "schema": schema,
                    "acceptance_criteria": [
                        {
                            "id": ac.id,
                            "description": ac.description,
                            "required": ac.required,
                        }
                        for ac in ac_tuple
                    ],
                    "version": {
                        "major": new_semver.major,
                        "minor": new_semver.minor,
                        "patch": new_semver.patch,
                    },
                    "composition": [
                        {
                            "template_id": ref.template_id,
                            "minimum_version": {
                                "major": ref.minimum_version.major,
                                "minor": ref.minimum_version.minor,
                                "patch": ref.minimum_version.patch,
                            },
                        }
                        for ref in ref_tuple
                    ],
                }
            )
            await self._dt_repo.save(template)
        return template

    async def delete(self, template_id: DeliverableTemplateId) -> None:
        """DeliverableTemplate を削除する（REQ-DT-HTTP-005）。

        Args:
            template_id: 対象の UUID。

        Raises:
            DeliverableTemplateNotFoundError: ``template_id`` の DeliverableTemplate が
                存在しない場合（Fail Fast）。
        """
        # BUG-001: Fail Fast + delete を単一の begin() 内で完結させる (EmpireService パターン)。
        # find_by_id が autobegin を起動したあとに begin() を呼ぶと
        # "InvalidRequestError: A transaction is already begun" が発生するため。
        async with self._session.begin():
            existing = await self._dt_repo.find_by_id(template_id)
            if existing is None:
                raise DeliverableTemplateNotFoundError(str(template_id), kind="primary")
            await self._dt_repo.delete(template_id)

    async def _check_dag(
        self,
        refs: tuple[DeliverableTemplateRef, ...],
        root_id: DeliverableTemplateId,
    ) -> None:
        """BFS で composition refs が DAG であることを検証する（§確定 D）。

        深度上限 = 10、ノード数上限 = 100。``root_id`` は「作成 / 更新中のテンプレート
        自身の id」であり、BFS の開始前から ``visited`` に追加して自己参照を防ぐ。

        Args:
            refs: 直接の composition refs タプル。
            root_id: 循環検出の起点となる UUID（新規作成時は生成済み uuid、
                更新時は既存 template_id）。

        Raises:
            CompositionCycleError:
                - ``reason="transitive_cycle"``: 推移的循環参照を検出。
                - ``reason="depth_limit"``: 深度が 10 を超えた。
                - ``reason="node_limit"``: 訪問ノード数が 100 を超えた。
        """
        visited: set[DeliverableTemplateId] = {root_id}
        # queue 要素: (ref, depth)
        queue: deque[tuple[DeliverableTemplateRef, int]] = deque((ref, 1) for ref in refs)

        while queue:
            ref, depth = queue.popleft()

            if ref.template_id in visited:
                raise CompositionCycleError(
                    reason="transitive_cycle",
                    cycle_path=[str(tid) for tid in visited] + [str(ref.template_id)],
                )

            if depth > _DAG_MAX_DEPTH:
                raise CompositionCycleError(reason="depth_limit")

            visited.add(ref.template_id)

            if len(visited) > _DAG_MAX_NODES:
                raise CompositionCycleError(reason="node_limit")

            # 子ノードの refs を取得して BFS キューに追加
            child_template = await self._dt_repo.find_by_id(ref.template_id)
            if child_template is not None:
                for child_ref in child_template.composition:
                    queue.append((child_ref, depth + 1))


__all__ = [
    "AcceptanceCriterionDict",
    "DeliverableTemplateRefDict",
    "DeliverableTemplateService",
    "SemVerDict",
]
