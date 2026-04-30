"""bakufu ドメイン層のドメイン例外。

各違反は、人間可読な ``message`` と機械処理用の ``detail`` dict
（HTTP API マッパーやテストで利用）に加え、構造化された ``kind`` 判別子を持つ。

* :class:`EmpireInvariantViolation` — empire 機能。
  ``docs/features/empire/detailed-design.md`` §Exception 参照。
* :class:`WorkflowInvariantViolation` — workflow 機能。
  ``docs/features/workflow/detailed-design.md`` §Exception 参照。
* :class:`StageInvariantViolation` — workflow の Stage エンティティレベル違反。
  :class:`WorkflowInvariantViolation` を継承するため、呼び出し側は
  親クラスを ``except`` してもより具体的なサブクラスを受け取れる。
* :class:`AgentInvariantViolation` — agent 機能。
  ``docs/features/agent/detailed-design.md`` §Exception 参照。
* :class:`RoomInvariantViolation` — room 機能。
  ``docs/features/room/detailed-design.md`` §Exception 参照。

Workflow / Agent / Room の違反は ``message`` と ``detail`` の両方に
自動的に :func:`mask_discord_webhook_in` を適用するため、webhook シークレットは
例外テキストや診断ペイロードを介して漏洩しない。これは
``NotifyChannel.target`` / ``Persona.prompt_body`` / ``SkillRef.path`` /
``PromptKit.prefix_markdown`` / ``Room.{name,description}`` に紛れ込む可能性がある
webhook URL を多層防御するためのもの。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type EmpireViolationKind = Literal[
    "name_range",
    "agent_duplicate",
    "room_duplicate",
    "room_not_found",
    "capacity_exceeded",
]
"""詳細設計 §Exception に対応する ``EmpireInvariantViolation`` の判別子。"""


# ドメイン命名規約は DDD に従う: "Violation" は不変条件違反を表現するもので、
# プログラミングエラーではない。そのため N818 "Error suffix" ルールは適用しない。
class EmpireInvariantViolation(Exception):  # noqa: N818
    """:class:`Empire` 集約の不変条件違反時に送出される。

    Pydantic v2 の ``model_validator(mode='after')`` は ``ValueError`` /
    ``AssertionError`` 以外の例外を ``ValidationError`` でラップせずに
    再送出するため、呼び出し側は完全な ``kind`` / ``detail`` 構造を保ったまま
    本例外を直接受け取る。

    Attributes:
        kind: :data:`EmpireViolationKind` の正式な違反判別子のいずれか。
            テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: 詳細設計 §MSG の ``MSG-EM-001``〜``MSG-EM-005`` に対応する
            ``[FAIL] ...`` 形式のユーザー向け完全文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト（UUID, 長さ, 件数等）。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: EmpireViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: EmpireViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type WorkflowViolationKind = Literal[
    "name_range",
    "entry_not_in_stages",
    "transition_ref_invalid",
    "transition_duplicate",
    "transition_id_duplicate",
    "unreachable_stage",
    "no_sink_stage",
    "capacity_exceeded",
    "stage_duplicate",
    "cannot_remove_entry",
    "stage_not_found",
    "missing_notify_aggregate",
    "empty_required_role_aggregate",
    "from_dict_invalid",
]
"""workflow 詳細設計 §Exception に対応する :class:`WorkflowInvariantViolation`
の判別子。設計上の正式 11 種類に加え、MSG-WF-001 / MSG-WF-008 で表面化する
3 つの運用判別子（``name_range`` / ``stage_duplicate`` 等）と、Transition
コレクション契約に対する ``stage_duplicate`` の対となる
``transition_id_duplicate`` を追加している（詳細設計 §Aggregate Root: Workflow
の ``transitions: 0〜60 件、transition_id の重複なし`` 行参照）。"""


