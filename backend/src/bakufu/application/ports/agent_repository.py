"""Agent Repository ポート。

``docs/features/agent-repository/detailed-design.md`` §確定 A
（empire-repo / workflow-repo テンプレート 100% 継承）および §確定 F
（``find_by_name`` を第 4 メソッドとして追加 — 標準 3 メソッド面を拡張する
コードベース上 **最初** の Repository）に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない** —
  Python 3.12 の ``typing.Protocol`` ダックタイピングで十分。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポートを越えて漏れることはない。
* ``find_by_name`` は ``empire_id`` を第 1 引数に取る。「名前は Empire 内で一意」
  という不変条件が Empire スコープのため（§確定 F (a) でグローバルスコープ案は
  却下）。引数順は **スコープ → 識別子** が自然な読み方となる。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.agent import Agent
from bakufu.domain.value_objects import AgentId, EmpireId


class AgentRepository(Protocol):
    """:class:`Agent` Aggregate Root の永続化契約。

    application 層（``AgentService.hire`` 等、将来 PR）が依存性注入により本
    Protocol を消費する。SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.agent_repository`
    に存在する。
    """

    async def find_by_id(self, agent_id: AgentId) -> Agent | None:
        """主キーが ``agent_id`` の Agent をハイドレートする。

        該当行がない場合は ``None`` を返す。SQLAlchemy / ドライバ /
        ``pydantic.ValidationError`` 例外はそのまま伝播させ、application service の
        Unit-of-Work 境界がロールバックとエラー表出のいずれを取るかを判断できるように
        する。
        """
        ...

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM agents`` を返す。

        application service は本メソッドを一括イントロスペクション
        （例: 監視ダッシュボード）に用いる。カウントが何を意味するかを判断するのは
        application 層の役割（§確定 D）。
        """
        ...

    async def save(self, agent: Agent) -> None:
        """§確定 B の delete-then-insert フローで ``agent`` を永続化する。

        実装は **呼び出し元が管理する** トランザクション内で 5 段階のシーケンス
        （UPSERT agents → DELETE agent_providers → bulk INSERT providers →
        DELETE agent_skills → bulk INSERT skills）を実行しなければならない。
        Repository は ``session.commit()`` / ``session.rollback()`` を決して
        呼び出さない。Unit-of-Work 境界の保有は application service の責務である。
        """
        ...

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Agent | None:
        """Empire ``empire_id`` 内で ``name`` という名前の Agent をハイドレートする（§確定 F）。

        「名前は Empire 内で一意」という不変条件は Empire スコープであり
        （``docs/features/agent/detailed-design.md`` 参照）、Repository は
        ``empire_id`` を第 1 引数に取る。実装は全 Agent を取得して Python 側で
        フィルタするのではなく、必ず ``WHERE empire_id = :empire_id AND name = :name LIMIT 1``
        を発行しなければならない（後者はメモリ / N+1 落とし穴として §確定 F (c) で
        明示的に却下されている）。

        該当する Agent がない場合は ``None`` を返す。実装は AgentId が判明した時点で
        サイドテーブルの SELECT を :meth:`find_by_id` に委譲し、``_to_row`` /
        ``_from_row`` 変換ロジックの重複を避けることが期待される（§設計判断補足）。
        """
        ...

    async def find_all_by_empire(self, empire_id: EmpireId) -> list[Agent]:
        """Empire ``empire_id`` 内の全 Agent を返す（前提条件 P-1 / §確定 D）。

        0 件の場合は空リストを返す。アーカイブ済み Agent も含む。
        SQL: ``SELECT ... FROM agents WHERE empire_id = :empire_id ORDER BY name``
        で全行を取得し、各行に対して provider / skill 子テーブルを JOIN して
        Agent を復元する。
        """
        ...


__all__ = ["AgentRepository"]
