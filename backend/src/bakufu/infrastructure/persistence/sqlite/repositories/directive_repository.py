""":class:`bakufu.application.ports.DirectiveRepository` の SQLite アダプタ。

§確定 R1-B の単一テーブル UPSERT 保存フローを 1 つのテーブル（``directives``）
に対して実装する:

1. ``directives`` UPSERT（id 衝突時に ``text`` + ``created_at`` + ``task_id`` を
   更新。**``target_room_id`` は更新しない** — Directive の所有権は作成後に
   変化しない、§確定 R1-B）。``text`` は :class:`MaskedText` 経由でバインドされる
   ため、埋め込まれた API キー / OAuth トークン / Discord webhook シークレットは
   SQLite に到達する *前* に伏字化される — §確定 R1-E、§確定 R1-G 不可逆性凍結。

Directive は **子テーブルを持たない** フラットな Aggregate のため、
empire-repository の delete-then-insert パターンは DELETE ステップ無しの単一
UPSERT ステップに簡約される（§確定 R1-B 子テーブルなし版）。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで UPSERT を 1
トランザクションに収める（empire-repo §確定 B Tx 境界の責務分離）。

``save(directive)`` は **標準の 1 引数パターン**（§確定 R1-F）を使う:
:class:`Directive` は ``target_room_id`` を自身の属性として保持するため、リポジトリ
はそれを直接読む — 非対称な Room パターンは不要。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（empire-repo §確定 C）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.directive.directive import Directive
from bakufu.domain.value_objects import DirectiveId, RoomId
from bakufu.infrastructure.persistence.sqlite.tables.directives import DirectiveRow


class SqliteDirectiveRepository:
    """:class:`DirectiveRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, directive_id: DirectiveId) -> Directive | None:
        """directive 行を SELECT し、:meth:`_from_row` で水和する。

        directives 行が存在しない場合は ``None`` を返す。Directive はフラットな
        Aggregate — 子テーブル SELECT は不要。
        """
        stmt = select(DirectiveRow).where(DirectiveRow.id == directive_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._from_row(row)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM directives``。

        実装詳細: SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を
        発行するため、SQLite は全 PK を Python にストリームせずスカラー 1 行だけ
        返す（empire-repo §確定 D 踏襲）。
        """
        stmt = select(func.count()).select_from(DirectiveRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, directive: Directive) -> None:
        """§確定 R1-B の単一テーブル UPSERT で ``directive`` を永続化する。

        ON CONFLICT (id) DO UPDATE は ``text``、``created_at``、``task_id`` を
        セットする。``target_room_id`` は意図的に **更新しない** — Directive の
        所有権（target room）は作成後に変化しない。

        ``text`` は :class:`MaskedText` 経由でバインドされるため、UPDATE 時にも
        伏字化された形で DB に到達する（§確定 R1-E / R1-G）。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。失敗は
        そのまま伝播するため、アプリケーション サービスの Unit-of-Work 境界は
        クリーンにロールバックできる（empire-repo §確定 B 踏襲）。
        """
        row = self._to_row(directive)

        # 単一ステップ UPSERT: directives は子テーブルを持たない（§確定 R1-B）。
        # target_room_id は ON CONFLICT 更新セットから除外する。所有権は不変 —
        # Directive は常に同じ Room を対象とする。
        upsert_stmt = sqlite_insert(DirectiveRow).values(row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "text": upsert_stmt.excluded.text,
                "created_at": upsert_stmt.excluded.created_at,
                "task_id": upsert_stmt.excluded.task_id,
            },
        )
        await self._session.execute(upsert_stmt)

    async def find_by_room(self, room_id: RoomId) -> list[Directive]:
        """``room_id`` を対象とする全 Directive を新しい順で返す。

        ORDER BY ``created_at DESC, id DESC``（BUG-EMR-001 規約: 決定的順序付け
        のための複合キー）。``created_at`` 単独では複数 Directive が同じタイム
        スタンプを共有する場合に不十分で、``id``（PK、UUID）が結果を完全に決定的
        にする tiebreaker となる（§確定 R1-D）。

        Room に Directive が無い場合は ``[]`` を返す。
        """
        stmt = (
            select(DirectiveRow)
            .where(DirectiveRow.target_room_id == room_id)
            .order_by(DirectiveRow.created_at.desc(), DirectiveRow.id.desc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._from_row(row) for row in rows]

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------
    def _to_row(self, directive: Directive) -> dict[str, Any]:
        """``directive`` を ``directives`` テーブル行 dict に変換する。

        ドメイン層が SQLAlchemy の型階層に偶発的に依存しないよう、SQLAlchemy
        ``Row`` オブジェクトは使わない。返却される dict のキーは ``mapped_column``
        名と完全一致する。

        ``text`` は素の文字列として渡す — :class:`MaskedText`
        ``process_bind_param`` が SQLAlchemy のバインド パラメータ解決時に
        マスキング ゲートを自動適用する（§確定 R1-E 物理保証）。
        """
        return {
            "id": directive.id,
            "text": directive.text,
            "target_room_id": directive.target_room_id,
            "created_at": directive.created_at,
            "task_id": directive.task_id,
        }

    def _from_row(self, row: DirectiveRow) -> Directive:
        """行から :class:`Directive` Aggregate Root を水和する。

        ``Directive.model_validate`` は post-validator を再実行するため、リポジトリ
        側の水和も ``DirectiveService.issue()`` が構築時に走らせるのと同じ不変条件
        チェックを通る。コントラクト（empire §確定 C）は「リポジトリ水和は妥当な
        Directive を生成するか例外を送出する」。

        TypeDecorator-trust パターン（PR #48 v2 確立）: :class:`UUIDStr` は
        ``process_result_value`` で ``UUID`` インスタンスを返すため、``row.id`` /
        ``row.target_room_id`` / ``row.task_id`` は既に ``UUID``（または ``None``）。
        防御的な ``UUID(row.id)`` ラッピング無しで属性を直接参照するのが正しく、
        必須である（§確定 R1-G）。

        §確定 R1-G §不可逆性: ``text`` はディスクから既に伏字化されたテキストを
        保持する。``Directive`` は長さ上限内の任意の文字列を受理するため伏字化
        された形でも構築は通るが、生成された Directive は ``feature/llm-adapter``
        の masked-prompt ガード無しに LLM へディスパッチすべきではない。
        """
        return Directive(
            id=row.id,
            text=row.text,
            target_room_id=row.target_room_id,
            created_at=row.created_at,
            task_id=row.task_id,
        )


__all__ = ["SqliteDirectiveRepository"]
