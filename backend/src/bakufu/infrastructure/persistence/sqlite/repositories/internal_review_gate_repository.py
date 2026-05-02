""":class:`bakufu.application.ports.InternalReviewGateRepository` の SQLite アダプタ。

§確定A の UPSERT + DELETE/bulk INSERT 保存フローを 2 つのテーブル
（``internal_review_gates`` / ``internal_review_gate_verdicts``）に対して実装する:

1. ``internal_review_gates`` UPSERT（id 衝突時に ``gate_decision`` を更新。
   ``task_id``、``stage_id``、``required_gate_roles``、``created_at`` は
   意図的に **更新しない** — Gate の起源は作成後に不変）。
2. ``DELETE FROM internal_review_gate_verdicts WHERE gate_id = :id`` —
   既存 Verdict を全件削除してから再 INSERT する（DELETE-then-INSERT パターン）。
3. ``INSERT INTO internal_review_gate_verdicts`` — ``gate.verdicts`` の
   :class:`Verdict` ごとに 1 行。保存ごとに各行で新しい ``uuid4()`` PK を生成する
   （§確定D）。``order_index`` で元の tuple 順序を保持（enumerate で付与）。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、全ステップを
1 トランザクションに収める（empire-repo §確定 B Tx 境界の責務分離）。

``find_by_task_and_stage`` は ``gate_decision='PENDING'`` のみを返す（§確定E:
PENDINGのみが"現在のGate"）。決定済みの Gate は履歴として ``find_all_by_task_id``
経由でアクセス可能。

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

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import (
    GateDecision,
    InternalGateId,
    StageId,
    TaskId,
)
from bakufu.infrastructure.persistence.sqlite.tables.internal_review_gate_verdicts import (
    InternalReviewGateVerdictRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.internal_review_gates import (
    InternalReviewGateRow,
)


class SqliteInternalReviewGateRepository:
    """:class:`InternalReviewGateRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, gate_id: InternalGateId) -> InternalReviewGate | None:
        """gate 行を SELECT し、:meth:`_hydrate_row` で水和する。

        gate 行が存在しない場合は ``None`` を返す。
        """
        gate_row = (
            await self._session.execute(
                select(InternalReviewGateRow).where(InternalReviewGateRow.id == gate_id)
            )
        ).scalar_one_or_none()
        if gate_row is None:
            return None
        return await self._hydrate_row(gate_row)

    async def find_by_task_and_stage(
        self, task_id: TaskId, stage_id: StageId
    ) -> InternalReviewGate | None:
        """``task_id`` と ``stage_id`` で PENDING Gate を検索する。

        §確定E: gate_decision='PENDING' のみを "現在のGate" として返す。決定済みの
        Gate は ``find_all_by_task_id`` 経由でアクセス可能。

        複合インデックス ``ix_internal_review_gates_task_id_stage_id`` が
        WHERE task_id + stage_id + gate_decision='PENDING' フィルタを最適化する。
        """
        gate_row = (
            await self._session.execute(
                select(InternalReviewGateRow)
                .where(
                    InternalReviewGateRow.task_id == task_id,
                    InternalReviewGateRow.stage_id == stage_id,
                    InternalReviewGateRow.gate_decision == GateDecision.PENDING.value,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if gate_row is None:
            return None
        return await self._hydrate_row(gate_row)

    async def find_all_by_task_id(self, task_id: TaskId) -> list[InternalReviewGate]:
        """``task_id`` の全 Gate を ``created_at ASC, id ASC`` 順で返す。

        インデックス ``ix_internal_review_gates_task_id`` が WHERE task_id +
        ORDER BY created_at ASC を最適化する。指定 Task の Gate が無い場合は
        ``[]`` を返す。
        """
        gate_rows = list(
            (
                await self._session.execute(
                    select(InternalReviewGateRow)
                    .where(InternalReviewGateRow.task_id == task_id)
                    .order_by(
                        InternalReviewGateRow.created_at.asc(),
                        InternalReviewGateRow.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not gate_rows:
            return []

        results: list[InternalReviewGate] = []
        for gate_row in gate_rows:
            results.append(await self._hydrate_row(gate_row))
        return results

    async def save(self, gate: InternalReviewGate) -> None:
        """§確定A の UPSERT + DELETE/bulk INSERT で ``gate`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。失敗はそのまま
        伝播するため、アプリケーション サービスの Unit-of-Work 境界はクリーンに
        ロールバックできる（empire-repo §確定 B 踏襲）。
        """
        # Step 1: _to_rows で gate を行データに変換する。
        gate_row, verdict_rows = self._to_rows(gate)

        # Step 2: internal_review_gates UPSERT。
        # 不変フィールド（task_id, stage_id, required_gate_roles, created_at）は
        # DO UPDATE から除外 — Gate の起源は作成後に変化しない。
        upsert_stmt = sqlite_insert(InternalReviewGateRow).values(gate_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "gate_decision": upsert_stmt.excluded.gate_decision,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 3: DELETE internal_review_gate_verdicts（CASCADE 無し、直接）。
        # 既存 Verdict を全件削除してから Step 4 で再 INSERT する。
        await self._session.execute(
            delete(InternalReviewGateVerdictRow).where(
                InternalReviewGateVerdictRow.gate_id == gate.id
            )
        )

        # Step 4: bulk INSERT internal_review_gate_verdicts。
        # gate_id FK が Step 2 で確定済み。order_index で元の tuple 順序を保持。
        if verdict_rows:
            await self._session.execute(insert(InternalReviewGateVerdictRow), verdict_rows)

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------

    async def _hydrate_row(self, gate_row: InternalReviewGateRow) -> InternalReviewGate:
        """既にロード済みの gate 行に対する子テーブルを取得して再構築する。

        :meth:`find_by_id`、:meth:`find_by_task_and_stage`、:meth:`find_all_by_task_id`
        で共有し、ルート テーブルの冗長な再取得を避ける。
        """
        # order_index ASC で Verdict タプルの元の順序を復元する。
        verdict_rows = list(
            (
                await self._session.execute(
                    select(InternalReviewGateVerdictRow)
                    .where(InternalReviewGateVerdictRow.gate_id == gate_row.id)
                    .order_by(InternalReviewGateVerdictRow.order_index.asc())
                )
            )
            .scalars()
            .all()
        )

        return InternalReviewGate.model_validate(
            {
                "id": gate_row.id,  # UUIDStr TypeDecorator が UUID 型で返す
                "task_id": gate_row.task_id,
                "stage_id": gate_row.stage_id,
                "required_gate_roles": frozenset(
                    gate_row.required_gate_roles
                ),  # JSON配列→frozenset
                "gate_decision": gate_row.gate_decision,
                "created_at": gate_row.created_at,
                "verdicts": [
                    {
                        "role": vrow.role,
                        "agent_id": vrow.agent_id,
                        "decision": vrow.decision,
                        "comment": vrow.comment or "",
                        "decided_at": vrow.decided_at,
                    }
                    for vrow in verdict_rows
                ],
            }
        )

    def _to_rows(
        self,
        gate: InternalReviewGate,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """``gate`` を ``(gate_row, verdict_rows)`` に変換する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存しないよう、SQLAlchemy ``Row``
        オブジェクトは使わない。

        TypeDecorator-trust（§確定 R1-A）: 生のドメイン値を直接渡す。``UUIDStr`` /
        ``MaskedText`` / ``UTCDateTime`` / ``JSONEncoded`` の TypeDecorator が
        バインド パラメータ時点で全ての変換を行う。``comment`` は素の文字列として渡す —
        ``MaskedText.process_bind_param`` が手動のマスキング呼び出し無しに自動的に
        マスキング ゲートを適用する。

        Verdict の PK: ``internal_review_gate_verdicts.id`` はドメインレベルの
        アイデンティティを持たない（ビジネス キーは ``UNIQUE(gate_id, role)``）。
        保存ごとに各 verdict 行で新しい ``uuid4()`` を生成する（§確定D）。
        step 3 の DELETE と step 4 の INSERT により PK 衝突は起きない。
        """
        gate_row: dict[str, Any] = {
            "id": gate.id,
            "task_id": gate.task_id,
            "stage_id": gate.stage_id,
            # frozenset → sorted list として JSONEncoded に渡す（JSON配列として保存）。
            "required_gate_roles": sorted(gate.required_gate_roles),
            "gate_decision": gate.gate_decision.value,
            "created_at": gate.created_at,
        }

        verdict_rows: list[dict[str, Any]] = [
            {
                # 新規 UUID PK — §確定D: 保存ごとに uuid4() で再生成する。
                "id": str(_uuid.uuid4()),
                "gate_id": gate.id,
                "order_index": idx,
                "role": verdict.role,
                "agent_id": verdict.agent_id,
                "decision": verdict.decision.value,
                # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
                "comment": verdict.comment,
                "decided_at": verdict.decided_at,
            }
            for idx, verdict in enumerate(gate.verdicts)
        ]

        return gate_row, verdict_rows


__all__ = ["SqliteInternalReviewGateRepository"]
