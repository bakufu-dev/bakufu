"""Workflow Repository ポート。

``docs/features/workflow-repository/detailed-design.md`` §確定 A
（empire-repository テンプレート 100% 継承）に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない** —
  Python 3.12 の ``typing.Protocol`` ダックタイピングで十分。
  ``@runtime_checkable`` の実行時オーバーヘッドは、application 層が必要としない
  ``isinstance`` 経路を増やしてしまう
  （:mod:`bakufu.application.ports.empire_repository` をミラーリング）。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。これにより
  application 層は ``async with session.begin():`` の Unit-of-Work 内で
  Repository を組み合わせられる。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポートを越えて漏れることはない。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.value_objects import WorkflowId
from bakufu.domain.workflow import Workflow


class WorkflowRepository(Protocol):
    """:class:`Workflow` Aggregate Root の永続化契約。

    application 層（``WorkflowService``、将来 PR）が依存性注入により本 Protocol を
    消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository`
    に存在する。
    """

    async def find_by_id(self, workflow_id: WorkflowId) -> Workflow | None:
        """主キーが ``workflow_id`` の Workflow をハイドレートする。

        該当行がない場合は ``None`` を返す。実装は SQLAlchemy / ドライバ /
        ``pydantic.ValidationError`` 例外をそのまま伝播させ、application service の
        Unit-of-Work 境界がロールバックとエラー表出のいずれを取るかを判断できるように
        する。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM workflows`` を返す。

        application service は本メソッドを用いて Workflow が少なくとも 1 件
        登録されているかを内省する（例: プリセット bootstrap チェック）。
        カウントが何を意味するかを判断するのは *application* 層の役割である
        （§確定 D）。
        """
        ...

    async def save(self, workflow: Workflow) -> None:
        """§確定 B の delete-then-insert フローで ``workflow`` を永続化する。

        実装は **呼び出し元が管理する** トランザクション内で 5 段階のシーケンス
        （UPSERT workflows → DELETE workflow_stages → bulk INSERT stages →
        DELETE workflow_transitions → bulk INSERT transitions）を実行しなければ
        ならない。Repository は ``session.commit()`` / ``session.rollback()`` を
        決して呼び出さない。Unit-of-Work 境界の保有は application service の責務である。
        """
        ...


__all__ = ["WorkflowRepository"]
