"""Task Repository ポート。

``docs/features/task-repository/detailed-design.md`` §確定 R1-A
（empire-repo / workflow-repo / agent-repo / room-repo / directive-repo
テンプレート 100% 継承）に加え、§確定 R1-D（Task 固有メソッドの追加）に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない**
  （empire-repo §確定 A: Python 3.12 の ``typing.Protocol`` ダックタイピングで十分）。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポート境界を越えることはない。
* ``save`` のシグネチャは ``save(task: Task) -> None``（標準 1 引数パターン、
  §確定 R1-F）。:class:`Task` が ``room_id`` および ``directive_id`` を自身の属性として
  保持するため、Repository が直接読み取れる。
* §確定 R1-D に従い、empire-repo §確定 B のベースラインに加え Task 固有のクエリ
  メソッドを 3 つ持つ（``count_by_status`` / ``count_by_room`` / ``find_blocked``）。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import RoomId, TaskId, TaskStatus


class TaskRepository(Protocol):
    """:class:`Task` Aggregate Root の永続化契約。

    application 層（``TaskService``、将来 PR）が依存性注入により本 Protocol を
    消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.task_repository`
    に存在する。
    """

    async def find_by_id(self, task_id: TaskId) -> Task | None:
        """主キーが ``task_id`` の Task をハイドレートする。

        該当行がない場合は ``None`` を返す。5 つのすべての子テーブル
        （task_assigned_agents / conversations / conversation_messages /
        deliverables / deliverable_attachments）がフェッチされ、ハイドレートされた
        Task に含まれる。SQLAlchemy / ドライバ / ``pydantic.ValidationError`` 例外は
        そのまま伝播させ、application service の Unit-of-Work 境界がロールバックと
        エラー表出のいずれを取るかを判断できるようにする。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM tasks`` を返す。

        ステータスや room を問わず、全 Task を横断するグローバルカウント。
        application service は本メソッドを監視 / 一括イントロスペクションに用いる
        （empire-repo §確定 D 踏襲）。
        """
        ...

    async def save(self, task: Task) -> None:
        """§確定 R1-B の 9 段階 delete-then-insert で ``task`` を永続化する。

        save フローは 6 つのテーブルすべてを対象とする:
        1. DELETE deliverables（CASCADE で deliverable_attachments も削除）
        2. DELETE conversations（CASCADE で conversation_messages も削除）
        3. DELETE task_assigned_agents
        4. UPSERT tasks（ON CONFLICT id DO UPDATE）
        5. INSERT task_assigned_agents（AgentId ごと、order_index 付き）
        6. INSERT conversations（Conversation ごと）
        7. INSERT conversation_messages（Conversation 内の Message ごと）
        8. INSERT deliverables（Deliverable ごと）
        9. INSERT deliverable_attachments（Deliverable 内の Attachment ごと）

        実装は ``session.commit()`` / ``session.rollback()`` を呼んではならない。
        Unit-of-Work 境界の保有は application service の責務である
        （empire-repo §確定 B 踏襲）。
        """
        ...

    async def count_by_status(self, status: TaskStatus) -> int:
        """``SELECT COUNT(*) FROM tasks WHERE status = :status`` を返す。

        Room ダッシュボードのステータス集計や監視に用いる。
        該当 status の Task が存在しない場合は 0 を返す。
        """
        ...

    async def count_by_room(self, room_id: RoomId) -> int:
        """``SELECT COUNT(*) FROM tasks WHERE room_id = :room_id`` を返す。

        Room 詳細ページの Task 件数表示（HTTP API PR 後）に用いる。
        該当 Room に Task が存在しない場合は 0 を返す。
        """
        ...

    async def find_blocked(self) -> list[Task]:
        """全 BLOCKED Task を ``updated_at DESC, id DESC`` の順で返す。

        ``TaskService.find_blocked_tasks()``（Issue #38）の障害隔離に用いる —
        最近ブロックされた Task が先に現れることで、運用者が優先順位順にトリアージ
        できるようにする。

        ORDER BY ``updated_at DESC, id DESC``（BUG-EMR-001 規約: 決定的な順序付けの
        ための複合キー — 複数の Task が同一タイムスタンプを持つ場合 ``updated_at``
        単独では不十分。``id``（PK、UUID）が tiebreaker として結果を完全に決定的にする）。

        BLOCKED Task が存在しない場合は ``[]`` を返す。
        """
        ...


__all__ = ["TaskRepository"]
