# 詳細設計書 — deliverable-template / room-matching

> feature: `deliverable-template` / sub-feature: `room-matching`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md) §7 業務ルール R1-A / §9 受入基準
> 関連: [`basic-design.md`](basic-design.md) / [`../domain/detailed-design.md`](../domain/detailed-design.md) / [`../../room/http-api/detailed-design.md`](../../room/http-api/detailed-design.md)
> 関連 Issue: [#120 feat(room-matching): Room matching (107-F)](https://github.com/bakufu-dev/bakufu/issues/120)

## 本書の役割

本書は **階層 3: deliverable-template / room-matching の詳細設計** を凍結する。[`basic-design.md`](basic-design.md) で凍結したモジュール構造・REQ 契約を、実装直前の **構造契約・アルゴリズム・確定文言** として詳細化する。実装 PR は本書を改変せず参照する。設計変更が必要なら本書を先に更新する PR を立てる。

## 記述ルール（必ず守ること）

詳細設計に **疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
必要なのは「構造契約（属性名・型・制約）」と「確定文言（メッセージ文字列）」と「実装の意図（なぜこの設計になるか）」のみ。

## クラス設計（詳細）

```mermaid
classDiagram
    class RoomMatchingService {
        -_override_repo: RoomRoleOverrideRepository
        -_role_profile_repo: RoleProfileRepository
        +validate_coverage(workflow: Workflow, effective_refs: tuple~DeliverableTemplateRef~) list~RoomDeliverableMismatch~
        +resolve_effective_refs(room_id: RoomId, empire_id: EmpireId, role: Role, custom_refs: tuple~DeliverableTemplateRef~ | None) tuple~DeliverableTemplateRef~
    }
    class RoomRoleOverrideService {
        -_room_repo: RoomRepository
        -_override_repo: RoomRoleOverrideRepository
        -_session: AsyncSession
        +upsert_override(room_id: RoomId, role: Role, refs: tuple~DeliverableTemplateRef~) RoomRoleOverride
        +delete_override(room_id: RoomId, role: Role) None
        +find_overrides(room_id: RoomId) list~RoomRoleOverride~
    }
    class RoomRoleOverride {
        <<Value Object (frozen Pydantic)>>
        +room_id: RoomId
        +role: Role
        +deliverable_template_refs: tuple~DeliverableTemplateRef~
        +__post_init__() RoomRoleOverrideInvariantViolation if duplicate template_id
    }
    class RoomDeliverableMatchingError {
        +room_id: str
        +role: str
        +missing: list~RoomDeliverableMismatch~
        +message: str
    }
    class RoomDeliverableMismatch {
        +stage_id: str
        +stage_name: str
        +template_id: str
    }
    RoomDeliverableMatchingError "1" --> "1..*" RoomDeliverableMismatch
```

### Service: `RoomMatchingService`

**責務**: マッチング検証（純粋関数）と effective_refs 解決（読み取り専用 I/O）。write 操作を持たず `_session` 不要。

| 属性 | 型 | 制約 | 意図 |
|-----|---|------|------|
| `_role_profile_repo` | `RoleProfileRepository` | コンストラクタで注入 | empire-level RoleProfile 参照 |
| `_override_repo` | `RoomRoleOverrideRepository` | コンストラクタで注入 | Room-level オーバーライド参照 |

**ふるまい:**

`validate_coverage(workflow, effective_refs)`:
- 全 `workflow.stages` を順次走査する
- 各 Stage について `required_deliverables` の中から `optional=False` のものを抽出する（§確定 E）
- 各必須 deliverable について `req.template_ref.template_id` が `effective_refs` の template_id セットに含まれるかを判定する（§確定 A）
- 不足を発見しても即時 raise せず、全 Stage を走査し **すべての不足** を収集する（§確定 C: Fail Fast は即時失敗ではなく全不足の一括報告）
- `list[RoomDeliverableMismatch]` を返す（空リストは充足を示す）
- 純粋関数（I/O なし）— テスト容易性のため非同期にしない
- **`role` は引数として受け取らない**。`RoomDeliverableMatchingError(room_id, role, missing)` の構築は呼び出し元（`RoomService.assign_agent`）の責務。これにより `validate_coverage` の責務を「不足の検出」のみに絞り、エラーオブジェクトへの文脈付与は呼び出し元に委ねる（Tell, Don't Ask 原則 + 純粋関数の維持）

`resolve_effective_refs(room_id, empire_id, role, custom_refs)`:
- §確定 B の優先順位に従い effective refs を非同期で取得する
- custom_refs が None でない場合は即座に返す（I/O なし）
- custom_refs が None の場合: `_override_repo.find_by_room_and_role` → ヒットすればその `deliverable_template_refs` を返す
- 不在の場合: `_role_profile_repo.find_by_empire_and_role` → ヒットすればその `deliverable_template_refs` を返す
- それも不在の場合: 空タプル `()` を返す（§確定 B）

### Service: `RoomRoleOverrideService`

**責務**: オーバーライドの CRUD。write 操作を持つため `_session` を注入し、UoW 境界（`async with self._session.begin():`）を管理する。

| 属性 | 型 | 制約 | 意図 |
|-----|---|------|------|
| `_room_repo` | `RoomRepository` | コンストラクタで注入 | Room 存在確認 + archived 確認 |
| `_override_repo` | `RoomRoleOverrideRepository` | コンストラクタで注入 | Room-level オーバーライド参照 |
| `_session` | `AsyncSession` | コンストラクタで注入 | write 操作の Unit-of-Work 境界 |

**ふるまい:**

`upsert_override(room_id, role, refs)`:
- `async with self._session.begin():` ブロック内で以下を実行
- Room 存在確認（不在 → `RoomNotFoundError`）/ archived 確認（→ `RoomArchivedError`）
- `RoomRoleOverride(room_id=room_id, role=role, deliverable_template_refs=refs)` を構築（template_id 重複時 → `RoomRoleOverrideInvariantViolation` 422）
- `_override_repo.save(override)` で UPSERT
- 保存済み `RoomRoleOverride` を返す

`delete_override(room_id, role)`:
- `async with self._session.begin():` ブロック内で以下を実行
- Room 存在確認 → `_override_repo.delete(room_id, role)`
- 存在しないオーバーライドへの delete は no-op（エラーなし）

`find_overrides(room_id)`:
- Room 存在確認 → `_override_repo.find_all_by_room(room_id)` を返す（read-only）
- 読み取り専用のため `async with session.begin():` 不要

### Domain VO: `RoomRoleOverride`

| 属性 | 型 | 制約 | 意図 |
|-----|---|------|------|
| `room_id` | `RoomId` | 必須 | Room スコープの識別子 |
| `role` | `Role` | 必須（StrEnum 値）| オーバーライド対象ロール |
| `deliverable_template_refs` | `tuple[DeliverableTemplateRef, ...]` | 空タプル可（明示的な「提供なし」を表現）| この Room 内でこの Role が提供する template refs |

**不変条件**: `deliverable_template_refs` 内の `template_id` は一意でなければならない（重複禁止）。重複がある場合はコンストラクタ内で `RoomRoleOverrideInvariantViolation` を raise する。

**設計根拠**: `RoleProfile.deliverable_template_refs` は同一制約を持つ（deliverable-template domain §確定）。`RoomRoleOverride` がこの制約を持たない場合、`RoleProfile` との非対称性が生まれ、override 値が永続化された後にマッチング結果が不定（同一 template_id が複数カバレッジとしてカウントされる等）になる可能性がある。Fail Fast 原則に従い構築時点で弾く。

**配置**: `backend/src/bakufu/domain/room/value_objects.py` に `AgentMembership` / `PromptKit` と並列追記する。frozen Pydantic モデルとして実装する。

### Application Exception: `RoomDeliverableMatchingError`

| 属性 | 型 | 意図 |
|-----|---|------|
| `room_id` | `str` | 対象 Room の文字列表現 |
| `role` | `str` | 検証対象 Role の文字列表現 |
| `missing` | `list[RoomDeliverableMismatch]` | 不足 deliverable の全リスト（1 件以上保証）|
| `message` | `str` | 2 行構造 (§確定 F) の確定文言 |

### Application Exception helper: `RoomDeliverableMismatch`

| 属性 | 型 | 意図 |
|-----|---|------|
| `stage_id` | `str` | 不足が検出された Stage の UUID 文字列 |
| `stage_name` | `str` | CEO に意味のある Stage 名（デバッグ / エラーメッセージ用）|
| `template_id` | `str` | 充足されていない DeliverableTemplate の UUID 文字列 |

### Repository Protocol: `RoomRoleOverrideRepository`

| メソッド | シグネチャ | 意図 |
|---------|-----------|------|
| `find_by_room_and_role` | `(room_id: RoomId, role: Role) -> RoomRoleOverride \| None` | UNIQUE(room_id, role) なので 0 または 1 件 |
| `find_all_by_room` | `(room_id: RoomId) -> list[RoomRoleOverride]` | Room 内全オーバーライド（ORDER BY role ASC）|
| `save` | `(override: RoomRoleOverride) -> None` | UPSERT。既存があれば `deliverable_template_refs_json` を UPDATE |
| `delete` | `(room_id: RoomId, role: Role) -> None` | 該当行を DELETE。不在は no-op |

## 確定事項（先送り撤廃）

### §確定 A: カバレッジ判定ルール

有効 refs が Stage の required_deliverable を「カバーしている」とは、`effective_refs` の中に `template_id` が等しい `DeliverableTemplateRef` が存在することを指す。`minimum_version` の比較は行わない。

**理由**: `minimum_version` の互換性チェック（実際の template version が minimum_version 以上かどうか）は Task 完了時の deliverable 提出段階で行う関心事であり、Room 編成時の責務ではない。Room 編成時は「このロールがそのテンプレートを提供する能力を持つか」のみを検証する。earliest 互換性チェックを Room 編成時に強制すると、テンプレートのパッチバージョンアップのたびに Room 再編成が必要になり過剰な制約となる（YAGNI）。

### §確定 B: effective_refs 優先順位（3 段階フォールバック）

| 優先順位 | 条件 | 使用する refs |
|---------|------|-------------|
| 1 | `custom_refs is not None`（リクエスト時に明示指定）| `custom_refs` を直接使用。空タプルも有効（「このロールはテンプレを提供しない」の明示宣言）|
| 2 | `RoomRoleOverride` が存在（この Room × Role のオーバーライド設定あり）| `override.deliverable_template_refs` を使用 |
| 3 | `RoleProfile` が存在（Empire レベルのデフォルト設定あり）| `role_profile.deliverable_template_refs` を使用 |
| 4 | いずれも存在しない | 空タプル `()` を返す。必須 deliverable が存在する Stage があればマッチング検証で失敗する |

**理由**: Room 固有のオーバーライドを Empire デフォルトより優先することで、CEO が Room ごとに異なる deliverable セットを割り当てられる（例: 新人向け Room は通常 RoleProfile より少ないテンプレート）。`custom_refs` をさらに優先するのは、リクエスト時の一過性指定（その場限りのオーバーライド）を既存設定より上位に置くことで、永続的な設定変更なしに動作検証できるようにするため。

### §確定 C: Fail Fast 詳細報告（全不足を一括収集）

`validate_coverage` は第一の不足を発見した時点で即時 raise しない。全 Stage の全 required_deliverable（optional=False）を走査し、不足しているもの全件を `list[RoomDeliverableMismatch]` に収集して呼び出し元に返す。呼び出し元は不足リストが空でない場合に `RoomDeliverableMatchingError` を構築して raise する。

**理由**: Stage が複数ある場合（典型的な Vモデル開発室は 13 Stage）、1 件ずつ修正 → エラー確認のサイクルを繰り返すことは CEO にとって非効率。全不足を一括で提示することで、RoleProfile の修正方針を1回で把握できる。

### §確定 D: DB スキーマ（room_role_overrides テーブル）

| カラム | 型 | 制約 | 意図 |
|-------|---|------|------|
| `room_id` | `VARCHAR(36)` | NOT NULL, FK → `rooms.id` ON DELETE CASCADE | Room を親とする依存関係 |
| `role` | `VARCHAR(64)` | NOT NULL | Role StrEnum 値（`ENGINEER` / `REVIEWER` 等） |
| `deliverable_template_refs_json` | `TEXT` | NOT NULL, DEFAULT `'[]'` | `DeliverableTemplateRef` リストを JSON 配列にシリアライズ（`template_id` + `minimum_version`）|
| `created_at` | `DATETIME` | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 監査 |
| `updated_at` | `DATETIME` | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 監査 |

**PRIMARY KEY**: `(room_id, role)`（`UNIQUE(room_id, role)` で UPSERT 対象）

**updated_at の更新**: SQLite には `ON UPDATE CURRENT_TIMESTAMP` トリガー構文がない。`SqliteRoomRoleOverrideRepository.save` の UPSERT 文では `updated_at = :now`（実行時刻）を明示的に SET すること。`DEFAULT CURRENT_TIMESTAMP` は INSERT 時のみ有効であり、UPDATE 時は自動更新されない点に注意する。

**外部キー設計**: `rooms.id` に対して `ON DELETE CASCADE` を設定し、Room アーカイブ後の物理削除が発生した場合（将来）にオーバーライドが孤立しないようにする。現 MVP では Room は論理削除のみのため cascade は保険的設計。物理削除実装時は cascade 影響範囲を必須レビュー項目とする。

**serialization 方針**: `deliverable_template_refs_json` は `[{"template_id": "<uuid>", "minimum_version": {"major": N, "minor": N, "patch": N}}, ...]` の JSON 文字列。既存の `composition_json` / `deliverable_template_refs_json`（role_profiles テーブル）と同一の serialization 規約に従う（deliverable-template repository §確定 B 踏襲）。

### §確定 E: マッチング対象は `optional=False` のみ

`Stage.required_deliverables` の中で `optional=True` の `DeliverableRequirement` はマッチング検証の対象外とする。

**理由**: `optional=True` は「提出が期待されるが必須ではない」を意味する（`workflow/feature-spec.md §7 確定 R1-17`）。Room 編成時にオプション deliverable の提供能力まで強制すると、柔軟な Role 編成を阻害する。オプション deliverable の提出は Task 完了時の加点要素として扱う（将来の Task completion 設計の責務）。

### §確定 F: エラーメッセージ 2 行構造

全例外メッセージは feature-spec.md §7 確定 R1-F（2 行構造）に従う。

| ID | 確定文言 |
|---|---------|
| MSG-RM-MATCH-001 | 1 行目: `[FAIL] Room {room_id} の役割 {role} は {N} 件の必須成果物テンプレートを提供できません。不足: {stage_name} → {template_id}[, ...]`（不足件数と対象 stage/template を列挙）/ 2 行目: `Next: RoleProfile の deliverable_template_refs にテンプレートを追加するか、Room レベルのオーバーライドを設定してください（PUT /api/rooms/{room_id}/role-overrides/{role}）。` |

HTTP レスポンス形式（error_handler 経由）:
```
{
  "error": {
    "code": "deliverable_matching_failed",
    "message": "<MSG-RM-MATCH-001 の 1 行目>",
    "detail": {
      "room_id": "<uuid>",
      "role": "<role>",
      "missing": [
        {"stage_id": "<uuid>", "stage_name": "<name>", "template_id": "<uuid>"},
        ...
      ]
    }
  }
}
```

**セキュリティ注記**: MVP はシングルユーザーローカルアプリケーション（loopback 127.0.0.1:8000 バインド + CSRF Origin 検証）として運用する。`missing` の内容（stage_id / stage_name / template_id）はユーザー自身が設定した Workflow ステージ・テンプレート情報であり、外部攻撃者から秘匿すべき機密データではないため、修正に必要な情報を提示する。

### §確定 G: `RoomService.assign_agent` への integration

`RoomService.assign_agent(room_id, agent_id, role, custom_refs=None)` の処理フローを以下のとおり変更する。

| 変更 | 場所 | 内容 |
|-----|------|------|
| パラメータ追加 | `assign_agent` シグネチャ | `custom_refs: tuple[DeliverableTemplateRef, ...] \| None = None` を末尾に追加 |
| UoW 統一 | `assign_agent` の全処理 | **全 async I/O（読み取り + 書き込み）を単一 `async with self._session.begin():` ブロックに包む**。以下の順序で実行する: 1) Room 存在確認・archived 確認 2) Agent 存在確認（`AgentRepository.find_by_id`）3) `empire_id = await _room_repo.find_empire_id_by_room_id(room_id)` 4) `workflow = await _workflow_repo.find_by_id(room.workflow_id)` 5) `effective_refs = await matching_svc.resolve_effective_refs(room_id, empire_id, role_enum, custom_refs)` — 内部で `_override_repo` / `_role_profile_repo` を呼ぶが `begin()` 内なので autobegin 競合なし 6) `missing = matching_svc.validate_coverage(workflow, effective_refs)` → `if missing: raise RoomDeliverableMatchingError(room_id, role_enum, missing)` 7) `room.add_member(membership)` 8) `await self._room_repo.save(updated_room, empire_id)` 9) `if custom_refs is not None: await self._override_repo.save(RoomRoleOverride(room_id, role_enum, custom_refs))` ← **`RoomService._override_repo` を直接使用**（`RoomRoleOverrideService.upsert_override` 経由にしない理由: ①Room 存在確認が二重実行になる ②`upsert_override` が独自 `begin()` を開くと外側の `begin()` と競合する）|