type StageViolationKind = Literal[
    "empty_required_role",
    "missing_notify",
]
""":class:`StageInvariantViolation` の判別子（Workflow 詳細設計）。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class WorkflowInvariantViolation(Exception):  # noqa: N818
    """:class:`Workflow` 集約の不変条件違反時に送出される。

    すべての ``message`` / ``detail`` 文字列は構築時に
    :func:`mask_discord_webhook_in` を通すため、埋め込まれた Discord
    webhook URL のシークレット ``token`` 部分は
    ``<REDACTED:DISCORD_WEBHOOK>`` に置換される。これにより、例外を
    シリアライズしただけで下流のログ・監査利用側が webhook 資格情報を
    漏洩することは不可能になる（Workflow 詳細設計 §確定 G
    「target のシークレット扱い」の「例外 message / detail」行）。
    """

    def __init__(
        self,
        *,
        kind: WorkflowViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: WorkflowViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


# ``except WorkflowInvariantViolation`` で Stage レベル違反も捕捉できるよう
# サブクラス化する（集約パスは Stage 自身のバリデータに委譲する場合があり、
# 呼び出し側は両者を一様に扱うべき）。
class StageInvariantViolation(WorkflowInvariantViolation):
    """:class:`Stage` の自己検証（集約とは独立）から送出される。

    ``kind`` は :data:`StageViolationKind` に絞られるが、周囲の
    ``WorkflowInvariantViolation` 型契約（``message`` / ``detail`` への
    シークレットマスク含む）は維持される。
    """

    def __init__(
        self,
        *,
        kind: StageViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        # 親へ転送し、マスクと判別子フィールドを同一に設定させる。
        # 静的型のため self.kind を再度狭める。
        super().__init__(
            kind=kind,  # type: ignore[arg-type]
            message=message,
            detail=detail,
        )
        self.kind: StageViolationKind = kind  # type: ignore[assignment]


type AgentViolationKind = Literal[
    "name_range",
    "no_provider",
    "default_not_unique",
    "provider_duplicate",
    "persona_too_long",
    "provider_not_found",
    "skill_duplicate",
    "skill_not_found",
    "skill_path_invalid",
    "archetype_too_long",
    "display_name_range",
    "provider_not_implemented",
    "skill_capacity_exceeded",
    "provider_capacity_exceeded",
]
"""Agent 詳細設計 §Exception に対応する :class:`AgentInvariantViolation` の
判別子。設計上の 12 種類に加え、§確定 C の境界値（providers ≤ 10, skills ≤ 20）を
表面化する 2 つの ``*_capacity_exceeded`` 運用判別子を追加している。これらが
なければ既存 kind と MSG が重複し、HTTP API 層での判別ができなくなる。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class AgentInvariantViolation(Exception):  # noqa: N818
    """:class:`Agent` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`EmpireInvariantViolation` と同一で、:class:`WorkflowInvariantViolation`
    と同じ Discord webhook シークレットマスクを適用する。SkillRef.path や
    Persona.prompt_body に Discord webhook URL の断片が含まれた場合でも、
    例外テキスト経由で漏洩することはない。
    """

    def __init__(
        self,
        *,
        kind: AgentViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: AgentViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type RoomViolationKind = Literal[
    "name_range",
    "description_too_long",
    "member_duplicate",
    "capacity_exceeded",
    "member_not_found",
    "room_archived",
]
"""Room 詳細設計 §Exception（§確定 I 例外型統一規約）に対応する
:class:`RoomInvariantViolation` の判別子。

集合は **6 種類で閉じている**: ``prompt_kit_too_long`` は *意図的に省略* されている。
PromptKit VO は Room 不変条件チェックが走る前に自身の ``model_validator`` で
:class:`pydantic.ValidationError` を送出するためであり、ここに追加しても
``RoomInvariantViolation`` から構造上到達できないデッドコードになる
（Room 詳細設計 §確定 I の 2 段階 catch 参照）。
"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class RoomInvariantViolation(Exception):  # noqa: N818
    """:class:`Room` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`AgentInvariantViolation` / :class:`WorkflowInvariantViolation`
    と同一で、同じ Discord webhook シークレットマスクを適用する。
    ``Room.name`` / ``Room.description`` / ``PromptKit.prefix_markdown`` は
    いずれもユーザーが貼り付けた webhook URL を含む可能性があるため、
    構築時に ``message`` / ``detail`` をマスクすることで、呼び出し側が
    例外をシリアライズしただけでトークンを漏洩することはなくなる
    （多層防御。Room 詳細設計 §確定 H 参照）。
    """

    def __init__(
        self,
        *,
        kind: RoomViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: RoomViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type DirectiveViolationKind = Literal[
    "text_range",
    "task_already_linked",
]
"""Directive 詳細設計 §確定 F に対応する :class:`DirectiveInvariantViolation` の
判別子。

集合は **2 種類で閉じている**。型・必須フィールド違反は
:class:`pydantic.ValidationError`（MSG-DR-003）として表面化し、``$``
プレフィックス正規化はアプリケーション層の責務（``DirectiveService.issue()``）
であるため、いずれも集約の判別子名前空間には漏れ出さない。
"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class DirectiveInvariantViolation(Exception):  # noqa: N818
    """:class:`Directive` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`RoomInvariantViolation` / :class:`AgentInvariantViolation` と
    同一で、同じ Discord webhook シークレットマスクを適用する。
    ``Directive.text`` はユーザーが貼り付ける CEO 指示の本文であり、
    webhook URL を埋め込まれる可能性があるため、構築時に ``message`` /
    ``detail`` をマスクすれば、呼び出し側は例外をシリアライズしただけで
    トークンを漏洩できなくなる（多層防御。Directive 詳細設計 §確定 E 参照）。
    """

    def __init__(
        self,
        *,
        kind: DirectiveViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: DirectiveViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type TaskViolationKind = Literal[
    "terminal_violation",
    "state_transition_invalid",
    "assigned_agents_unique",
    "assigned_agents_capacity",
    "last_error_consistency",
    "blocked_requires_last_error",
    "timestamp_order",
]
"""Task 詳細設計 §確定 J に対応する :class:`TaskInvariantViolation` の判別子。
7 種類の閉じた集合で、ターミナル違反・状態機械バイパス・
``model_validator(mode='after')`` で強制される 4 つの構造不変条件・
タイムスタンプ順序チェックを網羅する。型・必須フィールド違反は
``pydantic.ValidationError``（MSG-TS-008 / MSG-TS-009）として表面化し、
本判別子名前空間には漏れ出さない。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class TaskInvariantViolation(Exception):  # noqa: N818
    """:class:`Task` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`DirectiveInvariantViolation` / :class:`RoomInvariantViolation` /
    :class:`AgentInvariantViolation` / :class:`WorkflowInvariantViolation` と
    同一で、同じ Discord webhook シークレットマスクを適用する。
    ``Task.last_error`` は webhook URL を含む LLM-Adapter スタックトレースを
    保持する可能性があり（MVP は Discord 通知を行う）、
    ``Deliverable.body_markdown`` は CEO / Agent が書いたコンテンツである。
    両者は ``state_transition_invalid`` や ``last_error_consistency`` の経路を介して
    ``message`` / ``detail`` に流入し得るため、構築時に ``message`` /
    ``detail`` をマスクすれば、呼び出し側は例外をシリアライズしただけでトークンを
    漏洩できなくなる（多層防御。Task 詳細設計 §確定 I 参照）。
    """

    def __init__(
        self,
        *,
        kind: TaskViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: TaskViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type InternalReviewGateViolationKind = Literal[
    "role_already_submitted",
    "gate_already_decided",
    "comment_too_long",
    "invalid_role",
    "required_gate_roles_empty",
    "verdict_role_invalid",
    "duplicate_role_verdict",
    "gate_decision_inconsistent",
]
"""internal-review-gate 詳細設計に対応する :class:`InternalReviewGateInvariantViolation`
の判別子。8 種類で閉じた集合で、submit-verdict のガード条件と
``model_validator(mode='after')`` で強制される 4 つの構造的不変条件を網羅する。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class InternalReviewGateInvariantViolation(Exception):  # noqa: N818
    """:class:`InternalReviewGate` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`ExternalReviewGateInvariantViolation` と同一。内部レビュー コンテンツ
    （コメント、ロール名）はエージェント著作で Discord webhook URL を埋め込まない
    ため、本層ではシークレット マスキングを適用しない — 標準の ``kind`` /
    ``message`` / ``detail`` 三つ組で十分。

    Attributes:
        kind: :data:`InternalReviewGateViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: internal-review-gate 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト（ロール名、長さ、件数等）。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピー
            として格納する。
    """

    def __init__(
        self,
        *,
        kind: InternalReviewGateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: InternalReviewGateViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type ExternalReviewGateViolationKind = Literal[
    "decision_already_decided",
    "decided_at_inconsistent",
    "snapshot_immutable",
    "feedback_text_range",
    "audit_trail_append_only",
]
"""external-review-gate 詳細設計 §確定 I に対応する
:class:`ExternalReviewGateInvariantViolation` の判別子。5 種類で閉じた集合で、
state-machine バイパス（PENDING 限定の decision 遷移）、4 つの
``model_validator(mode='after')`` 構造的不変条件、そして audit-trail 追記専用
コントラクトを網羅する。型・必須フィールド違反は
:class:`pydantic.ValidationError`（MSG-GT-006）として表面化するため、本判別子
名前空間には漏れ出さない。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class ExternalReviewGateInvariantViolation(Exception):  # noqa: N818
    """:class:`ExternalReviewGate` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`TaskInvariantViolation` / :class:`DirectiveInvariantViolation` /
    :class:`RoomInvariantViolation` / :class:`AgentInvariantViolation` /
    :class:`WorkflowInvariantViolation` と同一で、同じ Discord webhook
    シークレット マスキングを適用する。Gate の ``feedback_text`` と
    ``audit_trail.comment`` は CEO 著作のフィールドで、Discord チャンネルから
    貼り付けられた webhook URL を埋め込まれる可能性があるため、構築時に
    ``message`` / ``detail`` をマスクすれば、呼び出し側は例外をシリアライズした
    だけでトークンを漏洩できなくなる（多層防御。external-review-gate 詳細設計
    §確定 H 参照）。
    """

    def __init__(
        self,
        *,
        kind: ExternalReviewGateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: ExternalReviewGateViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type DeliverableTemplateViolationKind = Literal[
    "schema_format_invalid",
    "composition_self_ref",
    "version_not_greater",
    "version_non_negative",
    "acceptance_criteria_empty_description",
    "acceptance_criteria_duplicate_id",
]
"""DeliverableTemplate 詳細設計 §Exception に対応する
:class:`DeliverableTemplateInvariantViolation` の判別子。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class DeliverableTemplateInvariantViolation(Exception):  # noqa: N818
    """:class:`DeliverableTemplate` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`EmpireInvariantViolation` / :class:`InternalReviewGateInvariantViolation`
    と同一。DeliverableTemplate のフィールドには Discord webhook URL が含まれないため、
    本層ではシークレット マスキングを適用しない。

    Attributes:
        kind: :data:`DeliverableTemplateViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: deliverable-template 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: DeliverableTemplateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: DeliverableTemplateViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type RoleProfileViolationKind = Literal[
    "duplicate_template_ref",
    "template_ref_not_found",
]
"""RoleProfile 詳細設計 §Exception に対応する
:class:`RoleProfileInvariantViolation` の判別子。"""


# DDD: "Violation" は不変条件違反を表現するもので、プログラミングのバグではない。
# そのため N818 "Error suffix" ルールは適用しない。
class RoleProfileInvariantViolation(Exception):  # noqa: N818
    """:class:`RoleProfile` 集約の不変条件違反時に送出される。

    形（``kind`` + ``message`` + ``detail`` + detail の不変コピー）は
    :class:`DeliverableTemplateInvariantViolation` と同一。

    Attributes:
        kind: :data:`RoleProfileViolationKind` の正式な違反判別子の
            いずれか。テストや HTTP API マッパーが使う安定した文字列値であり、
            ローカライズしない。
        message: role-profile 詳細設計 §MSG に対応する完全な
            ``[FAIL] ...`` 形式のユーザ向け文字列。
        detail: 診断・監査ログ向けの構造化コンテキスト。
            呼び出し側から見て例外が不変であるよう、新しい ``dict`` コピーとして格納する。
    """

    def __init__(
        self,
        *,
        kind: RoleProfileViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: RoleProfileViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


__all__ = [
    "AgentInvariantViolation",
    "AgentViolationKind",
    "DeliverableTemplateInvariantViolation",
    "DeliverableTemplateViolationKind",
    "DirectiveInvariantViolation",
    "DirectiveViolationKind",
    "EmpireInvariantViolation",
    "EmpireViolationKind",
    "ExternalReviewGateInvariantViolation",
    "ExternalReviewGateViolationKind",
    "InternalReviewGateInvariantViolation",
    "InternalReviewGateViolationKind",
    "RoleProfileInvariantViolation",
    "RoleProfileViolationKind",
    "RoomInvariantViolation",
    "RoomViolationKind",
    "StageInvariantViolation",
    "StageViolationKind",
    "TaskInvariantViolation",
    "TaskViolationKind",
    "WorkflowInvariantViolation",
    "WorkflowViolationKind",
]
