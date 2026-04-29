"""InternalReviewGate Aggregate Root。

``INTERNAL_REVIEW`` Stage 完了のための内部（エージェント間）レビュー ゲートを実装
する。Aggregate は agent が提出する role 別 :class:`Verdict` を集約し、state machine
を介してそれらから全体の :class:`GateDecision` を導出し、
``model_validator(mode='after')`` で 4 つの構造的不変条件を強制する。

設計コントラクト（再設計レビュー無しに破壊しないこと）:

* **Pre-validate rebuild** — ``submit_verdict`` は ``model_dump`` / dict-update /
  ``model_validate`` を使う（``model_copy(update=...)`` ではない）。
  ExternalReviewGate §確定 E パターンと対称。
* **Frozen aggregate** — 全フィールド不変。すべての振る舞いは **新** インスタンスを
  返す。
* **Comment NFC のみ** — :class:`Verdict` の ``comment`` フィールドは NFC 正規化のみ
  行い、strip は適用しない（先頭空白に意味を持たせ得る複数行レビュー コメント）。
* **Decision は計算であり独立保存ではない** — Aggregate に保存される
  ``gate_decision`` は常に ``compute_decision(verdicts, required_gate_roles)`` と
  等しくなければならない。これは振る舞いメソッドと Aggregate 不変条件バリデータの
  両方で強制される。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.internal_review_gate.state_machine import compute_decision
from bakufu.domain.value_objects import (
    _VERDICT_COMMENT_MAX_CHARS,
    AgentId,
    GateDecision,
    GateRole,
    InternalGateId,
    StageId,
    TaskId,
    Verdict,
    VerdictDecision,
)


class InternalReviewGate(BaseModel):
    """``INTERNAL_REVIEW`` Stage 用の複数ロール内部レビュー チェックポイント。

    Gate は空の ``verdicts`` タプルと非空の ``required_gate_roles`` 集合と共に
    ``GateDecision.PENDING`` で生成される。エージェントは :meth:`submit_verdict`
    で判定を提出する。Gate は全 required role が承認した時に ``ALL_APPROVED`` に、
    いずれかの判定が ``VerdictDecision.REJECTED`` になった時点で ``REJECTED`` に遷移
    する（most-pessimistic-wins ルール）。

    Aggregate はフローズン — すべての振る舞いは **新** :class:`InternalReviewGate`
    インスタンスを返し、元のインスタンスは変更しない。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    id: InternalGateId
    task_id: TaskId
    stage_id: StageId
    required_gate_roles: frozenset[GateRole]
    verdicts: tuple[Verdict, ...]
    gate_decision: GateDecision
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def _require_created_at_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "InternalReviewGate.created_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> InternalReviewGate:
        """4 つの構造的不変条件を実行する（internal-review-gate §確定 J）。

        メソッド内 import によって、本モジュールと ``aggregate_validators``
        （型アノテーションのために本クラスを import する）の間の循環依存を解消する。
        """
        from bakufu.domain.internal_review_gate.aggregate_validators import validate_all

        validate_all(self)
        return self

    # ---- 振る舞い（Tell, Don't Ask） ------------------------------------

    def submit_verdict(
        self,
        *,
        role: GateRole,
        agent_id: AgentId,
        decision: VerdictDecision,
        comment: str,
        decided_at: datetime,
    ) -> InternalReviewGate:
        """1 つのエージェント判定を追加し、ゲート判定を再計算する。

        ステップ順（§確定 A 8 ステップ厳守）:

        1. ガード: ``gate_decision`` は PENDING でなければならない（決定済み Gate
           は不変）。
        2. ガード: ``role`` は ``self.verdicts`` に既に判定を持っていてはならない
           （Gate ごと role ごとに 1 判定）。
        3. ``comment`` を NFC 正規化（strip は **適用しない**）。
        4. ガード: ``role`` は ``required_gate_roles`` に含まれていなければならない
           （無効なロールは Verdict 構築前に拒否）。
        5. ガード: NFC 正規化済み ``comment`` の長さは 5000 文字を超えてはならない。
        6. 新しい :class:`Verdict` を構築してタプルに追加する。
        7. :func:`compute_decision` で新しい :class:`GateDecision` を計算する。
        8. ``model_dump`` / dict-update / ``model_validate`` で再構築し
           ``_check_invariants`` を再発火させ（pre-validate rebuild パターン、§確定 E）、
           新インスタンスを返す。

        Args:
            role: 提出エージェントが代表する GateRole。``required_gate_roles`` に
                含まれていなければならない（``_check_invariants`` の不変条件 2 で
                強制）。
            agent_id: 提出エージェントの UUID。
            decision: APPROVED または REJECTED。
            comment: 自由形式のレビュー コメント、0〜5000 NFC 文字。strip は
                **適用しない**。
            decided_at: 提出時の UTC tz-aware モーメント。

        Returns:
            判定が追加され、``gate_decision`` が再計算された新しい
            :class:`InternalReviewGate`。

        Raises:
            :class:`InternalReviewGateInvariantViolation`:
                ``gate_already_decided`` — Gate がもう PENDING ではない。
                ``role_already_submitted`` — そのロールは既に判定済み。
                ``invalid_role`` — ロールが required_gate_roles にない。
                ``comment_too_long`` — NFC 正規化コメントが 5000 文字超過。
                （後者 2 つは rebuild 時に ``_check_invariants`` でも捕捉されるが、
                ユーザフレンドリなメッセージのためにここで早期チェックする。）
        """
        # Step 1: gate は PENDING でなければならない。
        if self.gate_decision != GateDecision.PENDING:
            raise InternalReviewGateInvariantViolation(
                kind="gate_already_decided",
                message=(
                    f"[FAIL] InternalReviewGate は既に判断確定済みです"
                    f"（{self.gate_decision.value}）。\n"
                    f"Next: 新しい Gate が生成されるまでお待ちください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "gate_decision": self.gate_decision.value,
                },
            )

        # Step 2: role は既に判定を持っていてはならない。
        existing_roles = frozenset(v.role for v in self.verdicts)
        if role in existing_roles:
            raise InternalReviewGateInvariantViolation(
                kind="role_already_submitted",
                message=(
                    f'[FAIL] GateRole "{role}" は既に判定を提出済みです。\n'
                    f"Next: 別の GateRole エージェントとして判定を提出してください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "role": role,
                },
            )

        # Step 3: コメントを NFC 正規化（strip は意図的に適用しない）。
        normalized_comment = unicodedata.normalize("NFC", comment)

        # Step 4: Verdict 構築前に role のメンバーシップを検証する。
        # Behavior 層での早期チェック:
        # invariant 層 (_validate_verdict_roles_in_required) でも同一条件を検査するが、
        # MSG-IRG-004 の日本語エラーメッセージを返すためにここで先に raise する。
        # invariant 層は InternalReviewGateInvariantViolation の
        # kind='verdict_role_invalid' を raise するが、submit_verdict 経由の caller には
        # kind='invalid_role' + 日本語 MSG が期待される。
        if role not in self.required_gate_roles:
            raise InternalReviewGateInvariantViolation(
                kind="invalid_role",
                message=(
                    f'[FAIL] GateRole "{role}" は本 Gate の required_gate_roles に'
                    f"含まれていません。\n"
                    f"Next: 有効な GateRole（{sorted(self.required_gate_roles)}）"
                    f"で提出してください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "role": role,
                    "required_gate_roles": sorted(self.required_gate_roles),
                },
            )

        # Step 5: コメント長チェック（NFC 正規化済み、strip 無し）。
        comment_length = len(normalized_comment)
        if comment_length > _VERDICT_COMMENT_MAX_CHARS:
            raise InternalReviewGateInvariantViolation(
                kind="comment_too_long",
                message=(
                    f"[FAIL] コメントが文字数上限（5000文字）を超えています"
                    f"（{comment_length}文字）。\n"
                    f"Next: 5000文字以内に短縮してください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "length": comment_length,
                    "max_length": _VERDICT_COMMENT_MAX_CHARS,
                },
            )

        # Step 6: 新しい Verdict を構築してタプルに追加する。
        new_verdict = Verdict(
            role=role,
            agent_id=agent_id,
            decision=decision,
            comment=comment,
            decided_at=decided_at,
        )
        new_verdicts = (*self.verdicts, new_verdict)

        # Step 7: 新しい gate_decision を計算する。
        new_gate_decision = compute_decision(new_verdicts, self.required_gate_roles)

        # Step 8: pre-validate rebuild（model_dump → update → model_validate）で
        # _check_invariants を再発火させ、新インスタンスを返す。
        state: dict[str, Any] = self.model_dump()
        state["verdicts"] = [v.model_dump() for v in new_verdicts]
        state["gate_decision"] = new_gate_decision
        return InternalReviewGate.model_validate(state)


__all__ = ["InternalReviewGate"]