**UoW 境界の理由**: SQLAlchemy の autobegin により、repository メソッド（SELECT）を `async with session.begin():` の外側で呼び出すと暗黙的なトランザクションが開始される。その後 explicit な `begin()` を呼び出すと `InvalidRequestError: A transaction is already begun on this Session.` が発生する（BUG-001 パターン）。`EmpireService` / `RoomService` の既存パターンと同様に、全 async I/O を単一 `begin()` ブロックに包む方針を採用する。

### §確定 H: `RoomMatchingService` / `RoomRoleOverrideService` の DI 配線

**`get_room_matching_service(session: SessionDep)` ファクトリ** を `interfaces/http/dependencies.py` に追加する。注入する依存:

| パラメータ | 型 | インスタンス |
|---|---|---|
| `override_repo` | `RoomRoleOverrideRepository` | `SqliteRoomRoleOverrideRepository(session)` |
| `role_profile_repo` | `RoleProfileRepository` | `SqliteRoleProfileRepository(session)` |

**`get_room_role_override_service(session: SessionDep)` ファクトリ** を同ファイルに追加する。注入する依存:

| パラメータ | 型 | インスタンス |
|---|---|---|
| `room_repo` | `RoomRepository` | `SqliteRoomRepository(session)` |
| `override_repo` | `RoomRoleOverrideRepository` | `SqliteRoomRoleOverrideRepository(session)` |

