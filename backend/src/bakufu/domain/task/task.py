"""Task Aggregate Root（REQ-TS-001〜009）。

``docs/features/task/`` を M1 の 6 番目の兄弟として実装する。Aggregate は
empire / workflow / agent / room / directive で確立された形を踏襲するが、Task の
ライフサイクル駆動的性質に固有の構造要素を 2 つ追加する:

* :mod:`bakufu.domain.task.state_machine` 内の **decision-table state machine**。
  §確定 B により ``Final[Mapping]`` + :class:`types.MappingProxyType` でロックされる。
* §確定 A-2（Steve R2 凍結）により state-machine テーブルのアクション名と 1:1 対応
  する **10 個の専用ビヘイビア メソッド** — 内部ディスパッチ無し、
  ``advance(..., gate_decision=...)`` の引数形も無し。
  ``method x current_status -> action`` はメソッド定義そのものによって静的に決定される。

設計コントラクト（再設計レビュー無しに破壊しないこと）:

* **Pre-validate rebuild（§確定 A）** — 全ビヘイビアは :meth:`_rebuild_with_state`
  を呼び、``model_dump`` / ``swap`` / ``model_validate`` を経由する。
  ``model_copy(update=...)`` は意図的に避ける: Pydantic v2 はその経路を
  ``validate=False`` にデフォルトし、モデル バリデータをサイレントにバイパスして
  しまう。
* **Terminal Fail-Fast（§確定 R1-B）** — DONE / CANCELLED の Task は不変。全メソッド
  は state machine に触れる前に :meth:`_assert_not_terminal` を通る。
* **State-machine bypass Fail-Fast（§確定 R1-A）** — 不正な ``(status, action)`` 対は
  ``TaskInvariantViolation(kind='state_transition_invalid')`` を送出し、合法アクション
  集合を ``detail`` に添付する。これにより MSG-TS-002 が「next action」ヒント込みで
  投入される。
* **Webhook auto-mask（§確定 I）** — :class:`TaskInvariantViolation` は構築時に
  ``mask_discord_webhook`` / ``mask_discord_webhook_in`` を ``message`` / ``detail``
  に適用するため、``last_error`` に Discord webhook URL が含まれていても例外
  ストリームは伏字化された状態を保つ。
* **Aggregate boundary（§確定 K）** — Task は ``ReviewDecision``（Gate VO）や他の
  Aggregate の Value Object を **import しない**。``approve_review`` / ``reject_review``
  は Gate APPROVED / REJECTED 時にアプリケーション層（``GateService``）が
  ディスパッチし、Task は Gate の内部に対して無知のままとなる。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.aggregate_validators import (
    _validate_assigned_agents_capacity,
    _validate_assigned_agents_unique,
    _validate_blocked_has_last_error,
    _validate_last_error_consistency,
    _validate_timestamp_order,
)
from bakufu.domain.task.state_machine import (
    TaskAction,
    allowed_actions_from,
    lookup,
)
from bakufu.domain.value_objects import (
    AgentId,
    Deliverable,
    DirectiveId,
    OwnerId,
    RoomId,
    StageId,
    TaskId,
    TaskStatus,
    TransitionId,
)


class Task(BaseModel):
    """1 体以上の Agent に委譲されるライフサイクル対応の作業単位。

    Task は ``DirectiveService.issue()`` によって生成される（PENDING、agent
    アサイン無し）。Workflow の Stage を進みながら Stage ごとの :class:`Deliverable`
    スナップショットを蓄積し、最終的に DONE または CANCELLED で終端する。
    ライフサイクルは 10 個のビヘイビア メソッドで駆動され、それらの名前は state
    machine のアクション名と完全に一致する — 暗黙ディスパッチは存在しない。

    Aggregate 外の関心事（Workflow / Room / Agent 参照整合性、``current_stage_id``
    ルックアップ、Gate 判定ブリッジ）は §確定 K により ``TaskService`` に置く。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: TaskId
    room_id: RoomId
    directive_id: DirectiveId
    current_stage_id: StageId
    deliverables: dict[StageId, Deliverable] = {}
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_ids: list[AgentId] = []
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        """Aggregate 境界で naive datetime を拒否する（§確定 H）。"""
        if value.tzinfo is None:
            raise ValueError(
                "Task timestamps must be timezone-aware UTC datetimes (received a naive datetime)"
            )
        return value

    @field_validator("last_error", mode="before")
    @classmethod
    def _normalize_last_error(cls, value: object) -> object:
        """``strip`` 無しで NFC 正規化を適用する（§確定 C）。

        LLM のスタック トレースはインデントのために先頭空白に依存する。
        ``Persona.prompt_body`` / ``PromptKit.prefix_markdown`` / ``Directive.text``
        が確立した先例（NFC のみ、strip 無し）を ``Task.last_error`` でも踏襲する。
        """
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """構造的不変条件を実行する（§確定 J kinds 3〜7）。

        バリデータ順序 — BUG-TSK-001 修正:

        ``_validate_blocked_has_last_error`` を ``_validate_last_error_consistency``
        より **先** に実行することで、BLOCKED 側の違反がより具体的な
        ``blocked_requires_last_error``（MSG-TS-006）として表面化する — テスト
        設計者およびオペレータが ``Task.block()`` が ``last_error=''`` /
        ``last_error=None`` を拒否したときに期待する「block() は非空の last_error
        を要求する」Next-action ヒント。Pydantic の ``model_validator(mode='after')``
        は最初の raise で短絡するため、この順序がレバーとなる。

        ``_validate_last_error_consistency`` は **逆向き** の不整合
        — ``status != BLOCKED`` かつ non-None ``last_error``（例えば ``status=DONE``
        にエラー テキストが残ったままの破損リポジトリ行）を捕捉するために残す。
        正例の 1〜2 パス（BLOCKED+None / BLOCKED+''）は上記 BLOCKED ヘルパで先行
        遮断されるが、バリデータ自身のテストケース
        ``test_invariants.py::TestLastErrorConsistency`` は依然として独立した
        コントラクトを固定する。
        """
        _validate_assigned_agents_unique(self.assigned_agent_ids)
        _validate_assigned_agents_capacity(self.assigned_agent_ids)
        _validate_blocked_has_last_error(self.status, self.last_error)
        _validate_last_error_consistency(self.status, self.last_error)
        _validate_timestamp_order(self.created_at, self.updated_at)
        return self

    # ---- 振る舞い（Tell, Don't Ask） -----------------------------------
    def assign(self, agent_ids: list[AgentId], *, updated_at: datetime) -> Task:
        """PENDING → IN_PROGRESS、``agent_ids`` を紐付ける（REQ-TS-002）。

        リストはそのまま受理する — 一意性／容量チェックはモデル バリデータに
        あるため、リポジトリ水和経路でもこのメソッドと同じゲートを通る。
        """
        next_status = self._lookup_or_raise("assign")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "assigned_agent_ids": list(agent_ids),
                "updated_at": updated_at,
            }
        )

    def commit_deliverable(
        self,
        stage_id: StageId,
        deliverable: Deliverable,
        by_agent_id: AgentId,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS 自己ループ、``deliverables[stage_id] = deliverable``（REQ-TS-003）。

        ``by_agent_id`` は ``TaskService`` との API 対称性のために受け取るが、ここでは
        ``assigned_agent_ids`` に対する検証は **行わない** — §確定 G に従い、その
        メンバシップ検査はアプリケーション層の責務。Aggregate は ``stage_id`` が
        構造的に有効な ``StageId`` であること、および state machine がアクションを
        許可することのみを保証する。
        """
        del by_agent_id  # ここではなく TaskService.commit_deliverable がチェックする。
        next_status = self._lookup_or_raise("commit_deliverable")
        new_deliverables = {**self.deliverables, stage_id: deliverable}
        return self._rebuild_with_state(
            {
                "status": next_status,
                "deliverables": new_deliverables,
                "updated_at": updated_at,
            }
        )

    def request_external_review(self, *, updated_at: datetime) -> Task:
        """IN_PROGRESS → AWAITING_EXTERNAL_REVIEW（REQ-TS-004）。"""
        next_status = self._lookup_or_raise("request_external_review")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "updated_at": updated_at,
            }
        )

    def approve_review(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        next_stage_id: StageId,
        *,
        updated_at: datetime,
    ) -> Task:
        """AWAITING_EXTERNAL_REVIEW → IN_PROGRESS（Gate APPROVED、REQ-TS-005a）。

        ``transition_id`` / ``by_owner_id`` は監査目的でアプリケーション層が
        受け渡す位置メタデータ。Aggregate はどちらも保存しない（audit_log は
        GateService の責務）。``next_stage_id`` は Workflow が進めるよう指示する
        Stage — それが Workflow の stages 内に存在するかの検証はアプリケーション層
        の責務（§確定 K）。
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("approve_review")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "current_stage_id": next_stage_id,
                "updated_at": updated_at,
            }
        )

    def reject_review(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        next_stage_id: StageId,
        *,
        updated_at: datetime,
    ) -> Task:
        """AWAITING_EXTERNAL_REVIEW → IN_PROGRESS（Gate REJECTED、REQ-TS-005b）。

        :meth:`approve_review` と同形。``next_stage_id`` は前進ではなくロールバック
        / リビジョン用の Stage となる。メソッドを分けたまま（単一の
        ``advance(..., gate_decision=...)`` にしない）は §確定 A-2 凍結 —
        Tell-Don't-Ask と Aggregate 境界保存のため。
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("reject_review")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "current_stage_id": next_stage_id,
                "updated_at": updated_at,
            }
        )

    def advance_to_next(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        next_stage_id: StageId,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS 自己ループ、``current_stage_id`` を進める（REQ-TS-005c）。

        EXTERNAL_REVIEW Gate を **通らない** Stage 間の進行（例: WORK Stage が次の
        WORK Stage に流れる）に用いる。Status は IN_PROGRESS のまま、
        ``current_stage_id`` のみが移動する。
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("advance_to_next")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "current_stage_id": next_stage_id,
                "updated_at": updated_at,
            }
        )

    def complete(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS → DONE（終端、REQ-TS-005d）。

        ``current_stage_id`` は意図的に変更しない: Task は現在の Stage で終端し、
        ダウンストリームの利用側はこの属性から最後の Stage を読める。現在の Stage
        が本当に sink であるかの検証は GateService / TaskService の責務（§確定 K）。
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("complete")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "updated_at": updated_at,
            }
        )

    def cancel(
        self,
        by_owner_id: OwnerId,
        reason: str,
        *,
        updated_at: datetime,
    ) -> Task:
        """{PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED} → CANCELLED（REQ-TS-006）。

        ``reason`` はアプリケーション層の監査メタデータ。Aggregate はこれを
        **永続化しない**（§設計判断補足 §「なぜ cancel reason を Aggregate 属性
        として持たないか」）。cancel 経路は ``last_error`` も ``None`` にリセット
        するため、``status != BLOCKED ⇔ last_error is None`` の一貫性不変条件が
        新インスタンスでも成立する。
        """
        del by_owner_id, reason
        next_status = self._lookup_or_raise("cancel")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "last_error": None,
                "updated_at": updated_at,
            }
        )

    def block(
        self,
        reason: str,
        last_error: str,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS → BLOCKED、``last_error`` を紐付ける（REQ-TS-007）。

        ``reason`` はアプリケーション層の監査注記（``TaskService`` が
        ``audit_log`` 書込前に記録する）。Aggregate に届くのは ``last_error`` のみ。
        モデル バリデータが NFC 正規化済みの形に対して
        ``_validate_blocked_has_last_error`` を実行するため、空 ／ 空白のみの
        ``last_error`` は構築時に拒否される。
        """
        del reason  # Task には保存せず TaskService.block が記録する。
        next_status = self._lookup_or_raise("block")
        return self._rebuild_with_state(
            {
                "status": next_status,
                # ``last_error`` のフィールド バリデータが rebuild 時に NFC 正規化を
                # 再適用するため、生の値をそのまま渡してよい。
                "last_error": last_error,
                "updated_at": updated_at,
            }
        )

    def unblock_retry(self, *, updated_at: datetime) -> Task:
        """BLOCKED → IN_PROGRESS、``last_error`` をクリアする（REQ-TS-008、§確定 D）。"""
        next_status = self._lookup_or_raise("unblock_retry")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "last_error": None,
                "updated_at": updated_at,
            }
        )

    # ---- 内部実装 -------------------------------------------------------
    def _assert_not_terminal(self) -> None:
        """DONE / CANCELLED の Task で呼ばれた振る舞いを拒否する（MSG-TS-001）。

        ここに集約することで、10 メソッド全てが同じ Fail-Fast 経路を共有する。
        将来の読者は「terminal_violation」を検索すれば単一の実装を見つけられる。
        terminal チェックは state-machine ルックアップの *前* に走るため、DONE Task
        への呼び出しは汎用の ``state_transition_invalid`` ではなくより具体的な
        ``MSG-TS-001`` メッセージを得る。
        """
        if self.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return
        raise TaskInvariantViolation(
            kind="terminal_violation",
            message=(
                f"[FAIL] Task is in terminal state {self.status.value} "
                f"and cannot be modified: task_id={self.id}\n"
                f"Next: Check Task status before invoking behaviors; "
                f"DONE/CANCELLED Tasks are immutable."
            ),
            detail={
                "status": self.status.value,
                "task_id": str(self.id),
            },
        )

    def _lookup_or_raise(self, action: TaskAction) -> TaskStatus:
        """振る舞い向けに terminal チェック + state-machine ルックアップを束ねる。

        state machine が決定した ``next_status`` を返す。3 つの失敗経路のいずれか
        （``terminal_violation`` / ``state_transition_invalid``）が
        :meth:`_rebuild_with_state` の実行前に :class:`TaskInvariantViolation` を
        送出するため、失敗時に元の Task が変更されないことが保証される
        （pre-validate コントラクト）。
        """
        self._assert_not_terminal()
        try:
            return lookup(self.status, action)
        except KeyError as exc:
            allowed = list(allowed_actions_from(self.status))
            raise TaskInvariantViolation(
                kind="state_transition_invalid",
                message=(
                    f"[FAIL] Invalid state transition: {self.status.value} "
                    f"cannot perform '{action}' "
                    f"(allowed actions from {self.status.value}: {allowed})\n"
                    f"Next: Verify Task lifecycle; review state_machine.py "
                    f"for the allowed transitions table."
                ),
                detail={
                    "status": self.status.value,
                    "action": action,
                    "allowed_actions": allowed,
                    "task_id": str(self.id),
                },
            ) from exc

    def _rebuild_with_state(self, updates: dict[str, Any]) -> Task:
        """振る舞い出力のための pre-validate rebuild（§確定 A）。

        M1 の 5 兄弟（Empire / Workflow / Agent / Room / Directive）と同じパターン。
        ``model_dump`` が正準 Python モード ペイロードを生成し、dict swap が振る舞い
        の差分を適用し、``model_validate`` が全フィールド バリデータと post-validator
        を再実行するため、新状態がどのように到達されたかに関わらず構造的不変条件
        が発火する。
        """
        state = self.model_dump()
        state.update(updates)
        return Task.model_validate(state)


__all__ = [
    "Task",
]
