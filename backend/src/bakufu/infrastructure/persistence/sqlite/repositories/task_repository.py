""":class:`bakufu.application.ports.TaskRepository` の SQLite アダプタ。

§確定 R1-B の 6 ステップ保存フローを 4 つのテーブル
（``tasks`` / ``task_assigned_agents`` / ``deliverables`` /
``deliverable_attachments``）に対して実装する:

1. ``DELETE FROM deliverables WHERE task_id = :id`` — CASCADE で
   ``deliverable_attachments`` も自動削除される。
2. ``DELETE FROM task_assigned_agents WHERE task_id = :id`` — CASCADE 無し、直接 DELETE。
3. ``tasks`` UPSERT（id 衝突時に ``current_stage_id`` + ``status`` + ``last_error``
   + ``updated_at`` を更新。``room_id``、``directive_id``、``created_at`` は意図的に
   **更新しない** — Task の所有権と起源は作成後に変化しない）。
4. ``INSERT INTO task_assigned_agents`` — AgentId ごとに 1 行、``order_index`` は
   リスト位置（0 始まり）。
5. ``INSERT INTO deliverables`` — ``task.deliverables.values()`` の Deliverable
   ごとに 1 行。保存ごとに各行で新しい ``uuid4()`` PK を生成する（DELETE-then-INSERT
   パターンが PK 衝突しないことを保証する）。
6. ``INSERT INTO deliverable_attachments`` — Deliverable ごとの Attachment 1 つに対し
   1 行。step 5 で生成した ``deliverable_id`` FK でリンクされる。

``conversations`` / ``conversation_messages`` テーブルはこのフローから除外
（§BUG-TR-002 凍結済み）: Task Aggregate には現状 ``conversations`` 属性が無い。
これらのテーブルは ``Task.conversations: list[Conversation]`` を導入する将来 PR
で追加される。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、6 ステップ全てを
1 トランザクションに収める（empire-repo §確定 B Tx 境界の責務分離）。

``save(task)`` は **標準の 1 引数パターン**（§確定 R1-F）を使う:
:class:`Task` は ``room_id`` と ``directive_id`` を自身の属性として保持するため、
リポジトリはそれらを直接読む。

``_to_rows`` / ``_from_rows`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（empire-repo §確定 C）。

TypeDecorator-trust パターン（PR #48 v2 で確立）: :class:`UUIDStr` は
``process_result_value`` で ``UUID`` インスタンスを返すため、``row.id`` 等は
すでに ``UUID`` である。防御的な ``UUID(row.id)`` ラッピング無しで属性を直接
参照するのが正しく、必須である（§確定 R1-A）。
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import (
    Attachment,
    Deliverable,
    RoomId,
    StageId,
    TaskId,
    TaskStatus,
)
from bakufu.infrastructure.persistence.sqlite.tables.deliverable_attachments import (
    DeliverableAttachmentRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.deliverables import DeliverableRow
from bakufu.infrastructure.persistence.sqlite.tables.task_assigned_agents import (
    TaskAssignedAgentRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.tasks import TaskRow


class SqliteTaskRepository:
    """:class:`TaskRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, task_id: TaskId) -> Task | None:
        """tasks 行と 3 つの子テーブルを SELECT し、:meth:`_from_rows` で水和する。

        tasks 行が存在しない場合は ``None`` を返す。成功時は §確定 R1-H の ORDER BY
        句で 3 つの子テーブル全てを問い合わせるため、水和された Aggregate は決定的になる。
        """
        task_row = (
            await self._session.execute(select(TaskRow).where(TaskRow.id == task_id))
        ).scalar_one_or_none()
        if task_row is None:
            return None

        # §確定 R1-H: ORDER BY order_index ASC により、Aggregate の
        # ``assigned_agent_ids`` から得たアサイン エージェント リスト順を保つ。
        agent_rows = list(
            (
                await self._session.execute(
                    select(TaskAssignedAgentRow)
                    .where(TaskAssignedAgentRow.task_id == task_id)
                    .order_by(TaskAssignedAgentRow.order_index.asc())
                )
            )
            .scalars()
            .all()
        )

        # §確定 R1-H: ORDER BY stage_id ASC（task ごとに UNIQUE で決定的）。
        deliv_rows = list(
            (
                await self._session.execute(
                    select(DeliverableRow)
                    .where(DeliverableRow.task_id == task_id)
                    .order_by(DeliverableRow.stage_id.asc())
                )
            )
            .scalars()
            .all()
        )

        # §確定 R1-H: 全 attachment を 1 クエリで取得し、deliverable_id でグルーピング。
        # ORDER BY sha256 ASC（deliverable スコープで UNIQUE で決定的）。
        attach_rows_by_deliv: dict[UUID, list[DeliverableAttachmentRow]] = {}
        if deliv_rows:
            deliv_ids = [r.id for r in deliv_rows]
            for row in (
                await self._session.execute(
                    select(DeliverableAttachmentRow)
                    .where(DeliverableAttachmentRow.deliverable_id.in_(deliv_ids))
                    .order_by(DeliverableAttachmentRow.sha256.asc())
                )
            ).scalars():
                attach_rows_by_deliv.setdefault(row.deliverable_id, []).append(row)

        return self._from_rows(task_row, agent_rows, deliv_rows, attach_rows_by_deliv)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM tasks``。

        SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を発行するため、
        SQLite は全 PK を Python にストリームせずスカラー 1 行だけ返す
        （empire-repo §確定 D 踏襲）。
        """
        return (await self._session.execute(select(func.count()).select_from(TaskRow))).scalar_one()

    async def save(self, task: Task) -> None:
        """§確定 R1-B の 6 ステップ delete-then-insert で ``task`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。失敗はそのまま
        伝播するため、アプリケーション サービスの Unit-of-Work 境界はクリーンに
        ロールバックできる（empire-repo §確定 B 踏襲）。
        """
        task_row, agent_rows, deliv_rows, attach_rows = self._to_rows(task)

        # Step 1: DELETE deliverables — CASCADE で deliverable_attachments も削除。
        await self._session.execute(delete(DeliverableRow).where(DeliverableRow.task_id == task.id))

        # Step 2: DELETE task_assigned_agents（CASCADE 無し、直接 DELETE）。
        await self._session.execute(
            delete(TaskAssignedAgentRow).where(TaskAssignedAgentRow.task_id == task.id)
        )

        # Step 3: tasks UPSERT。
        # room_id / directive_id / created_at は DO UPDATE から除外 — Task の所有権と
        # 起源は作成後に不変。
        upsert_stmt = sqlite_insert(TaskRow).values(task_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "current_stage_id": upsert_stmt.excluded.current_stage_id,
                "status": upsert_stmt.excluded.status,
                "last_error": upsert_stmt.excluded.last_error,
                "updated_at": upsert_stmt.excluded.updated_at,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 4: INSERT task_assigned_agents。
        if agent_rows:
            await self._session.execute(insert(TaskAssignedAgentRow), agent_rows)

        # Step 5: INSERT deliverables。
        if deliv_rows:
            await self._session.execute(insert(DeliverableRow), deliv_rows)

        # Step 6: INSERT deliverable_attachments。
        if attach_rows:
            await self._session.execute(insert(DeliverableAttachmentRow), attach_rows)

    async def count_by_status(self, status: TaskStatus) -> int:
        """``SELECT COUNT(*) FROM tasks WHERE status = :status``。

        複合 INDEX ``ix_tasks_status_updated_id`` の ``(status)`` プレフィックスが
        この WHERE フィルタを高速化する（§確定 R1-K）。指定 status の Task が
        存在しない場合は 0 を返す。
        """
        return (
            await self._session.execute(
                select(func.count()).select_from(TaskRow).where(TaskRow.status == status.value)
            )
        ).scalar_one()

    async def count_by_room(self, room_id: RoomId) -> int:
        """``SELECT COUNT(*) FROM tasks WHERE room_id = :room_id``。

        INDEX ``ix_tasks_room_id`` がこの WHERE フィルタを高速化する（§確定 R1-K）。
        指定 Room の Task が存在しない場合は 0 を返す。
        """
        return (
            await self._session.execute(
                select(func.count()).select_from(TaskRow).where(TaskRow.room_id == room_id)
            )
        ).scalar_one()

    async def find_blocked(self) -> list[Task]:
        """``updated_at DESC, id DESC`` 順で全 BLOCKED Task を返す。

        ``(status, updated_at, id)`` 上の複合 INDEX ``ix_tasks_status_updated_id``
        は WHERE フィルタと ORDER BY の両方を 1 回の B-tree スキャンでカバーする
        （§確定 R1-K）。各 BLOCKED TaskRow について子テーブルを個別に取得する —
        :meth:`find_by_id` と同じパターン。

        BLOCKED Task が存在しない場合は ``[]`` を返す。
        """
        task_rows = list(
            (
                await self._session.execute(
                    select(TaskRow)
                    .where(TaskRow.status == TaskStatus.BLOCKED.value)
                    .order_by(TaskRow.updated_at.desc(), TaskRow.id.desc())
                )
            )
            .scalars()
            .all()
        )
        if not task_rows:
            return []

        results: list[Task] = []
        for task_row in task_rows:
            task = await self.find_by_id(task_row.id)
            if task is not None:
                results.append(task)
        return results

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------

    def _to_rows(
        self,
        task: Task,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """``task`` を ``(task_row, agent_rows, deliv_rows, attach_rows)`` に変換する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存しないよう、SQLAlchemy ``Row``
        オブジェクトは使わない。

        TypeDecorator-trust（§確定 R1-A）: 生のドメイン値を直接渡す。``UUIDStr`` /
        ``MaskedText`` / ``UTCDateTime`` の TypeDecorator がバインド パラメータ時点で
        全ての変換を行う。``last_error`` と ``body_markdown`` は素の文字列として渡す
        — ``MaskedText.process_bind_param`` が手動の ``MaskingGateway.mask()`` 呼び
        出し無しに自動的にマスキング ゲートを適用する。

        Deliverable の PK: ``deliverables.id`` はドメインレベルのアイデンティティを
        持たない（Aggregate は Deliverable を ``stage_id`` で識別する）。保存ごとに
        各 deliverable 行で新しい ``uuid4()`` を生成する。step 1→5 が
        DELETE-then-INSERT のため PK 衝突は起きない。同じ呼び出しで構築される対応する
        attachment 行の ``deliverable_id`` には同じ新規 UUID が使われる。

        ``conversations`` / ``conversation_messages`` 行は除外（§BUG-TR-002 凍結済み）:
        Task ドメインには現状 ``conversations`` 属性が無い。
        """
        task_row: dict[str, Any] = {
            "id": task.id,
            "room_id": task.room_id,
            "directive_id": task.directive_id,
            "current_stage_id": task.current_stage_id,
            "status": task.status.value,
            # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
            "last_error": task.last_error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

        agent_rows: list[dict[str, Any]] = [
            {
                "task_id": task.id,
                "agent_id": agent_id,
                "order_index": idx,
            }
            for idx, agent_id in enumerate(task.assigned_agent_ids)
        ]

        deliv_rows: list[dict[str, Any]] = []
        attach_rows: list[dict[str, Any]] = []

        for deliverable in task.deliverables.values():
            # 当該 deliverable の PK 用に新規 UUID を生成。同じ UUID をこの deliverable
            # に属する全 attachment 行の ``deliverable_id`` に再利用する — この save()
            # 呼び出し内でリンクを成立させる。
            deliv_pk = _uuid.uuid4()
            deliv_rows.append(
                {
                    "id": deliv_pk,
                    "task_id": task.id,
                    "stage_id": deliverable.stage_id,
                    # MaskedText.process_bind_param がバインド時にシークレットを伏字化する。
                    "body_markdown": deliverable.body_markdown,
                    "committed_by": deliverable.committed_by,
                    "committed_at": deliverable.committed_at,
                }
            )
            for attachment in deliverable.attachments:
                attach_rows.append(
                    {
                        "id": _uuid.uuid4(),
                        "deliverable_id": deliv_pk,
                        "sha256": attachment.sha256,
                        "filename": attachment.filename,
                        "mime_type": attachment.mime_type,
                        "size_bytes": attachment.size_bytes,
                    }
                )

        return task_row, agent_rows, deliv_rows, attach_rows

    def _from_rows(
        self,
        task_row: TaskRow,
        agent_rows: list[TaskAssignedAgentRow],
        deliv_rows: list[DeliverableRow],
        attach_rows_by_deliv: dict[UUID, list[DeliverableAttachmentRow]],
    ) -> Task:
        """行型から :class:`Task` Aggregate Root を水和する。

        ``Task.model_validate`` / 直接構築は post-validator を再実行するため、リポジトリ
        側の水和も ``TaskService.create()`` が構築時に走らせるのと同じ不変条件チェック
        を通る（empire §確定 C コントラクト「リポジトリ水和は妥当な Task を生成するか
        例外を送出する」）。

        TypeDecorator-trust（§確定 R1-A）: ``UUIDStr`` は ``process_result_value`` で
        ``UUID`` インスタンスを返し、``UTCDateTime`` は tz-aware ``datetime`` を返し、
        ``MaskedText`` は伏字化済みの文字列を返す。``UUID(row.id)`` のような防御的
        ラッピングは不要。

        §確定 R1-J §不可逆性: ``last_error`` と deliverable の ``body_markdown`` は
        ディスクから既に伏字化されたテキストを保持する。両フィールドは長さ上限内の
        任意の文字列を受理するため伏字化された形でも構築は通る。LLM へのディスパッチ
        は独自の masked-prompt ガードを適用する必要がある（``feature/llm-adapter`` 範囲）。
        """
        # §確定 R1-H: agent_rows は呼び元側で order_index ASC でソート済み。
        assigned_agent_ids = [row.agent_id for row in agent_rows]

        # §確定 R1-J: StageId をキーとした deliverables 辞書を再構築する。
        # deliv_rows は呼び元側で stage_id ASC でソート済み。
        deliverables: dict[StageId, Deliverable] = {}
        for deliv_row in deliv_rows:
            stage_id: StageId = deliv_row.stage_id
            attachments = [
                Attachment(
                    sha256=att.sha256,
                    filename=att.filename,
                    mime_type=att.mime_type,
                    size_bytes=att.size_bytes,
                )
                for att in attach_rows_by_deliv.get(deliv_row.id, [])
            ]
            deliverables[stage_id] = Deliverable(
                stage_id=deliv_row.stage_id,
                body_markdown=deliv_row.body_markdown,
                attachments=attachments,
                committed_by=deliv_row.committed_by,
                committed_at=deliv_row.committed_at,
            )

        return Task(
            id=task_row.id,
            room_id=task_row.room_id,
            directive_id=task_row.directive_id,
            current_stage_id=task_row.current_stage_id,
            status=TaskStatus(task_row.status),
            last_error=task_row.last_error,
            assigned_agent_ids=assigned_agent_ids,
            deliverables=deliverables,
            created_at=task_row.created_at,
            updated_at=task_row.updated_at,
        )


__all__ = ["SqliteTaskRepository"]
