""":class:`bakufu.application.ports.RoleProfileRepository` の SQLite アダプタ。

§確定 B の UPSERT 保存フロー（子テーブルなし）を実装する:

1. ``role_profiles`` UPSERT（id 衝突時に empire_id / role / refs を更新）

``UNIQUE(empire_id, role)`` 制約は業務ルール R1-D を DB レベルで物理保証する。
同一 Empire 内で同 Role の別 id を INSERT しようとすると ``IntegrityError`` が
上位伝播する（§確定 H）。application 層の 2 重防衛
（``find_by_empire_and_role`` 事前チェック → DB 制約）の最終防衛線として機能する。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、UoW 境界を
管理する（§確定 B Tx 境界の責務分離）。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドとして保持する（§確定 C）。
``deliverable_template_refs_json`` のシリアライズ契約は §確定 G で凍結されている。
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.deliverable_template import RoleProfile
from bakufu.domain.value_objects import DeliverableTemplateRef, EmpireId
from bakufu.domain.value_objects.enums import Role
from bakufu.infrastructure.persistence.sqlite.tables.role_profiles import RoleProfileRow


class SqliteRoleProfileRepository:
    """:class:`RoleProfileRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_empire_and_role(
        self,
        empire_id: EmpireId,
        role: Role,
    ) -> RoleProfile | None:
        """``(empire_id, role)`` に対応する RoleProfile をハイドレートする。

        UNIQUE 制約により最大 1 件。該当なしは ``None`` を返す。
        """
        stmt = select(RoleProfileRow).where(
            RoleProfileRow.empire_id == empire_id,
            RoleProfileRow.role == role.value,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._from_row(row)

    async def find_all_by_empire(self, empire_id: EmpireId) -> list[RoleProfile]:
        """指定 Empire の全 RoleProfile を ``ORDER BY role ASC`` で返す（§確定 I）。

        0 件の場合は空リストを返す。ORDER BY により決定論的順序を保証する
        （empire-repository §BUG-EMR-001 コントラクト踏襲）。
        """
        stmt = (
            select(RoleProfileRow)
            .where(RoleProfileRow.empire_id == empire_id)
            .order_by(RoleProfileRow.role)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._from_row(row) for row in rows]

    async def save(self, role_profile: RoleProfile) -> None:
        """``role_profiles`` 1 テーブルへの UPSERT で永続化する（§確定 B）。

        ``ON CONFLICT (id) DO UPDATE SET ...`` を使用する。
        同一 ``(empire_id, role)`` で別 ``id`` の INSERT は
        ``UNIQUE(empire_id, role)`` 違反として ``IntegrityError`` を上位伝播する
        （§確定 H）。外側の ``async with session.begin():`` ブロックは呼び元の責任。
        """
        row = self._to_row(role_profile)
        upsert_stmt = sqlite_insert(RoleProfileRow).values(row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "empire_id": upsert_stmt.excluded.empire_id,
                "role": upsert_stmt.excluded.role,
                "deliverable_template_refs_json": (
                    upsert_stmt.excluded.deliverable_template_refs_json
                ),
            },
        )
        await self._session.execute(upsert_stmt)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(self, role_profile: RoleProfile) -> dict[str, Any]:
        """``role_profile`` を ``role_profiles`` 行の dict に変換する。"""
        return {
            "id": role_profile.id,
            # empire_id は RoleProfile.empire_id から参照（別引数不要、§確定 設計判断）。
            "empire_id": role_profile.empire_id,
            "role": role_profile.role.value,
            # §確定 G: DeliverableTemplateRef を model_dump(mode='json') で list[dict] に変換。
            # JSONEncoded TypeDecorator が json.dumps して Text に格納する。
            "deliverable_template_refs_json": [
                r.model_dump(mode="json") for r in role_profile.deliverable_template_refs
            ],
        }

    def _from_row(self, row: RoleProfileRow) -> RoleProfile:
        """行から :class:`RoleProfile` Aggregate Root を水和する。

        ``RoleProfile.model_validate`` は post-validator を再実行するため、
        水和もアプリケーション サービスが構築時に走らせるのと同じ不変条件チェックを
        通る（§確定 C）。
        """
        # §確定 G: A08 防御 — model_validate 経由で template_id UUID 型変換を保証。
        # 生 dict を Aggregate に直接渡す経路は禁止。
        ref_payloads = cast(
            "list[dict[str, Any]]",
            row.deliverable_template_refs_json or [],
        )
        deliverable_template_refs = tuple(
            DeliverableTemplateRef.model_validate(d) for d in ref_payloads
        )

        # §確定 C: model_validate 経由で post-validator（不変条件チェック）を再実行する。
        # コンストラクタ直接呼び出しでは validator が走らない経路が存在するため禁止。
        return RoleProfile.model_validate(
            {
                "id": _uuid(row.id),
                "empire_id": _uuid(row.empire_id),
                "role": Role(row.role),
                "deliverable_template_refs": deliverable_template_refs,
            }
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


__all__ = ["SqliteRoleProfileRepository"]
