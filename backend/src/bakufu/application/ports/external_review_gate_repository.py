"""ExternalReviewGate Repository ポート。

``docs/features/external-review-gate-repository/detailed-design.md`` §確定 R1-A
（empire-repo / workflow-repo / agent-repo / room-repo / directive-repo / task-repo
テンプレート 100% 継承）に加え、Gate 固有のクエリメソッドに従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない**
  （empire-repo §確定 A: Python 3.12 の ``typing.Protocol`` ダックタイピングで十分）。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポート境界を越えることはない。
* ``save`` のシグネチャは ``save(gate: ExternalReviewGate) -> None``
  （標準 1 引数パターン）。:class:`ExternalReviewGate` がすべての属性を保持するため、
  Repository が直接読み取る。
* empire-repo §確定 B のベースラインに加え、Gate 固有のクエリメソッドを 4 つ持つ
  （``find_pending_by_reviewer`` / ``find_by_task_id`` / ``count_by_decision``）。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import GateId, OwnerId, ReviewDecision, TaskId


class ExternalReviewGateRepository(Protocol):
    """:class:`ExternalReviewGate` Aggregate Root の永続化契約。

    application 層（``GateService``、将来 PR）が依存性注入により本 Protocol を
    消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository`
    に存在する。
    """

    async def find_by_id(self, gate_id: GateId) -> ExternalReviewGate | None:
        """主キーが ``gate_id`` の Gate をハイドレートする。

        該当行がない場合は ``None`` を返す。両方の子テーブル
        （external_review_gate_attachments / external_review_audit_entries）が
        フェッチされ、ハイドレートされた Gate に含まれる。SQLAlchemy / ドライバ /
        ``pydantic.ValidationError`` 例外はそのまま伝播させ、application service の
        Unit-of-Work 境界がロールバックとエラー表出のいずれを取るかを判断できるように
        する。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM external_review_gates`` を返す。

        decision や reviewer に関わらず、全 Gate を横断するグローバルカウント。
        application service は本メソッドを監視 / 一括イントロスペクションに用いる
        （empire-repo §確定 D 踏襲）。
        """
        ...

    async def save(self, gate: ExternalReviewGate) -> None:
        """§確定 R1-B の 5 段階 delete-then-insert で ``gate`` を永続化する。

        save フローは 3 つのテーブルすべてを対象とする:

        1. DELETE external_review_gate_attachments WHERE gate_id = :id
        2. DELETE external_review_audit_entries WHERE gate_id = :id
        3. UPSERT external_review_gates（ON CONFLICT id DO UPDATE で可変フィールド更新）
        4. INSERT external_review_gate_attachments（snapshot 内の Attachment ごと）
        5. INSERT external_review_audit_entries（audit_trail 内の AuditEntry ごと）

        実装は ``session.commit()`` / ``session.rollback()`` を呼んではならない。
        Unit-of-Work 境界の保有は application service の責務である
        （empire-repo §確定 B 踏襲）。
        """
        ...

    async def find_pending_by_reviewer(self, reviewer_id: OwnerId) -> list[ExternalReviewGate]:
        """``reviewer_id`` の全 PENDING Gate を ``created_at DESC, id DESC`` の順で返す。

        ``GateService`` が reviewer のオープンなレビューキューを表面化するために用いる。
        該当 reviewer に PENDING Gate が存在しない場合は ``[]`` を返す。

        ORDER BY ``created_at DESC, id DESC``（BUG-EMR-001 規約: 決定的な順序付けの
        ための複合キー — 複数の Gate が同一タイムスタンプを持つ場合 ``created_at``
        単独では不十分。``id``（PK、UUID）が tiebreaker として結果を完全に決定的にする）。
        """
        ...

    async def find_by_task_id(self, task_id: TaskId) -> list[ExternalReviewGate]:
        """``task_id`` の全 Gate を ``created_at ASC, id ASC`` の順で返す。

        ``GateService`` が Task の完全なレビュー履歴を取得するために用いる。
        該当 Task に Gate が存在しない場合は ``[]`` を返す。

        ORDER BY ``created_at ASC, id ASC`` — 古い gate が先に現れる「レビュー履歴」の
        読み取りパターンに合致する時系列順。
        """
        ...

    async def count_by_decision(self, decision: ReviewDecision) -> int:
        """``SELECT COUNT(*) FROM external_review_gates WHERE decision = :decision`` を返す。

        ダッシュボード指標（PENDING バックログサイズ、APPROVED / REJECTED /
        CANCELLED の履歴件数）に用いる。
        該当 decision の Gate が存在しない場合は 0 を返す。
        """
        ...


__all__ = ["ExternalReviewGateRepository"]
