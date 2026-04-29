"""横断的および Aggregate 固有のテーブル群。

横断的（M2 persistence-foundation、PR #23）:

* :mod:`...tables.audit_log` — Admin CLI 監査証跡（DELETE 拒否）。
* :mod:`...tables.pid_registry` — bakufu_pid_registry（オーファン プロセス GC）。
* :mod:`...tables.outbox` — domain_event_outbox（Outbox パターン）。

Empire Aggregate（PR #25）:

* :mod:`...tables.empires` — Empire ルート行。
* :mod:`...tables.empire_room_refs` — RoomRef コレクション。
* :mod:`...tables.empire_agent_refs` — AgentRef コレクション。

Workflow Aggregate（PR #31）:

* :mod:`...tables.workflows` — Workflow ルート行（entry_stage_id は DB レベル
  FK を持たず、Aggregate 不変条件が代わりにガードする）。
* :mod:`...tables.workflow_stages` — Stage 子行。``notify_channels_json`` カラム
  は ``audit_log`` / ``domain_event_outbox`` の外で **最初の** ``MaskedJSONEncoded``
  カラムであり、CI 3 層防御の *positive* コントラクトに登録されている。
* :mod:`...tables.workflow_transitions` — Transition 子行（マスク無し）。

Agent Aggregate（PR #32）:

* :mod:`...tables.agents` — Agent ルート行。``prompt_body`` カラムは
  Schneier 申し送り #3 を **最初に** リポジトリ適用した ``MaskedText``（PR #23
  フック → PR #32 配線）。本テーブルは CI 3 層防御の *partial-mask* コントラクト
  に登録され、マスク対象カラムを厳密に 1 つ固定する。
* :mod:`...tables.agent_providers` — ProviderConfig 子行。
  「Agent ごとに default プロバイダはちょうど 1 つ」の多層防御として
  ``WHERE is_default = 1`` の部分一意インデックスを持つ。
* :mod:`...tables.agent_skills` — SkillRef 子行（マスク無し）。

Room Aggregate（PR #33）:

* :mod:`...tables.rooms` — Room ルート行。``prompt_kit_prefix_markdown`` カラムは
  ``MaskedText``（room §確定 G 実適用）。本テーブルは CI 3 層防御の
  *partial-mask* コントラクトに登録され、マスク対象カラムを厳密に 1 つ固定する。
  ``empire_room_refs.room_id → rooms.id`` FK は Alembic 0005 で確定する
  （BUG-EMR-001 closure）。
* :mod:`...tables.room_members` — AgentMembership 子行（マスク無し）。
  §確定 R1-D 多層防御のため複合 PK + 明示的 ``UniqueConstraint``。``agent_id`` は
  意図的に ``agents.id`` への FK を持たない（アプリケーション層の責務）。

Directive Aggregate（PR #34）:

* :mod:`...tables.directives` — Directive ルート行。``text`` カラムは ``MaskedText``
  （§確定 R1-E 実適用）。本テーブルは CI 3 層防御の *partial-mask* コントラクト
  に登録され、マスク対象カラムを厳密に 1 つ固定する。
  ``directives.task_id → tasks.id`` FK は Alembic 0007 で確定する
  （BUG-DRR-001 closure）。

Task Aggregate（PR #35）:

* :mod:`...tables.tasks` — Task ルート行。``last_error`` カラムは ``MaskedText``
  （§確定 R1-E 実適用）。本テーブルは CI 3 層防御の *partial-mask* コントラクト
  に登録され、マスク対象カラムを厳密に 1 つ固定する。インデックスは 2 つ:
  ``ix_tasks_room_id``（単一カラム）と ``ix_tasks_status_updated_id``（複合、
  §確定 R1-K）。
* :mod:`...tables.task_assigned_agents` — AgentId リスト子行。
  多層防御のため複合 PK ``(task_id, agent_id)`` + 明示的 ``UniqueConstraint``。
  ``agent_id`` は意図的に ``agents.id`` への FK を持たない（§設計決定 TR-001）。
* :mod:`...tables.deliverables` — Deliverable 子行。``body_markdown`` は
  ``MaskedText``（§確定 R1-E 実適用）。CI 3 層防御の *partial-mask* コントラクト
  に登録される。``UNIQUE(task_id, stage_id)`` は Aggregate の
  ``deliverables: dict[StageId, Deliverable]`` 不変条件をミラーする。
* :mod:`...tables.deliverable_attachments` — Attachment メタデータ子行（マスク
  無し）。メタデータのみ — 物理ファイル バイトは ``feature/attachment-storage``
  の範囲（§確定 R1-I）。

ExternalReviewGate Aggregate（PR #36）:

* :mod:`...tables.external_review_gates` — Gate ルート行。マスク対象カラムは
  2 つ: ``feedback_text``（MaskedText、§設計決定 ERGR-002）と
  ``snapshot_body_markdown``（MaskedText、§確定 R1-E 実適用）。両者とも CI 3 層
  防御の *partial-mask* コントラクトに登録される。インデックスは 3 つ
  （§確定 R1-K）: ``ix_external_review_gates_task_id_created``（複合）、
  ``ix_external_review_gates_reviewer_decision``（複合）、
  ``ix_external_review_gates_decision``（単一カラム）。
* :mod:`...tables.external_review_gate_attachments` — スナップショット Attachment
  メタデータ子行（マスク無し）。ビジネス キー ``UNIQUE(gate_id, sha256)``。
  PK は保存内部（save() ごとに uuid4() を再生成）。
* :mod:`...tables.external_review_audit_entries` — AuditEntry 子行。``comment``
  は ``MaskedText``（§確定 R1-E 実適用）。CI 3 層防御の *partial-mask* コントラクト
  に登録され、マスク対象カラムを厳密に 1 つ固定する。PK はドメイン側で割り当てられた
  値（AuditEntry.id、再生成しない）。

注意: ``conversations`` / ``conversation_messages`` テーブルは除外
（§BUG-TR-002 凍結済み）。Task ドメインが ``conversations: list[Conversation]``
属性を獲得した時点でここに登録される。

シークレット保持テーブルは :class:`MaskedJSONEncoded` / :class:`MaskedText` の
TypeDecorator（:mod:`bakufu.infrastructure.persistence.sqlite.base` で定義）で
カラムを宣言する。これらの TypeDecorator は ``process_bind_param`` 経由で値を
マスキング ゲートウェイに通す。バインド パラメータ解決時に発火するため、Core
``insert(table).values(...)`` と ORM ``Session.add()`` の両方で発動する —
技術的根拠は ``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D を参照（旧 ``before_insert`` / ``before_update`` イベント リスナ
方式は、PR #23 BUG-PF-001 でリスナが Core ``insert(table).values({...})`` で
発火しないことが判明し reverse-rejected された）。

Empire テーブルはシークレット保持カラムを **持たない**。明示的な不在は CI 3 層
防御（grep ガード + アーキ テスト + storage.md §逆引き表）に登録され、将来の
PR がカラムをサイレントにシークレット保持の意味へ置き換えることはできない。
Workflow ``workflows`` / ``workflow_transitions`` テーブルは同じノー マスク
パターンに従う。Workflow 側でシークレット保持なのは
``workflow_stages.notify_channels_json`` のみ。
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.tables import (
    agent_providers,
    agent_skills,
    agents,
    audit_log,
    deliverable_attachments,
    deliverables,
    directives,
    empire_agent_refs,
    empire_room_refs,
    empires,
    external_review_audit_entries,
    external_review_gate_attachments,
    external_review_gates,
    outbox,
    pid_registry,
    room_members,
    rooms,
    task_assigned_agents,
    tasks,
    workflow_stages,
    workflow_transitions,
    workflows,
)

__all__ = [
    "agent_providers",
    "agent_skills",
    "agents",
    "audit_log",
    "deliverable_attachments",
    "deliverables",
    "directives",
    "empire_agent_refs",
    "empire_room_refs",
    "empires",
    "external_review_audit_entries",
    "external_review_gate_attachments",
    "external_review_gates",
    "outbox",
    "pid_registry",
    "room_members",
    "rooms",
    "task_assigned_agents",
    "tasks",
    "workflow_stages",
    "workflow_transitions",
    "workflows",
]
