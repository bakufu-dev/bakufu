"""bakufu ドメイン全体で共有される StrEnum 定義。

ここの全 enum は ``StrEnum`` であるため、ラッパ無しで SQLite/JSON シリアライズが
自然に動作する。各 enum 内の順序は適用可能な範囲で自然なライフサイクル進行
（PENDING → 終端）に一致させており、テストでの enum 反復が現実的な状態遷移を
辿るようにしている。
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """:class:`AgentRef` が取れるロール。

    ``docs/design/domain-model/value-objects.md`` の正準リストをミラーする。
    ``str``（StrEnum）として保存されるため、後続の永続化機能でラッパ無しで
    SQLite/JSON シリアライズが容易になる。
    """

    LEADER = "LEADER"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"
    REVIEWER = "REVIEWER"
    UX = "UX"
    SECURITY = "SECURITY"
    ASSISTANT = "ASSISTANT"
    DISCUSSANT = "DISCUSSANT"
    WRITER = "WRITER"
    SITE_ADMIN = "SITE_ADMIN"


class StageKind(StrEnum):
    """``domain-model/value-objects.md`` §列挙型一覧 に従った Workflow Stage 種別。"""

    WORK = "WORK"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    EXTERNAL_REVIEW = "EXTERNAL_REVIEW"


class TransitionCondition(StrEnum):
    """``domain-model/value-objects.md`` に従った Workflow Transition 発火条件。"""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONAL = "CONDITIONAL"
    TIMEOUT = "TIMEOUT"


class ProviderKind(StrEnum):
    """``domain-model/value-objects.md`` §列挙型一覧 に従った LLM プロバイダ。

    6 値全てを事前に定義することで、Phase 2 の新プロバイダ追加には Adapter 実装
    + ``BAKUFU_IMPLEMENTED_PROVIDERS`` 更新のみで済むようにする — 永続化済みの
    全 Agent を再構築させる enum マイグレーションを発生させない（Agent feature
    §確定 I）。
    """

    CLAUDE_CODE = "CLAUDE_CODE"
    CODEX = "CODEX"
    GEMINI = "GEMINI"
    OPENCODE = "OPENCODE"
    KIMI = "KIMI"
    COPILOT = "COPILOT"


class TaskStatus(StrEnum):
    """``domain-model/value-objects.md`` §列挙型一覧 に従った Task ライフサイクル状態。

    ``docs/features/task/detailed-design.md`` §確定 A-2 ディスパッチ表によって
    凍結された 6 値。順序は自然なライフサイクル進行（PENDING → IN_PROGRESS →
    終端）に一致させているため、テストでの enum 反復が現実的な状態遷移を辿る。
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_EXTERNAL_REVIEW = "AWAITING_EXTERNAL_REVIEW"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class LLMErrorKind(StrEnum):
    """``domain-model/value-objects.md`` に従った粒度の粗い LLM-Adapter エラー分類。

    アプリケーション層のディスパッチ／モニタリングが retry vs Task BLOCK を判断
    するために使う。Task Aggregate 自体はこの enum を参照しない — 値は事前
    構築された ``last_error`` 文字列として届く — が、Adapter 機能と Admin CLI が
    両方とも同じ enum 表面を必要とするため共有 VO モジュールに置く。
    """

    SESSION_LOST = "SESSION_LOST"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class ReviewDecision(StrEnum):
    """``domain-model/value-objects.md`` に従った ExternalReviewGate の決定結果。

    ``docs/features/external-review-gate/detailed-design.md`` §確定 A ディスパッチ
    表で凍結された 4 値。``PENDING`` → {``APPROVED`` / ``REJECTED`` /
    ``CANCELLED``} のいずれか 1 つに 1 度だけ遷移し、3 つの終端値からはそれ以上
    遷移しない（state machine テーブルが非 PENDING からの ``approve`` /
    ``reject`` / ``cancel`` アクションを拒否する）。``record_view`` は全値で
    自己ループする（決定済み Gate に対する読み取りも監査証跡で許可、§確定 G）。
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AuditAction(StrEnum):
    """``domain-model/value-objects.md`` に従った監査ログ アクション識別子。

    MVP は ExternalReviewGate Aggregate のための 4 値（``record_view`` から来る
    ``VIEWED`` と、decision 遷移をミラーする ``APPROVED`` / ``REJECTED`` /
    ``CANCELLED``）を必要とする。``docs/design/domain-model/value-objects.md``
    §列挙型一覧 で凍結された残り 6 値（``RETRIED`` / ``ADMIN_RETRY_TASK`` /
    ``ADMIN_CANCEL_TASK`` / ``ADMIN_RETRY_EVENT`` / ``ADMIN_LIST_BLOCKED`` /
    ``ADMIN_LIST_DEAD_LETTERS``）は Admin CLI 機能が投入された時点で参加する。
    本番コードがまだ消費しない enum コントラクトを先回りで宣伝することは避ける —
    必要になるまで待つ（YAGNI、agent feature §確定 I と同方針）。
    """

    VIEWED = "VIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class GateDecision(StrEnum):
    """``domain-model/value-objects.md`` に従った InternalReviewGate 全体決定。

    internal-review-gate state machine と一致する 3 値:

    * ``PENDING`` — 1 つ以上の required ロールがまだ判定を提出していない、または
      REJECTED 判定をまだ受けていない。
    * ``ALL_APPROVED`` — 全 required GateRole が APPROVED 判定を提出し、誰も
      reject していない。
    * ``REJECTED`` — 少なくとも 1 つの判定が :attr:`VerdictDecision.REJECTED` を
      持つ（most-pessimistic-wins ルール）。

    :class:`ReviewDecision` と異なり ``CANCELLED`` 値は無い。InternalReviewGate
    のキャンセル（Stage 再アサイン）は Gate 内部ではなく Workflow / Task 層で扱う
    ため。
    """

    PENDING = "PENDING"
    ALL_APPROVED = "ALL_APPROVED"
    REJECTED = "REJECTED"


class VerdictDecision(StrEnum):
    """:class:`InternalReviewGate` に提出される role 別判定。

    2 値のみ — エージェントは成果物を承認するか拒否するかのいずれか。棄権は
    サポートしない。state machine は欠落判定を「未提出」と同じく扱う（全 required
    ロールが投票するまで ``GateDecision.PENDING`` のまま）。
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TemplateType(StrEnum):
    """DeliverableTemplate の種別。

    Aggregate が schema フィールドの期待型（str vs dict）を判定するために使う。
    """

    MARKDOWN = "MARKDOWN"
    JSON_SCHEMA = "JSON_SCHEMA"
    OPENAPI = "OPENAPI"
    CODE_SKELETON = "CODE_SKELETON"
    PROMPT = "PROMPT"


__all__ = [
    "AuditAction",
    "GateDecision",
    "LLMErrorKind",
    "ProviderKind",
    "ReviewDecision",
    "Role",
    "StageKind",
    "TaskStatus",
    "TemplateType",
    "TransitionCondition",
    "VerdictDecision",
]