**`RoomService.__init__` の完全な DI 引数リスト**（全引数を凍結）:

| パラメータ | 型 | インスタンス（`get_room_service` 内）|
|---|---|---|
| `room_repo` | `RoomRepository` | `SqliteRoomRepository(session)` |
| `empire_repo` | `EmpireRepository` | `SqliteEmpireRepository(session)` |
| `workflow_repo` | `WorkflowRepository` | `SqliteWorkflowRepository(session)` |
| `agent_repo` | `AgentRepository` | `SqliteAgentRepository(session)` |
| `matching_svc` | `RoomMatchingService` | `get_room_matching_service(session)` |
| `override_repo` | `RoomRoleOverrideRepository` | `SqliteRoomRoleOverrideRepository(session)` |

`override_repo` を `RoomService` に直接注入する理由: §確定 G ステップ 9 で `Room.save` と `RoomRoleOverride.save` を同一 `begin()` トランザクション内で実行するため、`RoomRoleOverrideService.upsert_override` 経由にできない（独自 `begin()` を開き競合する）。

`RoomRouter` は override CRUD エンドポイント（REQ-RM-HTTP-008〜010）で `RoomRoleOverrideService` を DI で受け取る。`RoomMatchingService` は `RoomService` 内部で使用するため Router が直接受け取らない。

## ユーザー向けメッセージ確定文言

| ID | HTTP ステータス | 確定文言（要点）| 発火条件 |
|---|--------------|-------------|---------|
| MSG-RM-MATCH-001 | 422 | `deliverable_matching_failed` — 不足 stage/template リスト付き | validate_coverage が missing >= 1 を返し、RoomService.assign_agent が RoomDeliverableMatchingError を raise |
