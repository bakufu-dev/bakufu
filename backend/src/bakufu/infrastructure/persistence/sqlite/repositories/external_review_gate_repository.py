""":class:`bakufu.application.ports.ExternalReviewGateRepository` の SQLite アダプタ。

§確定 R1-B の 5 ステップ保存フローを 3 つのテーブル
（``external_review_gates`` / ``external_review_gate_attachments`` /
``external_review_audit_entries``）に対して実装する:

1. ``DELETE FROM external_review_gate_attachments WHERE gate_id = :id`` —
   CASCADE 親無し、直接 DELETE。新規 Gate では 0 行（no-op）。
2. ``DELETE FROM external_review_audit_entries WHERE gate_id = :id`` —
   同様。直接 DELETE、CASCADE 親無し。
3. ``external_review_gates`` UPSERT（id 衝突時に変更可能フィールドを更新。
   ``task_id``、``stage_id``、``reviewer_id``、``created_at``、および全 ``snapshot_*``
   カラムは意図的に **更新しない** — Gate の起源、レビュアー アサイン、成果物スナップ
   ショットは作成後に不変）。
4. ``INSERT INTO external_review_gate_attachments`` —
   ``gate.deliverable_snapshot.attachments`` の :class:`Attachment` ごとに 1 行。
   保存ごとに各行で新しい ``uuid4()`` PK を生成する（DELETE-then-INSERT パターンが
   PK 衝突しないことを保証する）。ビジネス キーは引き続き ``UNIQUE(gate_id, sha256)``。
5. ``INSERT INTO external_review_audit_entries`` — ``gate.audit_trail`` の
   :class:`AuditEntry` ごとに 1 行。PK は ``AuditEntry.id`` から直接取得する
   （ドメイン側で割り当てられた UUID、再生成しない）。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、5 ステップ全てを
1 トランザクションに収める（empire-repo §確定 B Tx 境界の責務分離）。

``save(gate)`` は **標準の 1 引数パターン**（§確定 R1-F）を使う:
:class:`ExternalReviewGate` は全ての必要な属性を自身に保持するため、リポジトリは
それらを直接読む。

``_to_rows`` / ``_from_rows`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（empire-repo §確定 C）。

TypeDecorator-trust パターン（§確定 R1-A）: :class:`UUIDStr` は
``process_result_value`` で ``UUID`` インスタンスを返すため、``row.id`` 等は
すでに ``UUID`` である。防御的な ``UUID(row.id)`` ラッピング無しで属性を直接参照する
のが正しく、必須である。:class:`MaskedText` は SELECT 時に伏字化済みの文字列を返し、
INSERT 時には素のドメイン文字列が渡され、``process_bind_param`` がマスキング ゲート
を自動適用する。
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import (
    Attachment,
    AuditAction,
    AuditEntry,
    Deliverable,
    GateId,
    OwnerId,
    ReviewDecision,
    TaskId,
)
from bakufu.infrastructure.persistence.sqlite.tables.external_review_audit_entries import (
    ExternalReviewAuditEntryRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.external_review_gate_attachments import (
    ExternalReviewGateAttachmentRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.external_review_gates import (
    ExternalReviewGateRow,
)


class SqliteExternalReviewGateRepository:
    """:class:`ExternalReviewGateRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, gate_id: GateId) -> ExternalReviewGate | None:
        """gate 行と 2 つの子テーブルを SELECT し、:meth:`_from_rows` で水和する。

        gate 行が存在しない場合は ``None`` を返す。成功時は §確定 R1-H の ORDER BY
        句で 2 つの子テーブル全てを問い合わせるため、水和された Aggregate は決定的になる。
        """
        gate_row = (
            await self._session.execute(
                select(ExternalReviewGateRow).where(ExternalReviewGateRow.id == gate_id)
            )
        ).scalar_one_or_none()
        if gate_row is None:
            return None
        return await self._hydrate_row(gate_row)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM external_review_gates``。

        SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を発行するため、
        SQLite は全 PK を Python にストリームせずスカラー 1 行だけ返す
        （empire-repo §確定 D 踏襲）。
        """
        return (
            await self._session.execute(select(func.count()).select_from(ExternalReviewGateRow))
        ).scalar_one()

    async def save(self, gate: ExternalReviewGate) -> None:
        """§確定 R1-B の 5 ステップ delete-then-insert で ``gate`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。失敗はそのまま
        伝播するため、アプリケーション サービスの Unit-of-Work 境界はクリーンに
        ロールバックできる（empire-repo §確定 B 踏襲）。
        """
        gate_row, attach_rows, audit_rows = self._to_rows(gate)

        # Step 1: DELETE external_review_gate_attachments（CASCADE 無し、直接）。
        await self._session.execute(
            delete(ExternalReviewGateAttachmentRow).where(
                ExternalReviewGateAttachmentRow.gate_id == gate.id
            )
        )

        # Step 2: DELETE external_review_audit_entries（CASCADE 無し、直接）。
        await self._session.execute(
            delete(ExternalReviewAuditEntryRow).where(
                ExternalReviewAuditEntryRow.gate_id == gate.id
            )
        )

        # Step 3: external_review_gates UPSERT。
        # 不変フィールドは DO UPDATE から除外 — Gate の起源、レビュアー アサイン、
        # 成果物スナップショットは作成後に変化しない。
        upsert_stmt = sqlite_insert(ExternalReviewGateRow).values(gate_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "decision": upsert_stmt.excluded.decision,
                "feedback_text": upsert_stmt.excluded.feedback_text,
                "decided_at": upsert_stmt.excluded.decided_at,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 4: INSERT external_review_gate_attachments。
        if attach_rows:
            await self._session.execute(insert(ExternalReviewGateAttachmentRow), attach_rows)

        # Step 5: INSERT external_review_audit_entries。
        if audit_rows:
            await self._session.execute(insert(ExternalReviewAuditEntryRow), audit_rows)

    async def find_pending_by_reviewer(self, reviewer_id: OwnerId) -> list[ExternalReviewGate]:
        """``reviewer_id`` の全 PENDING Gate を ``created_at DESC, id DESC`` 順で返す。

        ``(reviewer_id, decision)`` 上の複合 INDEX
        ``ix_external_review_gates_reviewer_decision`` が WHERE フィルタをカバーする
        （§確定 R1-K）。指定レビュアーの PENDING Gate が無い場合は ``[]`` を返す。
        """
        gate_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewGateRow)
                    .where(
                        ExternalReviewGateRow.reviewer_id == reviewer_id,
                        ExternalReviewGateRow.decision == ReviewDecision.PENDING.value,
                    )
                    .order_by(
                        ExternalReviewGateRow.created_at.desc(),
                        ExternalReviewGateRow.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not gate_rows:
            return []

        results: list[ExternalReviewGate] = []
        for gate_row in gate_rows:
            results.append(await self._hydrate_row(gate_row))
        return results

    async def find_by_task_id(self, task_id: TaskId) -> list[ExternalReviewGate]:
        """``task_id`` の全 Gate を ``created_at ASC, id ASC`` 順で返す。

        ``(task_id, created_at)`` 上の複合 INDEX
        ``ix_external_review_gates_task_id_created`` は WHERE と ORDER BY の両方を
        1 回の B-tree スキャンでカバーする（§確定 R1-K）。指定 Task の Gate が無い場合
        は ``[]`` を返す。
        """
        gate_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewGateRow)
                    .where(ExternalReviewGateRow.task_id == task_id)
                    .order_by(
                        ExternalReviewGateRow.created_at.asc(),
                        ExternalReviewGateRow.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not gate_rows:
            return []

        results: list[ExternalReviewGate] = []
        for gate_row in gate_rows:
            results.append(await self._hydrate_row(gate_row))
        return results

    async def count_by_decision(self, decision: ReviewDecision) -> int:
        """``SELECT COUNT(*) FROM external_review_gates WHERE decision = :decision``。

        ``(decision)`` 上の INDEX ``ix_external_review_gates_decision`` がこの WHERE
        フィルタを高速化する（§確定 R1-K）。指定 decision の Gate が無い場合は 0 を返す。
        """
        return (
            await self._session.execute(
                select(func.count())
                .select_from(ExternalReviewGateRow)
                .where(ExternalReviewGateRow.decision == decision.value)
            )
        ).scalar_one()

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------

    async def _hydrate_row(self, gate_row: ExternalReviewGateRow) -> ExternalReviewGate:
        """既にロード済みの gate 行に対する子テーブルを取得して再構築する。

        :meth:`find_by_id`、:meth:`find_pending_by_reviewer`、:meth:`find_by_task_id`
        で共有し、ルート テーブルの冗長な再取得を避ける。
        """
        # §確定 R1-H: ORDER BY sha256 ASC（gate スコープで UNIQUE で決定的）。
        attach_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewGateAttachmentRow)
                    .where(ExternalReviewGateAttachmentRow.gate_id == gate_row.id)
                    .order_by(ExternalReviewGateAttachmentRow.sha256.asc())
                )
            )
            .scalars()
            .all()
        )

        # §確定 R1-H: ORDER BY occurred_at ASC, id ASC（追記専用の監査証跡は時系列順で
        # 再構築する必要があり、id がタイムスタンプ重複の決め手となる）。
        audit_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewAuditEntryRow)
                    .where(ExternalReviewAuditEntryRow.gate_id == gate_row.id)
                    .order_by(
                        ExternalReviewAuditEntryRow.occurred_at.asc(),
                        ExternalReviewAuditEntryRow.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

        return self._from_rows(gate_row, attach_rows, audit_rows)

    def _to_rows(
        self,
        gate: ExternalReviewGate,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """``gate`` を ``(gate_row, attach_rows, audit_rows)`` に変換する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存しないよう、SQLAlchemy ``Row``
        オブジェクトは使わない。

        TypeDecorator-trust（§確定 R1-A）: 生のドメイン値を直接渡す。``UUIDStr`` /
        ``MaskedText`` / ``UTCDateTime`` の TypeDecorator がバインド パラメータ時点で
        全ての変換を行う。``feedback_text``、``snapshot_body_markdown``、``comment``
        は素の文字列として渡す — ``MaskedText.process_bind_param`` が手動の
        ``MaskingGateway.mask()`` 呼び出し無しに自動的にマスキング ゲートを適用する。

        Attachment の PK: ``external_review_gate_attachments.id`` はドメインレベルの
        アイデンティティを持たない（ビジネス キーは ``UNIQUE(gate_id, sha256)``）。
        保存ごとに各 attachment 行で新しい ``uuid4()`` を生成する。step 1 の DELETE
        と step 4 の INSERT により PK 衝突は起きない。

        Audit entry の PK: ``external_review_audit_entries.id`` は ``AuditEntry.id``
        から直接取得（ドメイン側で割り当てられた UUID）。step 2+5 の DELETE-then-INSERT
        フローにより、証跡が伸びても PK 衝突は起きない。
        """
        gate_row: dict[str, Any] = {
            "id": gate.id,
            "task_id": gate.task_id,
            "stage_id": gate.stage_id,
            "reviewer_id": gate.reviewer_id,
            "decision": gate.decision.value,
            # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
            "feedback_text": gate.feedback_text,
            # インラインのスナップショット コピー — 構築後に不変（§確定 D）。
            "snapshot_stage_id": gate.deliverable_snapshot.stage_id,
            # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
            "snapshot_body_markdown": gate.deliverable_snapshot.body_markdown,
            "snapshot_committed_by": gate.deliverable_snapshot.committed_by,
            "snapshot_committed_at": gate.deliverable_snapshot.committed_at,
            "created_at": gate.created_at,
            "decided_at": gate.decided_at,
        }

        attach_rows: list[dict[str, Any]] = [
            {
                # 新規 UUID PK — ビジネス キーは UNIQUE(gate_id, sha256)。
                "id": _uuid.uuid4(),
                "gate_id": gate.id,
                "sha256": attachment.sha256,
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
            }
            for attachment in gate.deliverable_snapshot.attachments
        ]

        audit_rows: list[dict[str, Any]] = [
            {
                # AuditEntry.id はドメイン側で割り当てられた値 — そのまま保持する。
                "id": entry.id,
                "gate_id": gate.id,
                "actor_id": entry.actor_id,
                "action": entry.action.value,
                # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
                "comment": entry.comment,
                "occurred_at": entry.occurred_at,
            }
            for entry in gate.audit_trail
        ]

        return gate_row, attach_rows, audit_rows

    def _from_rows(
        self,
        gate_row: ExternalReviewGateRow,
        attach_rows: list[ExternalReviewGateAttachmentRow],
        audit_rows: list[ExternalReviewAuditEntryRow],
    ) -> ExternalReviewGate:
        """行型から :class:`ExternalReviewGate` を水和する。

        ``ExternalReviewGate(...)`` の直接構築は post-validator を再実行するため、
        リポジトリ側の水和も ``GateService.create()`` が構築時に走らせるのと同じ
        不変条件チェックを通る（empire §確定 C コントラクト「リポジトリ水和は妥当な
        Gate を生成するか例外を送出する」）。

        TypeDecorator-trust（§確定 R1-A）: ``UUIDStr`` は ``process_result_value`` で
        ``UUID`` インスタンスを返し、``UTCDateTime`` は tz-aware ``datetime`` を返し、
        ``MaskedText`` は伏字化済みの文字列を返す。``UUID(row.id)`` のような防御的
        ラッピングは不要。

        §確定 R1-J §不可逆性: ``feedback_text``、``snapshot_body_markdown``、
        ``comment`` はディスクから既に伏字化されたテキストを保持する。全フィールドは
        長さ上限内の任意の文字列を受理するため、伏字化された形でも構築は通る。
        """
        # §確定 R1-C: gate_row のスカラと attach_rows から deliverable_snapshot を
        # 再構築する（attach_rows は呼び元側で sha256 ASC でソート済み）。
        attachments = [
            Attachment(
                sha256=a.sha256,
                filename=a.filename,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
            )
            for a in attach_rows
        ]
        deliverable_snapshot = Deliverable(
            stage_id=gate_row.snapshot_stage_id,
            body_markdown=gate_row.snapshot_body_markdown,
            attachments=attachments,
            committed_by=gate_row.snapshot_committed_by,
            committed_at=gate_row.snapshot_committed_at,
        )

        # §確定 R1-C: audit_rows から audit_trail を再構築する（呼び元側で
        # occurred_at ASC, id ASC でソート済み — 追記専用ドメイン順と一致）。
        # TypeDecorator-trust（§確定 R1-A）: UUIDStr.process_result_value は
        # 既に UUID インスタンスを返す — 防御的ラッピング不要。
        audit_trail: list[AuditEntry] = [
            AuditEntry(
                id=r.id,
                actor_id=r.actor_id,
                action=AuditAction(r.action),
                comment=r.comment,
                occurred_at=r.occurred_at,
            )
            for r in audit_rows
        ]

        return ExternalReviewGate(
            id=gate_row.id,
            task_id=gate_row.task_id,
            stage_id=gate_row.stage_id,
            deliverable_snapshot=deliverable_snapshot,
            reviewer_id=gate_row.reviewer_id,
            decision=ReviewDecision(gate_row.decision),
            feedback_text=gate_row.feedback_text,
            audit_trail=audit_trail,
            created_at=gate_row.created_at,
            decided_at=gate_row.decided_at,
        )


__all__ = ["SqliteExternalReviewGateRepository"]
