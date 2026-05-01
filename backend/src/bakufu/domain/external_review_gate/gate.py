"""ExternalReviewGate Aggregate Root（REQ-GT-001〜007）。

``docs/features/external-review-gate/`` を M1 の 7 番目かつ最後の兄弟として実装する。
この Aggregate は empire / workflow / agent / room / directive / task で確立された
形を踏襲するが、**スコープがより絞り込まれている**: 4 メソッド × 4 decision 状態 =
16 セルのディスパッチ表で **7 ✓ 遷移 + 9 ✗ セル**。狭い表面は Gate の役割と一致する
— 単一の人間レビュー ラウンドを単一の Stage 結果に結び付け、その後固定する。

Gate のライフサイクル特有の構造要素は 2 つ:

* :mod:`bakufu.domain.external_review_gate.state_machine` 内の **decision-table
  state machine**。§確定 B により ``Final[Mapping]`` + :class:`types.MappingProxyType`
  でロックされる。
* §確定 A により state-machine テーブルのアクション名と 1:1 対応する **4 つの専用
  ビヘイビア メソッド**（task #42 §確定 A-2 が導入した Steve R2 凍結パターン）。

設計コントラクト（再設計レビュー無しに破壊しないこと）:

* **Pre-validate rebuild（§確定 E）** — 全ビヘイビアは :meth:`_rebuild_with_state`
  を呼び、``model_dump`` / ``swap`` / ``model_validate`` を経由する。
  ``model_copy(update=...)`` は意図的に避ける。
* **State-machine bypass Fail-Fast（§確定 A）** — 不正な ``(decision, action)`` 対は
  :class:`ExternalReviewGateInvariantViolation` を ``kind='decision_already_decided'``
  で送出するため、MSG-GT-001 が「Next:」ヒント込みで投入される（Gate は設計上
  単一決定）。
* **Snapshot immutable（§確定 D）** — :meth:`_rebuild_with_state` は
  ``deliverable_snapshot`` 引数を **受け取らない**。再構築のあらゆる経路は構築時の
  スナップショットをバイト単位で継承する。構造的な不在こそが偶発的な変異に対する
  最強の保証である。
* **Audit-trail append-only（§確定 C）** — 全ビヘイビアは末尾に厳密に 1 つの新しい
  :class:`AuditEntry` を追記する。:meth:`_rebuild_with_state` は再構築前に
  :func:`_validate_audit_trail_append_only` を旧 trail に対して実行するため、
  rebuild 経路が誤動作した場合は新インスタンス構築の *前* に
  ``audit_trail_append_only``（MSG-GT-005）が表面化する。
* **Webhook auto-mask（§確定 H）** —
  :class:`ExternalReviewGateInvariantViolation` は構築時に ``mask_discord_webhook`` /
  ``mask_discord_webhook_in`` を ``message`` / ``detail`` に適用するため、
  ``feedback_text`` に埋め込まれた webhook URL が例外ストリームから漏洩することは
  ない。
* **Aggregate boundary（§確定 J）** — Gate は Task / Workflow / Stage のメソッドを
  **import しない**。``GateService.approve()`` → ``task.approve_review(...)``
  （および対称な REJECTED / CANCELLED 経路）はアプリケーション層がディスパッチし、
  Gate は Task の内部に対して無知のままとなる。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Self
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.aggregate_validators import (
    _validate_audit_trail_append_only,
    _validate_criteria_immutable,
    _validate_decided_at_consistency,
    _validate_feedback_text_range,
    _validate_snapshot_immutable,
)
from bakufu.domain.external_review_gate.state_machine import (
    GateAction,
    allowed_actions_from,
    lookup,
)
from bakufu.domain.value_objects import (
    AcceptanceCriterion,
    AuditAction,
    AuditEntry,
    Deliverable,
    GateId,
    OwnerId,
    ReviewDecision,
    StageId,
    TaskId,
)


class ExternalReviewGate(BaseModel):
    """Task の Stage を Decision に結び付ける 1 つの人間レビュー チェックポイント。

    Gate は ``GateService.create()``（Task.request_external_review が発火した後）に
    よって PENDING で生成され、:meth:`record_view` で監査ビューを蓄積し、
    :meth:`approve` / :meth:`reject` / :meth:`cancel` のいずれか 1 つで終端する。
    終端状態でも :meth:`record_view` は許可される（決定済み Gate に対する監査読取は
    正当でありトラックする、§確定 G「誰がいつ何度見たか」）。

    Aggregate 外の関心事（Task / Stage / Owner 参照整合性、スナップショットの
    インライン コピー永続化、Gate-to-Task ディスパッチ）は §確定 J により
    ``GateService`` に置く。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: GateId
    task_id: TaskId
    stage_id: StageId
    deliverable_snapshot: Deliverable
    reviewer_id: OwnerId
    decision: ReviewDecision = ReviewDecision.PENDING
    feedback_text: str = ""
    audit_trail: list[AuditEntry] = []
    # required_deliverable_criteria: Gate 生成時に Stage.required_deliverables から
    # 引き込んだ AcceptanceCriterion snapshot（空タプル可）。§確定 D' criteria_immutable。
    required_deliverable_criteria: tuple[AcceptanceCriterion, ...] = ()
    created_at: datetime
    decided_at: datetime | None = None

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("created_at", mode="after")
    @classmethod
    def _require_created_at_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "ExternalReviewGate.created_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @field_validator("decided_at", mode="after")
    @classmethod
    def _require_decided_at_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "ExternalReviewGate.decided_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @field_validator("feedback_text", mode="before")
    @classmethod
    def _normalize_feedback_text(cls, value: object) -> object:
        """NFC のみの正規化（§確定 F）。

        ``strip`` は意図的に **適用しない** — CEO が書くレビュー コメントには
        インデント引用や複数段落の本文が含まれる場合があり、その先頭空白に
        意味を持たせている。``Persona.prompt_body`` /
        ``PromptKit.prefix_markdown`` / ``Directive.text`` /
        ``Task.last_error`` と同じ先例。
        """
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """構造的不変条件を実行する（§確定 J kinds 2 + 4）。

        ``decision_already_decided`` は state-machine ``lookup`` 経路で強制される
        （このバリデータより前に送出される）。``snapshot_immutable`` / ``criteria_immutable``
        は :meth:`_rebuild_with_state` が snapshot / criteria 引数を���理しないことで
        構造的に強制される。``audit_trail_append_only`` は :meth:`_rebuild_with_state`
        が新インスタンス構築前に旧 trail に対してバリデータを走らせて強制する。
        after-validator に残るのは、水和経路（リポジトリ往復）も満たさなければならない
        単一インスタンス不変条件のペア。
        """
        _validate_decided_at_consistency(self.decision, self.decided_at)
        _validate_feedback_text_range(self.feedback_text)
        return self

    # ---- 振る舞い（Tell, Don't Ask） -----------------------------------
    def approve(
        self,
        by_owner_id: OwnerId,
        comment: str,
        *,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING → APPROVED、``feedback_text`` と監査エントリを追加（REQ-GT-002）。

        ``by_owner_id`` は承認した人間を記録する。``decided_at`` 引数は明示的に取る
        （§設計判断補足「なぜ decided_at を引数で受け取るか」）ので Aggregate は
        time-pure に保たれ、テストは ``freezegun`` を必要としない。
        """
        next_decision = self._lookup_or_raise("approve")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.APPROVED,
            new_audit_actor=by_owner_id,
            new_audit_comment=comment,
            new_audit_at=decided_at,
            decision=next_decision,
            feedback_text=comment,
            decided_at=decided_at,
        )

    def reject(
        self,
        by_owner_id: OwnerId,
        comment: str,
        *,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING → REJECTED、``feedback_text`` と監査エントリを追加（REQ-GT-003）。

        :meth:`approve` と同形 — 違いは目的の ``decision``（REJECTED）と監査行の
        :class:`AuditAction` 識別子のみ。
        """
        next_decision = self._lookup_or_raise("reject")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.REJECTED,
            new_audit_actor=by_owner_id,
            new_audit_comment=comment,
            new_audit_at=decided_at,
            decision=next_decision,
            feedback_text=comment,
            decided_at=decided_at,
        )

    def cancel(
        self,
        by_owner_id: OwnerId,
        reason: str,
        *,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING → CANCELLED、``feedback_text`` と監査エントリを追加（REQ-GT-004）。

        ``reason`` は ``feedback_text``（アプリケーション層が Gate 取り下げ理由を
        表面化できるよう）と監査エントリの ``comment``（監査証跡が理由を記録できる
        よう）の両方に格納する。
        """
        next_decision = self._lookup_or_raise("cancel")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.CANCELLED,
            new_audit_actor=by_owner_id,
            new_audit_comment=reason,
            new_audit_at=decided_at,
            decision=next_decision,
            feedback_text=reason,
            decided_at=decided_at,
        )

    def record_view(
        self,
        by_owner_id: OwnerId,
        *,
        viewed_at: datetime,
    ) -> ExternalReviewGate:
        """VIEWED 監査エントリを追記。**全** decision 状態で許可（REQ-GT-005、§確定 G）。

        ``decision`` / ``decided_at`` / ``feedback_text`` は意図的に *更新しない* —
        record_view は純粋な監査操作。冪等性は **提供しない**（§確定 G「冪等性なし」）:
        同じ ``(by_owner_id, viewed_at)`` での 2 回の呼び出しは別個のエントリを 2 つ
        生成する。監査要件が「誰がいつ何度見たか」だからであり、重複を畳み込むと監査
        証跡が保持すべきシグナルそのものを破棄してしまう。
        """
        # State-machine ルックアップにより現在の decision からアクションが正当である
        # ことを確認する。結果は同じ値（self-loop）だが、呼び出し自体がコントラクトを
        # 文書化する。
        self._lookup_or_raise("record_view")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.VIEWED,
            new_audit_actor=by_owner_id,
            new_audit_comment="",
            new_audit_at=viewed_at,
        )

    # ---- 内部実装 -------------------------------------------------------
    def _lookup_or_raise(self, action: GateAction) -> ReviewDecision:
        """State-machine ルックアップ。``KeyError`` を MSG-GT-001 に翻訳する。

        (current_decision, action) ペアの ``next_decision`` を返す。PENDING 限定の
        4 つのアクション（``approve`` / ``reject`` / ``cancel``）は Gate が既に決定
        済みの場合ここで送出する — ルックアップ表に ``(APPROVED, 'approve')`` 等の
        行が単に存在しないため。
        """
        try:
            return lookup(self.decision, action)
        except KeyError as exc:
            allowed = list(allowed_actions_from(self.decision))
            raise ExternalReviewGateInvariantViolation(
                kind="decision_already_decided",
                message=(
                    f"[FAIL] Gate decision is already decided: "
                    f"gate_id={self.id}, current_decision={self.decision.value}\n"
                    f"Next: A Gate can only be decided once "
                    f"(PENDING -> APPROVED/REJECTED/CANCELLED); "
                    f"issue a new directive for re-review."
                ),
                detail={
                    "gate_id": str(self.id),
                    "current_decision": self.decision.value,
                    "attempted_action": action,
                    "allowed_actions": allowed,
                },
            ) from exc

    def _rebuild_with_state(
        self,
        *,
        new_audit_action: AuditAction,
        new_audit_actor: OwnerId,
        new_audit_comment: str,
        new_audit_at: datetime,
        decision: ReviewDecision | None = None,
        feedback_text: str | None = None,
        decided_at: datetime | None = None,
    ) -> ExternalReviewGate:
        """ビヘイビア出力のための pre-validate rebuild（§確定 E）。

        rebuild 経路は Gate の audit_trail / decision / feedback_text / decided_at
        フィールドを変異させる **唯一の** 合法経路である。``deliverable_snapshot``
        はキーワード専用引数リストから意図的に除外されているため、いかなる rebuild
        経路もこれを置き換えられない（§確定 D）。

        ステップ順:

        1. 新しい :class:`AuditEntry` を構築する — 全ビヘイビアは厳密に 1 エントリを
           追記するため、コンストラクタ呼出は各呼び出し箇所ではなくここに置く。
        2. ``new_audit_trail = self.audit_trail + [new]`` を作り、旧 trail に対して
           （:func:`_validate_audit_trail_append_only`）検証する。ここでの失敗は
           壊れている可能性のあるインスタンスが構築される *前* に表面化する —
           既存エントリを誤って落とす / 並べ替えるプログラミング バグに対する
           Fail-Fast。
        3. 現在状態を ``model_dump`` し、与えられたフィールド差分をスワップ し、
           ``model_validate`` で再構築する。これにより ``_check_invariants`` が再発火する。
        """
        new_entry = AuditEntry(
            id=uuid4(),
            actor_id=new_audit_actor,
            action=new_audit_action,
            comment=new_audit_comment,
            occurred_at=new_audit_at,
        )
        new_audit_trail = [*self.audit_trail, new_entry]
        _validate_audit_trail_append_only(self.audit_trail, new_audit_trail)

        state: dict[str, Any] = self.model_dump()
        if decision is not None:
            state["decision"] = decision
        if feedback_text is not None:
            state["feedback_text"] = feedback_text
        if decided_at is not None:
            state["decided_at"] = decided_at
        state["audit_trail"] = [entry.model_dump() for entry in new_audit_trail]
        # ``deliverable_snapshot`` / ``required_deliverable_criteria`` は
        # ``model_dump`` / ``model_validate`` をバイト単位で通過する: 構築時に
        # 固定した値が再構築された Gate にもそのまま継承される
        # （§確定 D snapshot_immutable / §確定 D' criteria_immutable）。
        rebuilt = ExternalReviewGate.model_validate(state)
        # §確定 D 3 重防衛 セーフティ ネット（snapshot）: 上記のキーワード専用
        # シグネチャが *構造的* 保証だが、Steve R-S1 はバリデータを **アクティブ**
        # に保つことを要求するため、構造的保証を破る将来のリファクタもここで捕捉。
        _validate_snapshot_immutable(self.deliverable_snapshot, rebuilt.deliverable_snapshot)
        # §確定 D' 3 重防衛 セーフティ ネット（criteria）: snapshot と同形。
        _validate_criteria_immutable(
            self.required_deliverable_criteria,
            rebuilt.required_deliverable_criteria,
        )
        return rebuilt


__all__ = ["ExternalReviewGate"]
