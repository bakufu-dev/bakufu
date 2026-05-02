"""InternalReviewGate Repository ポート。

``INTERNAL_REVIEW`` Stage の Gate 管理クエリに従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない**
  （empire-repo §確定 A: Python 3.12 の ``typing.Protocol`` ダックタイピングで十分）。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポート境界を越えることはない。
* ``save`` のシグネチャは ``save(gate: InternalReviewGate) -> None``
  （標準 1 引数パターン）。:class:`InternalReviewGate` がすべての属性を保持するため、
  Repository が直接読み取る。
* ``find_by_task_and_stage`` は PENDING Gate のみを返す（設計書§確定E:
  ``WHERE gate_decision='PENDING' LIMIT 1`` — Stage につき高々 1 件の PENDING Gate
  が存在するという不変条件に依拠する）。
* ``find_all_by_task_id`` は ``created_at ASC`` 順でレビュー履歴を返す。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import InternalGateId, StageId, TaskId


class InternalReviewGateRepository(Protocol):
    """:class:`InternalReviewGate` Aggregate Root の永続化契約。

    application 層（``InternalReviewGateService``）が依存性注入により本 Protocol を
    消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository`
    に存在する。
    """

    async def find_by_id(self, gate_id: InternalGateId) -> InternalReviewGate | None:
        """主キーが ``gate_id`` の Gate をハイドレートする。

        該当行がない場合は ``None`` を返す。子テーブル
        （internal_review_gate_verdicts）がフェッチされ、ハイドレートされた Gate
        に含まれる。SQLAlchemy / ドライバ / ``pydantic.ValidationError`` 例外は
        そのまま伝播させ、application service の Unit-of-Work 境界がロールバックと
        エラー表出のいずれを取るかを判断できるようにする。
        """
        ...

    async def find_by_task_and_stage(
        self, task_id: TaskId, stage_id: StageId
    ) -> InternalReviewGate | None:
        """``task_id`` かつ ``stage_id`` の PENDING Gate を返す（設計書§確定E）。

        ``WHERE gate_decision='PENDING' LIMIT 1`` で取得する — Stage につき高々 1 件
        の PENDING Gate が存在するという Aggregate 不変条件に依拠する。
        PENDING Gate が存在しない場合は ``None`` を返す。

        application service は本メソッドを「Stage 遷移のブロックゲートを検出」する
        ために用いる。
        """
        ...

    async def find_all_by_task_id(self, task_id: TaskId) -> list[InternalReviewGate]:
        """``task_id`` の全 Gate を ``created_at ASC`` の順で返す。

        application service が Task の完全な内部レビュー履歴を取得するために用いる。
        該当 Task に Gate が存在しない場合は ``[]`` を返す。

        ORDER BY ``created_at ASC`` — 古い gate が先に現れる「レビュー履歴」の
        読み取りパターンに合致する時系列順。
        """
        ...

    async def save(self, gate: InternalReviewGate) -> None:
        """delete-then-insert で ``gate`` を永続化する。

        save フローは 2 つのテーブルを対象とする:

        1. DELETE internal_review_gate_verdicts WHERE gate_id = :id
        2. UPSERT internal_review_gates（ON CONFLICT id DO UPDATE で可変フィールド更新）
        3. INSERT internal_review_gate_verdicts（verdicts タプル内の Verdict ごと）

        実装は ``session.commit()`` / ``session.rollback()`` を呼んではならない。
        Unit-of-Work 境界の保有は application service の責務である
        （empire-repo §確定 B 踏襲）。
        """
        ...


__all__ = ["InternalReviewGateRepository"]
