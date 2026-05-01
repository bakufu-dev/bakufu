"""DeliverableTemplate Repository ポート。

empire-repository §確定 A に従う:

* Protocol クラスに ``@runtime_checkable`` デコレータを **付けない** —
  Python 3.12 の ``typing.Protocol`` ダックタイピングで十分。
* すべてのメソッドを ``async def`` で宣言（async-first 契約）。
* 引数および戻り値の型は :mod:`bakufu.domain` 由来のもののみ —
  SQLAlchemy 型がポートを越えて漏れることはない。
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.deliverable_template import DeliverableTemplate
from bakufu.domain.value_objects import DeliverableTemplateId


class DeliverableTemplateRepository(Protocol):
    """:class:`DeliverableTemplate` Aggregate Root の永続化契約。

    application 層が依存性注入により本 Protocol を消費する。
    SQLite 実装は
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository`
    に存在する。
    """

    async def find_by_id(self, template_id: DeliverableTemplateId) -> DeliverableTemplate | None:
        """主キーが ``template_id`` の DeliverableTemplate をハイドレートする。

        該当行がない場合は ``None`` を返す。SQLAlchemy / ドライバの例外は
        そのまま伝播させ、application service の Unit-of-Work 境界がロールバックと
        エラー表出のいずれを取るかを判断できるようにする。
        """
        ...

    async def find_all(self) -> list[DeliverableTemplate]:
        """全 DeliverableTemplate 行を ``ORDER BY name ASC`` で返す（§確定 I）。

        0 件の場合は空リストを返す。決定論的な順序は
        empire-repository §BUG-EMR-001 コントラクトを踏襲する。
        """
        ...

    async def save(self, template: DeliverableTemplate) -> None:
        """``deliverable_templates`` 1 テーブルへの UPSERT で永続化する（§確定 B）。

        子テーブルなし — acceptance_criteria / composition は JSONEncoded カラムに
        シリアライズ済み。Repository は ``session.commit()`` / ``session.rollback()``
        を決して呼ばない。Unit-of-Work 境界の保有は application service の責務。
        """
        ...

    async def delete(self, template_id: DeliverableTemplateId) -> None:
        """``DELETE FROM deliverable_templates WHERE id = :id``（§確定 E）。

        対象行が存在しない場合は何もしない（no-op）。Service 層で事前に
        ``find_by_id`` による存在確認を行う設計のため、Repository 側では
        silent no-op を許容する。
        """
        ...


__all__ = ["DeliverableTemplateRepository"]
