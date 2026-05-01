""":class:`bakufu.domain.ports.AbstractDeliverableRecordRepository` の SQLite アダプタ。

§確定 D の 7 ステップ保存フローを 2 つのテーブル
（``deliverable_records`` / ``criterion_validation_results``）に対して実装する:

1. ``DELETE FROM criterion_validation_results WHERE deliverable_record_id = :id`` —
   CASCADE 親無し、直接 DELETE。新規 Record では 0 行（no-op）。
2. ``DELETE FROM deliverable_records WHERE id = :id`` —
   直接 DELETE。criterion_validation_results は Step 1 で削除済み。
3. ``INSERT INTO deliverable_records VALUES (...)`` — 新 Record 挿入。
4. ``INSERT INTO criterion_validation_results VALUES (...) * N`` —
   新評価結果挿入（N 件）。record_id FK が Step 3 で確定済み。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、
全ステップを 1 トランザクションに収める（empire-repo §確定 B Tx 境界の責務分離）。

``save(record)`` は **標準の 1 引数パターン**（§確定 R1-F）を使う:
:class:`DeliverableRecord` は全ての必要な属性を自身に保持するため、
リポジトリはそれらを直接読む。

``_to_rows`` / ``_from_rows`` はクラスのプライベートメソッドのまま保持し、
双方向の変換が隣接して存在するようにする（empire-repo §確定 C）。

TypeDecorator-trust パターン（§確定 R1-A）: :class:`UUIDStr` は
``process_result_value`` で ``UUID`` インスタンスを返すため、``row.id`` 等は
すでに ``UUID`` である。防御的な ``UUID(row.id)`` ラッピング無しで属性を直接参照する
のが正しく、必須である。:class:`MaskedText` は SELECT 時に伏字化済みの文字列を返し、
INSERT 時には素のドメイン文字列が渡され、``process_bind_param`` がマスキング ゲートを
自動適用する。
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.deliverable_record.deliverable_record import DeliverableRecord
from bakufu.domain.value_objects.deliverable_record_vos import CriterionValidationResult
from bakufu.domain.value_objects.enums import ValidationStatus
from bakufu.domain.value_objects.identifiers import DeliverableId, DeliverableRecordId
from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer
from bakufu.infrastructure.persistence.sqlite.tables.criterion_validation_results import (
    CriterionValidationResultRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.deliverable_records import (
    DeliverableRecordRow,
)


class SqliteDeliverableRecordRepository:
    """:class:`AbstractDeliverableRecordRepository` の SQLite 実装（§確定 D）。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: DeliverableRecord) -> None:
        """§確定 D の 4 ステップ delete-then-insert で ``record`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。失敗はそのまま
        伝播するため、アプリケーション サービスの Unit-of-Work 境界はクリーンに
        ロールバックできる（empire-repo §確定 B 踏襲）。
        """
        record_row, result_rows = self._to_rows(record)

        # Step 1: DELETE criterion_validation_results（CASCADE 無し、直接）。
        # FK の子テーブルを先に削除して FK 制約違反を回避する。
        await self._session.execute(
            delete(CriterionValidationResultRow).where(
                CriterionValidationResultRow.deliverable_record_id == record.id
            )
        )

        # Step 2: DELETE deliverable_records（子テーブル削除済み）。
        await self._session.execute(
            delete(DeliverableRecordRow).where(DeliverableRecordRow.id == record.id)
        )

        # Step 3: INSERT deliverable_records。
        await self._session.execute(insert(DeliverableRecordRow).values(record_row))

        # Step 4: INSERT criterion_validation_results。
        # deliverable_record_id FK が Step 3 で確定済み。
        if result_rows:
            await self._session.execute(insert(CriterionValidationResultRow), result_rows)

    async def find_by_id(self, record_id: DeliverableRecordId) -> DeliverableRecord | None:
        """record_id で DeliverableRecord を 1 件取得する。

        行が存在しない場合は ``None`` を返す。
        子テーブルは ``created_at ASC, id ASC`` で ORDER BY して
        決定的な順序を保証する（§確定 R1-H）。
        """
        record_row = (
            await self._session.execute(
                select(DeliverableRecordRow).where(DeliverableRecordRow.id == record_id)
            )
        ).scalar_one_or_none()
        if record_row is None:
            return None
        return await self._hydrate_row(record_row)

    async def find_by_deliverable_id(
        self, deliverable_id: DeliverableId
    ) -> DeliverableRecord | None:
        """deliverable_id で最新の DeliverableRecord を 1 件取得する。

        ``created_at DESC LIMIT 1`` で最新レコードを取得する。
        ``ix_deliverable_records_deliverable_id`` が WHERE を高速化する（§確定 R1-K）。
        対象レコードが存在しない場合は ``None`` を返す。
        """
        record_row = (
            await self._session.execute(
                select(DeliverableRecordRow)
                .where(DeliverableRecordRow.deliverable_id == deliverable_id)
                .order_by(DeliverableRecordRow.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if record_row is None:
            return None
        return await self._hydrate_row(record_row)

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------

    async def _hydrate_row(self, record_row: DeliverableRecordRow) -> DeliverableRecord:
        """既にロード済みの record 行に対する子テーブルを取得して再構築する。

        :meth:`find_by_id`、:meth:`find_by_deliverable_id` で共有し、
        ルート テーブルの冗長な再取得を避ける。
        """
        # §確定 R1-H: ORDER BY created_at ASC, id ASC（決定的な順序で水和）。
        result_rows = list(
            (
                await self._session.execute(
                    select(CriterionValidationResultRow)
                    .where(CriterionValidationResultRow.deliverable_record_id == record_row.id)
                    .order_by(
                        CriterionValidationResultRow.created_at.asc(),
                        CriterionValidationResultRow.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return self._from_rows(record_row, result_rows)

    def _to_rows(
        self,
        record: DeliverableRecord,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """``record`` を ``(record_row, result_rows)`` に変換する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存しないよう、SQLAlchemy ``Row``
        オブジェクトは使わない。

        TypeDecorator-trust（§確定 R1-A）: 生のドメイン値を直接渡す。``UUIDStr`` /
        ``MaskedText`` / ``UTCDateTime`` の TypeDecorator がバインド パラメータ時点で
        全ての変換を行う。``content`` は素の文字列として渡す —
        ``MaskedText.process_bind_param`` が手動の ``MaskingGateway.mask()`` 呼び出し
        無しに自動的にマスキング ゲートを適用する。

        CriterionValidationResult の PK: ``criterion_validation_results.id`` はドメイン
        レベルのアイデンティティを持たない（ビジネス キーは ``(deliverable_record_id,
        criterion_id)``）。保存ごとに各行で新しい ``uuid4()`` を生成する。
        Step 1 の DELETE と Step 4 の INSERT により PK 衝突は起きない。
        """
        record_row: dict[str, Any] = {
            "id": record.id,
            "deliverable_id": record.deliverable_id,
            # template_ref インライン展開。
            "template_ref_template_id": record.template_ref.template_id,
            "template_ref_version_major": record.template_ref.minimum_version.major,
            "template_ref_version_minor": record.template_ref.minimum_version.minor,
            "template_ref_version_patch": record.template_ref.minimum_version.patch,
            # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
            "content": record.content,
            "task_id": record.task_id,
            "validation_status": record.validation_status.value,
            "produced_by": record.produced_by,
            "created_at": record.created_at,
            "validated_at": record.validated_at,
        }

        # 評価日時: validated_at があればそれを使用、なければ現在時刻。
        result_created_at = record.validated_at or datetime.now(UTC)

        result_rows: list[dict[str, Any]] = [
            {
                # 新規 UUID PK — ビジネス キーは (deliverable_record_id, criterion_id)。
                "id": _uuid.uuid4(),
                "deliverable_record_id": record.id,
                "criterion_id": result.criterion_id,
                "status": result.status.value,
                "reason": result.reason,
                # required: §確定 R1-G の overall status 導出に必要なスナップショット。
                "required": result.required,
                "created_at": result_created_at,
            }
            for result in record.criterion_results
        ]

        return record_row, result_rows

    def _from_rows(
        self,
        record_row: DeliverableRecordRow,
        result_rows: list[CriterionValidationResultRow],
    ) -> DeliverableRecord:
        """行型から :class:`DeliverableRecord` を水和する。

        ``DeliverableRecord(...)`` の直接構築は post-validator を再実行するため、
        リポジトリ側の水和も domain 層の不変条件チェックを通る
        （empire §確定 C コントラクト踏襲）。

        TypeDecorator-trust（§確定 R1-A）: ``UUIDStr`` は ``process_result_value`` で
        ``UUID`` インスタンスを返し、``UTCDateTime`` は tz-aware ``datetime`` を返し、
        ``MaskedText`` は伏字化済みの文字列を返す。``UUID(row.id)`` のような防御的
        ラッピングは不要。

        §確定 R1-J §不可逆性: ``content`` はディスクから既に伏字化されたテキストを
        保持する。DeliverableRecord の ``content`` フィールドは任意の文字列を受理する
        ため、伏字化された形でも構築は通る。
        """
        # template_ref をインライン列から再構築する。
        template_ref = DeliverableTemplateRef(
            template_id=record_row.template_ref_template_id,
            minimum_version=SemVer(
                major=record_row.template_ref_version_major,
                minor=record_row.template_ref_version_minor,
                patch=record_row.template_ref_version_patch,
            ),
        )

        # §確定 R1-C: result_rows から criterion_results を再構築する
        # （呼び元側で created_at ASC, id ASC でソート済み）。
        # TypeDecorator-trust（§確定 R1-A）: UUIDStr.process_result_value は
        # 既に UUID インスタンスを返す — 防御的ラッピング不要。
        criterion_results = tuple(
            CriterionValidationResult(
                criterion_id=r.criterion_id,
                status=ValidationStatus(r.status),
                reason=r.reason,
                # required: §確定 R1-G のスナップショットを復元する。
                required=r.required,
            )
            for r in result_rows
        )

        return DeliverableRecord(
            id=record_row.id,
            deliverable_id=record_row.deliverable_id,
            template_ref=template_ref,
            content=record_row.content,
            task_id=record_row.task_id,
            validation_status=ValidationStatus(record_row.validation_status),
            criterion_results=criterion_results,
            produced_by=record_row.produced_by,
            created_at=record_row.created_at,
            validated_at=record_row.validated_at,
        )


__all__ = ["SqliteDeliverableRecordRepository"]
