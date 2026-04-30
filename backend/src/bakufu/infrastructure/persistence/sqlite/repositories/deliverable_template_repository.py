""":class:`bakufu.application.ports.DeliverableTemplateRepository` の SQLite アダプタ。

§確定 B の UPSERT 保存フロー（子テーブルなし）を実装する:

1. ``deliverable_templates`` UPSERT（id 衝突時に全カラムを更新）

acceptance_criteria / composition は JSONEncoded カラムに集約されるため、
empire-repository の delete-then-insert パターンは不要。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、UoW 境界を
管理する（§確定 B Tx 境界の責務分離）。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドとして保持し、双方向の
変換が隣接して存在するようにする（§確定 C）。これらは §確定 D〜F で凍結した
フォーマット選択をカプセル化する:

* ``schema`` — type カラムを判別キーとして JSON_SCHEMA / OPENAPI → json.dumps /
  json.loads、それ以外は plain text のまま保存（§確定 D）。
* ``version`` — ``str(template.version)`` / ``SemVer.from_str(row.version)`` で
  "major.minor.patch" TEXT に相互変換（§確定 E）。
* ``acceptance_criteria_json`` / ``composition_json`` — model_dump(mode='json') /
  model_validate(d) 経由で A08 Unsafe Deserialization を防御（§確定 F）。
"""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.deliverable_template import DeliverableTemplate
from bakufu.domain.value_objects import (
    AcceptanceCriterion,
    DeliverableTemplateId,
    DeliverableTemplateRef,
)
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.template_vos import SemVer
from bakufu.infrastructure.persistence.sqlite.tables.deliverable_templates import (
    DeliverableTemplateRow,
)

# JSON_SCHEMA / OPENAPI は dict ↔ json.dumps/loads でラウンドトリップ。
# それ以外の type は plain text のまま（§確定 D）。
_JSON_TYPES = frozenset({TemplateType.JSON_SCHEMA, TemplateType.OPENAPI})


class SqliteDeliverableTemplateRepository:
    """:class:`DeliverableTemplateRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, template_id: DeliverableTemplateId) -> DeliverableTemplate | None:
        """主キーが ``template_id`` の DeliverableTemplate をハイドレートする。

        行が存在しない場合は ``None`` を返す。
        """
        stmt = select(DeliverableTemplateRow).where(DeliverableTemplateRow.id == template_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._from_row(row)

    async def find_all(self) -> list[DeliverableTemplate]:
        """全 DeliverableTemplate 行を ``ORDER BY name ASC`` で返す（§確定 I）。

        0 件の場合は空リストを返す。ORDER BY により決定論的順序を保証する
        （empire-repository §BUG-EMR-001 コントラクト踏襲）。
        """
        stmt = select(DeliverableTemplateRow).order_by(DeliverableTemplateRow.name)
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._from_row(row) for row in rows]

    async def save(self, template: DeliverableTemplate) -> None:
        """``deliverable_templates`` 1 テーブルへの UPSERT で永続化する（§確定 B）。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。
        """
        row = self._to_row(template)
        upsert_stmt = sqlite_insert(DeliverableTemplateRow).values(row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": upsert_stmt.excluded.name,
                "description": upsert_stmt.excluded.description,
                "type": upsert_stmt.excluded.type,
                "version": upsert_stmt.excluded.version,
                "schema": upsert_stmt.excluded.schema,
                "acceptance_criteria_json": upsert_stmt.excluded.acceptance_criteria_json,
                "composition_json": upsert_stmt.excluded.composition_json,
            },
        )
        await self._session.execute(upsert_stmt)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(self, template: DeliverableTemplate) -> dict[str, Any]:
        """``template`` を ``deliverable_templates`` 行の dict に変換する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存することを防ぐため、
        SQLAlchemy の ``Row`` オブジェクトは意図的に使わない。
        """
        # §確定 D: JSON_SCHEMA / OPENAPI は json.dumps、それ以外は plain text。
        schema_value: str = (
            json.dumps(template.schema)
            if template.type in _JSON_TYPES
            else cast(str, template.schema)
        )
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "type": template.type.value,
            # §確定 E: SemVer を "major.minor.patch" 形式に変換。
            "version": str(template.version),
            "schema": schema_value,
            # §確定 F: AcceptanceCriterion を model_dump(mode='json') で list[dict] に変換。
            # JSONEncoded TypeDecorator が json.dumps して Text に格納する。
            "acceptance_criteria_json": [
                c.model_dump(mode="json") for c in template.acceptance_criteria
            ],
            # §確定 F: DeliverableTemplateRef を model_dump(mode='json') で list[dict] に変換。
            "composition_json": [r.model_dump(mode="json") for r in template.composition],
        }

    def _from_row(self, row: DeliverableTemplateRow) -> DeliverableTemplate:
        """行から :class:`DeliverableTemplate` Aggregate Root を水和する。

        ``DeliverableTemplate.model_validate`` は post-validator を再実行するため、
        リポジトリ側の水和もアプリケーション サービスが構築時に走らせるのと同じ
        不変条件チェックを通る（§確定 C）。
        """
        template_type = TemplateType(row.type)

        # §確定 D: type カラムを判別キーとしてシリアライズ形式を逆転する。
        schema_value: dict[str, object] | str = (
            json.loads(row.schema) if template_type in _JSON_TYPES else row.schema
        )

        # §確定 E: "major.minor.patch" TEXT を SemVer に復元。
        version = SemVer.from_str(row.version)

        # §確定 F: A08 防御 — model_validate 経由で UUID 型変換を保証。
        # 生 dict を Aggregate に直接渡す経路は禁止（§確定 F 理由参照）。
        ac_payloads = cast(
            "list[dict[str, Any]]",
            row.acceptance_criteria_json or [],
        )
        acceptance_criteria = tuple(AcceptanceCriterion.model_validate(d) for d in ac_payloads)

        comp_payloads = cast(
            "list[dict[str, Any]]",
            row.composition_json or [],
        )
        composition = tuple(DeliverableTemplateRef.model_validate(d) for d in comp_payloads)

        return DeliverableTemplate(
            id=_uuid(row.id),
            name=row.name,
            description=row.description,
            type=template_type,
            schema=schema_value,
            version=version,
            acceptance_criteria=acceptance_criteria,
            composition=composition,
        )


def _uuid(value: UUID | str) -> UUID:
    """行の値を :class:`uuid.UUID` に強制変換する。

    SQLAlchemy の UUIDStr TypeDecorator は ``process_result_value`` で既に ``UUID``
    インスタンスを返すが、防御的な強制変換により、raw SQL 経路の水和も同じコードを
    通せる。
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


__all__ = ["SqliteDeliverableTemplateRepository"]
