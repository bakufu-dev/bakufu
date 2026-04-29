""":class:`bakufu.application.ports.WorkflowRepository` の SQLite アダプタ。

§確定 B の "delete-then-insert" 保存フローを 3 つのテーブル
（``workflows`` / ``workflow_stages`` / ``workflow_transitions``）に対して実装する:

1. ``workflows`` UPSERT（id 衝突時に name + entry_stage_id を更新）
2. ``workflow_stages`` DELETE WHERE workflow_id = ?
3. ``workflow_stages`` 一括 INSERT（Stage ごとに 1 行。``notify_channels_json`` は
   :class:`MaskedJSONEncoded` 経由でバインドされるため、Discord の Webhook トークンは
   JSON が ディスクに到達する *前* に伏字化される — Schneier 申し送り #6 多層防御を
   Workflow 経路にも適用）。
4. ``workflow_transitions`` DELETE WHERE workflow_id = ?
5. ``workflow_transitions`` 一括 INSERT（Transition ごとに 1 行）。

リポジトリは ``session.commit()`` / ``session.rollback()`` を **決して** 呼ばない。
呼び元のサービスが ``async with session.begin():`` を実行することで、上記 5 ステップ
を 1 トランザクションに収める（§確定 B Tx 境界の責務分離）。
:class:`SqliteEmpireRepository` と同じ Unit-of-Work パターン。

``_to_row`` / ``_from_row`` はクラスのプライベートメソッドのまま保持し、双方向の
変換が隣接して存在するようにする。これにより、テストが公開された変換 API を誤って
取得して依存することを避ける（§確定 C）。2 つのヘルパは §確定 G〜J で凍結された
4 つのフォーマット選択もカプセル化する:

* ``roles_csv`` — ``frozenset[Role]`` のソート CSV シリアライズ（§確定 G）。
  ソートは **必須**。frozenset の実装依存な反復順により、実行ごとに
  delete-then-insert の差分ノイズが発生するのを防ぐ。
* ``notify_channels_json`` — :class:`MaskedJSONEncoded`（§確定 H）。基底の
  TypeDecorator が伏字化を行う。``_to_row`` は ``NotifyChannel.model_dump(mode='json')``
  が生成した ``list[dict]`` を渡すだけ（VO の ``when_used='json'`` シリアライザ
  自体も伏字化を行う — 多層防御）。
* ``completion_policy_json`` — 通常の :class:`JSONEncoded`（§確定 I）。
  CompletionPolicy は Schneier #6 のシークレット カテゴリを持たないため、
  ``MaskedJSONEncoded`` だと過剰マスキングになる。CI の Layer 2 アーキテクチャ
  テストが非マスキング TypeDecorator を固定する。
* ``workflows.entry_stage_id`` — DB レベルの FK は持たない（§確定 J）。
  Aggregate 不変条件 ``_validate_entry_in_stages`` が責任を持つ。

``_from_row`` は ``Workflow.model_validate(...)`` を実行する。これにより、
アプリケーション層が構築時に強制する不変条件と同じものが、再水和（rehydration）時
にも発火する。したがって ``find_by_id`` は、保存時に Notify URL が伏字化された
``EXTERNAL_REVIEW`` ステージを含む Workflow を読み込んだ際に ``pydantic.ValidationError``
を送出する可能性がある（§確定 H §不可逆性）。アプリケーション層がこれを捕捉し、
オペレータに「Webhook の再登録が必要」エラーとして表面化する。
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.value_objects import (
    CompletionPolicy,
    NotifyChannel,
    Role,
    StageKind,
    TransitionCondition,
    WorkflowId,
)
from bakufu.domain.workflow import Stage, Transition, Workflow
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_transitions import (
    WorkflowTransitionRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow


class SqliteWorkflowRepository:
    """:class:`WorkflowRepository` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, workflow_id: WorkflowId) -> Workflow | None:
        """workflow と関連テーブルを SELECT し、:meth:`_from_row` で水和する。

        workflows 行が存在しない場合は ``None`` を返す。関連テーブルの SELECT は
        ``ORDER BY stage_id`` / ``ORDER BY transition_id`` を使い、水和されたリスト
        が決定的になるようにする — empire-repository BUG-EMR-001 が凍結したコントラクト
        を本 PR の最初から適用する。
        """
        workflow_stmt = select(WorkflowRow).where(WorkflowRow.id == workflow_id)
        workflow_row = (await self._session.execute(workflow_stmt)).scalar_one_or_none()
        if workflow_row is None:
            return None

        # ORDER BY を付与することで find_by_id を決定的にする。これがないと SQLite は
        # 内部スキャン順で行を返し、``Workflow == Workflow`` の往復等価性が壊れる
        # （Aggregate はリスト同士で比較する）。basic-design §ユースケース 2 と
        # docs/features/empire-repository/detailed-design.md §Known Issues §BUG-EMR-001
        # 参照 — 本 PR では当初から決定の済んだコントラクトを採用する。
        stage_stmt = (
            select(WorkflowStageRow)
            .where(WorkflowStageRow.workflow_id == workflow_id)
            .order_by(WorkflowStageRow.stage_id)
        )
        stage_rows = list((await self._session.execute(stage_stmt)).scalars().all())

        transition_stmt = (
            select(WorkflowTransitionRow)
            .where(WorkflowTransitionRow.workflow_id == workflow_id)
            .order_by(WorkflowTransitionRow.transition_id)
        )
        transition_rows = list((await self._session.execute(transition_stmt)).scalars().all())

        return self._from_row(workflow_row, stage_rows, transition_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM workflows``。

        実装詳細: SQLAlchemy の ``func.count()`` は適切な ``SELECT COUNT(*)`` を
        発行するため、SQLite は全 PK を Python にストリームせずスカラー 1 行だけ
        返す。これは empire-repository §確定 D 補強コントラクトの継続である —
        Stage / Transition / Workflow テーブルはプリセット ライブラリが入ると
        数百行を保持し得るため、このパターンが効いてくる。
        """
        stmt = select(func.count()).select_from(WorkflowRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, workflow: Workflow) -> None:
        """§確定 B の 5 ステップ delete-then-insert で ``workflow`` を永続化する。

        外側の ``async with session.begin():`` ブロックは呼び元の責任。各ステップ
        内部の失敗はそのまま伝播するため、アプリケーション サービスの Unit-of-Work
        境界はクリーンにロールバックできる。
        """
        workflow_row, stage_rows, transition_rows = self._to_row(workflow)

        # Step 1: workflows UPSERT（id PK、ON CONFLICT で name + entry_stage_id を更新）。
        # entry_stage_id は、オペレータが DAG の先頭に新しい entry stage を挿入する
        # 際に変化し得る。
        upsert_stmt = sqlite_insert(WorkflowRow).values(workflow_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": upsert_stmt.excluded.name,
                "entry_stage_id": upsert_stmt.excluded.entry_stage_id,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: workflow_stages DELETE。
        await self._session.execute(
            delete(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
        )

        # Step 3: workflow_stages 一括 INSERT（stages が無い場合はスキップ —
        # Workflow のキャパシティ バリデータは長さ 0 を禁止しているが、空チェックは
        # Empire テンプレートとの動作整合のために残す）。
        if stage_rows:
            await self._session.execute(insert(WorkflowStageRow), stage_rows)

        # Step 4: workflow_transitions DELETE。
        await self._session.execute(
            delete(WorkflowTransitionRow).where(WorkflowTransitionRow.workflow_id == workflow.id)
        )

        # Step 5: workflow_transitions 一括 INSERT（transitions が無い場合はスキップ —
        # 単一ステージの Workflow は有効）。
        if transition_rows:
            await self._session.execute(insert(WorkflowTransitionRow), transition_rows)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(
        self,
        workflow: Workflow,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """``workflow`` を ``(workflow_row, stage_rows, transition_rows)`` に分割する。

        ここでは SQLAlchemy の ``Row`` オブジェクトを意図的に使わない。これによって
        ドメイン層が SQLAlchemy の型階層に偶発的に依存することを防ぐ。返却される
        各 ``dict`` のキーは対応するテーブルの ``mapped_column`` 名と完全一致する。
        """
        workflow_row: dict[str, Any] = {
            "id": workflow.id,
            "name": workflow.name,
            "entry_stage_id": workflow.entry_stage_id,
        }
        stage_rows: list[dict[str, Any]] = [
            {
                "workflow_id": workflow.id,
                "stage_id": stage.id,
                "name": stage.name,
                "kind": stage.kind.value,
                # §確定 G: ソート済み CSV。``sorted(..., key=str)`` により Python の
                # frozenset がどんな順序で反復しようとバイト等価性のコントラクトを保つ。
                "roles_csv": ",".join(sorted(role.value for role in stage.required_role)),
                "deliverable_template": stage.deliverable_template,
                # §確定 I: 通常の JSONEncoded。``model_dump(mode='json')`` は
                # ``{'kind': ..., 'description': ...}`` を返す。
                "completion_policy_json": stage.completion_policy.model_dump(mode="json"),
                # §確定 H: 伏字化されたターゲットを含む list[dict]。カラム型
                # :class:`MaskedJSONEncoded` がバインド値に対して再度 ``mask_in`` を
                # 実行するため、仮に ``when_used='json'`` を素通りした生 URL があっても
                # ``json.dumps`` の前にゲートウェイで伏字化される（BUG-PF-001 双子防御）。
                "notify_channels_json": [
                    channel.model_dump(mode="json") for channel in stage.notify_channels
                ],
            }
            for stage in workflow.stages
        ]
        transition_rows: list[dict[str, Any]] = [
            {
                "workflow_id": workflow.id,
                "transition_id": transition.id,
                "from_stage_id": transition.from_stage_id,
                "to_stage_id": transition.to_stage_id,
                "condition": transition.condition.value,
                "label": transition.label,
            }
            for transition in workflow.transitions
        ]
        return workflow_row, stage_rows, transition_rows

    def _from_row(
        self,
        workflow_row: WorkflowRow,
        stage_rows: list[WorkflowStageRow],
        transition_rows: list[WorkflowTransitionRow],
    ) -> Workflow:
        """3 つの行から :class:`Workflow` Aggregate Root を水和する。

        ``Workflow.model_validate`` は post-validator を再実行するため、リポジトリ
        側の水和もアプリケーション サービスが構築時に走らせるのと同じ不変条件
        チェックを通る（Empire §確定 C）。``EXTERNAL_REVIEW`` ステージの notify
        channels を持つ Workflow の水和は ``pydantic.ValidationError`` を送出する —
        永続化されたターゲットが伏字化されているため。これは §確定 H §不可逆性
        による設計上のコントラクト。
        """
        stages = [self._stage_from_row(row) for row in stage_rows]
        transitions = [self._transition_from_row(row) for row in transition_rows]
        return Workflow(
            id=_uuid(workflow_row.id),
            name=workflow_row.name,
            stages=stages,
            transitions=transitions,
            entry_stage_id=_uuid(workflow_row.entry_stage_id),
        )

    @staticmethod
    def _stage_from_row(row: WorkflowStageRow) -> Stage:
        """永続化された行から ``Stage`` を 1 つ水和する。"""
        # §確定 G: CSV を split → 集合内包 → frozenset。``required_role`` が空に
        # なることはない（保存カラムが NOT NULL であり、Workflow キャパシティ
        # 不変条件が保存時に拒否する）。万一壊れた行をすり抜けた場合、``Role(s)``
        # が ``ValueError`` を送出し、Aggregate の StageInvariantViolation 経路が
        # ダウンストリームで引き継ぐ（Fail-Fast）。
        roles = frozenset(Role(token) for token in row.roles_csv.split(","))
        completion_policy = CompletionPolicy.model_validate(row.completion_policy_json)
        # §確定 H §不可逆性: NotifyChannel.model_validate は、保存時に ``target``
        # フィールドが伏字化されているため例外を送出することがある。例外が
        # find_by_id から漏れ出るのは意図的。
        notify_payloads = cast(
            "list[dict[str, Any]]",
            row.notify_channels_json or [],
        )
        notify_channels = [NotifyChannel.model_validate(payload) for payload in notify_payloads]
        return Stage(
            id=_uuid(row.stage_id),
            name=row.name,
            kind=StageKind(row.kind),
            required_role=roles,
            deliverable_template=row.deliverable_template,
            completion_policy=completion_policy,
            notify_channels=notify_channels,
        )

    @staticmethod
    def _transition_from_row(row: WorkflowTransitionRow) -> Transition:
        """永続化された行から ``Transition`` を 1 つ水和する。"""
        return Transition(
            id=_uuid(row.transition_id),
            from_stage_id=_uuid(row.from_stage_id),
            to_stage_id=_uuid(row.to_stage_id),
            condition=TransitionCondition(row.condition),
            label=row.label,
        )


def _uuid(value: UUID | str) -> UUID:
    """行の値を :class:`uuid.UUID` に強制変換する。

    SQLAlchemy の UUIDStr TypeDecorator は ``process_result_value`` で既に ``UUID``
    インスタンスを返すが、防御的な強制変換により、raw SQL 経路の水和も同じコードを
    通せる — 各呼び出し箇所で ``isinstance`` の階段を書かずに済む。
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


__all__ = ["SqliteWorkflowRepository"]
