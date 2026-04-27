# 要求分析書

> feature: `room`
> Issue: [#18 feat(room): Room Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/18)
> 凍結済み設計: [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Room / [`value-objects.md`](../../architecture/domain-model/value-objects.md) §AgentMembership

## 人間の要求

> Issue #18:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の 4 番目の Aggregate として **Room Aggregate Root** を実装する。Room は Empire 配下の編成空間（"Vモデル開発室"、"アジャイル開発室"、"雑談部屋" 等）で、特定の Workflow を採用し、複数の Agent を Role 付きで編成する。CEO directive は最終的に Room を委譲先として Task を起票するため、Room は MVP のユースケースの中核を担う。

## 背景・目的

### 現状の痛点

1. M1 ドメイン骨格 3 兄弟（empire / workflow / agent）が PR #15 / #16 / #17 で完走したが、**3 者を編成して実用に供する Room がないと CEO directive を起点とする E2E が立ち上がらない**。`mvp-scope.md` §M7「V モデル E2E」へ至る経路が Room で塞がれている
2. M1 後段の `directive` は `target_room_id` を持ち、`task` は `room_id` を介して Workflow を解決する。Room がないと両 Aggregate の参照整合性検査が宙に浮く
3. UI の MVP（普通の Tailwind ダッシュボード）は「Room 一覧 → Room 詳細」を中核ナビゲーションに据える設計で、Room の attribute / 不変条件が決まっていないと UI 側の画面・API も着手できない

### 解決されれば変わること

- `directive` / `task` Issue が Room 参照を前提に実装可能になる
- UI の Room 編成画面（メンバー追加・削除、PromptKit 編集、archive）が API 仕様確定前でも domain 契約から逆算できる
- empire / workflow / agent の確立済みパターン（pre-validate / frozen Pydantic v2 / `_validate_*` helper / 例外 auto-mask / ディレクトリ層分離）を **4 例目**として揃え、後続 directive / task / external-review-gate の実装パターンを完全に固定する

### ビジネス価値

- bakufu の核心思想「Room First / DAG Workflow / External Review Gate」のうち最初の **Room First** を Aggregate 単位で表現する。これが揃うと Phase 2 の「Room プリセット（V モデル / アジャイル）」を Workflow と Room の組合せで提供できる
- 同一 Empire 内で複数 Room（V モデル開発室 / 雑談部屋 / ブログ編集部 等）を持てる構造が確定し、ai-team でのチャネル衝突運用を脱却する経路を確保する

## 議論結果

### 設計担当による採用前提

- Room Aggregate は **Pydantic v2 BaseModel + `model_config.frozen=True` + `model_validator(mode='after')`**（empire / workflow / agent と同じ規約）
- `AgentMembership` は既存 VO（[`value-objects.md`](../../architecture/domain-model/value-objects.md) §AgentMembership）を流用する。本 feature で再定義しない
- `PromptKit` VO は本 feature で属性を確定する（[`aggregates.md`](../../architecture/domain-model/aggregates.md) §Room で「部屋固有のシステムプロンプト（前置き）」と概念のみ定義された VO）
- `name` の Empire 内一意制約は **application 層責務**（empire の `name` / agent の `name` と同方針）。Aggregate 内では「name は非空かつ 1〜80 文字（NFC + strip 後）」だけ守る
- `workflow_id` 参照整合性 / Agent 存在検証 / leader 必須性（Workflow が要求する場合）の 3 件は **application 層責務**。Aggregate 内では「構造的不変条件（`(agent_id, role)` 重複なし、capacity 上限）」のみ守る
- ディレクトリ層分離は agent と同パターン（`backend/src/bakufu/domain/room/` 配下に `room.py` / `value_objects.py` / `aggregate_validators.py` / `__init__.py`、各ファイル 270 行目安）
- 状態変更ふるまいは新インスタンス返却の pre-validate 方式（agent の `archive()` `_rebuild_with_state` パターン踏襲、冪等は「結果状態の同値性」で担保）
- `RoomInvariantViolation` は workflow / agent と同じく **`mask_discord_webhook` + `mask_discord_webhook_in` を `super().__init__` 前に強制適用**（PromptKit に webhook URL が混入し得る経路の防衛線）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| Room Aggregate 内で Workflow の `required_role` を見て leader 必須を強制する | Aggregate 集合知識（Workflow 全体）を要するため Aggregate Root の責務外。agent の `provider_kind` MVP gate が `AgentService.hire()` に押し出された先例（§確定 I）と同方針で `RoomService.add_member()` 責務に分離 |
| `members` を `Dict[AgentId, list[Role]]` にする | 「同一 Agent が複数 Role を兼任」が表現できる利点はあるが、`AgentMembership.joined_at` を Role ごとに持てなくなる。MVP では `(agent_id, role)` を一意キーとする list で素直に表現 |
| `PromptKit` を単一の `prompt_prefix: str` に展開し VO 化しない | Phase 2 で variables / sections / role-specific prefix を追加する余地が消える。VO 化することで構造拡張が局所化される（agent の `Persona` VO と同設計判断） |
| `archived` を terminal 状態にせず unarchive 経路を提供 | MVP では archive = soft delete 相当の終端で十分。empire の `archive_room()` も同方針で物理削除しない（履歴保持）。unarchive は Phase 2 で運用実績を見て判断 |
| `name` の Empire 内一意を Aggregate 内で強制 | empire / agent と同じく Aggregate 集合知識（同 Empire の他 Room との衝突）であり Repository SELECT が必須。application 層 `RoomService.create()` の責務に分離 |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: leader 必須性検査の責務分離

「Workflow が leader を要求する場合に members に LEADER が 1 名以上」の検査は **`RoomService.add_member()` / `RoomService.remove_member()` / `RoomService.create()` の application 層責務**として分離する。Aggregate 内不変条件には含めない。

理由:

1. Workflow の `stages[*].required_role` 集合知識を要する（Room Aggregate 単独では観測できない）
2. Workflow が leader を要求しない部屋（雑談部屋 等）では検査自体が不要で、Aggregate 一律の不変条件にすると false positive を生む
3. agent の §確定 I（`provider_kind` MVP gate を `AgentService.hire()` に押し出し）と同じ責務分離パターン

`RoomService` 側の検査仕様は本 feature の §確定 R1-D で凍結する（実装は別 Issue）。

#### 確定 R1-B: `(agent_id, role)` 重複検査の Aggregate 内検査

`model_validator(mode='after')` で:

1. `members` の `(agent_id, role)` ペアを集合化
2. `len(set) < len(members)` なら `RoomInvariantViolation(kind='member_duplicate')` を raise

これは Aggregate 内不変条件として明確に定義される（外部知識を要しない）。**同一 Agent が異なる Role で複数 membership を持つことは許容**する（leader 兼 reviewer 等）。

#### 確定 R1-C: archive() ふるまいの返り値型と冪等性

`archive() -> Room`（新インスタンス）。agent の §確定 D を踏襲:

- 状態に依らず `_rebuild_with_state` 経由で新インスタンス返却
- 冪等性は「結果状態の同値性」（`new.archived == True`）で担保、オブジェクト同一性ではない
- 既に `archived == True` の Room に対しても同手順を踏み新インスタンス返却（エラーにしない）

archived Room への変更ふるまい（`add_member` / `remove_member` / `update_prompt_kit`）は **terminal 状態違反として `RoomInvariantViolation(kind='room_archived')` を raise**（Fail Fast）。

#### 確定 R1-D: `RoomService` の add_member / remove_member 責務（application 層、別 Issue）

application 層の `RoomService.add_member(room_id, agent_id, role)` は以下を**順次実行**:

1. `RoomRepository.find_by_id(room_id)` で Room 取得
2. `AgentRepository.find_by_id(agent_id)` で Agent 存在検証（不在なら `AgentNotFoundError`）
3. Workflow を `WorkflowRepository.find_by_id(room.workflow_id)` で取得
4. Workflow の **任意の Stage が `LEADER ∈ required_role`** を持つ場合、`role == LEADER` の member が結果として 1 件以上残ることを検査
5. `room.add_member(agent_id, role, joined_at)` で Aggregate 内検査
6. `RoomRepository.save(updated_room)` で永続化

`remove_member()` も同様で、削除後に LEADER が 0 件にならないかを Workflow 要件と突合する。

#### 確定 R1-E: PromptKit の構造（属性確定）

[`aggregates.md`](../../architecture/domain-model/aggregates.md) §Room で「部屋固有のシステムプロンプト（前置き）」と概念のみ定義された VO の構造を本 feature で確定する:

| 属性 | 型 | 制約 |
|----|----|----|
| `prefix_markdown` | `str` | 0〜10000 文字（NFC 正規化のみ、strip しない — Markdown の前後改行を保持） |

agent の `Persona.prompt_body` と完全に同じ規約（§確定 E 適用範囲表）。Phase 2 で variables / sections / role-specific prefix の追加余地を残すため VO 化を維持。永続化前マスキングは [`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則の適用先一覧に追記する（同 PR で更新）。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | GitHub / Docker / CLI 日常使用 | UI から Room を編成、Agent を Role 付きで採用、PromptKit で部屋固有の方針を注入 | 数クリックで V モデル開発室を立ち上げ、5 名の Agent を leader / developer / tester / reviewer / ux に配属、directive を流す |

bakufu システム全体のペルソナは [`docs/architecture/context.md`](../../architecture/context.md) §4 を参照。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / Pydantic v2 / pyright strict / pytest |
| 既存 CI | lint / typecheck / test-backend / audit |
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — domain 層 |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-RM-001 | Room 構築 | コンストラクタで `id` / `name` / `description` / `workflow_id` / `members` / `prompt_kit` / `archived` を受け取り、不変条件検査を経て valid な Room を返す | 必須 |
| REQ-RM-002 | メンバー追加 | `add_member(agent_id, role, joined_at)` で `members` リストに `AgentMembership` を追加。`(agent_id, role)` 重複は不変条件違反 | 必須 |
| REQ-RM-003 | メンバー削除 | `remove_member(agent_id, role)` で対象 `AgentMembership` を削除。不在は不変条件違反 | 必須 |
| REQ-RM-004 | PromptKit 更新 | `update_prompt_kit(prompt_kit)` で `prompt_kit` を新 PromptKit に置換 | 必須 |
| REQ-RM-005 | アーカイブ | `archive()` で `archived = True` の新 Room を返す（冪等） | 必須 |
| REQ-RM-006 | 不変条件検査 | コンストラクタ末尾と状態変更ふるまい末尾で実行。`(agent_id, role)` 重複なし / capacity 上限 / archived terminal / `name` 1〜80 文字 / `description` 0〜500 文字 | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 4 設計書 + 実装 + ユニットテストを完結させる。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-RM-001〜006 | Room Aggregate + PromptKit VO + ユニットテスト + storage.md / value-objects.md 追記 | M1 ドメイン骨格 3 兄弟（PR #15 / #16 / #17）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(M)（M=members 件数）。MVP の想定規模 M ≤ 50 で 1ms 未満 |
| 可用性 | 該当なし — domain 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 95% 以上（agent 実績水準） |
| 可搬性 | 純 Python のみ |
| セキュリティ | `PromptKit.prefix_markdown` は LLM システムプロンプト前置きに展開される。永続化前にマスキング規則の適用対象（[`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則）。`RoomInvariantViolation` は webhook URL auto-mask（agent / workflow と同パターン）。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A04 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | 0 メンバー / 空 PromptKit の最小 Room が構築できる | TC-UT-RM-001 |
| 2 | name が 0 文字 / 81 文字以上で `RoomInvariantViolation(kind='name_range')` | TC-UT-RM-002 |
| 3 | description が 501 文字以上で `RoomInvariantViolation(kind='description_too_long')` | TC-UT-RM-003 |
| 4 | `add_member(agent_id, role)` で `members` に追加 | TC-UT-RM-004 |
| 5 | 同一 `(agent_id, role)` の `add_member` は `RoomInvariantViolation(kind='member_duplicate')` | TC-UT-RM-005 |
| 6 | 異なる `role` での同一 `agent_id` の重複追加は許容（leader 兼 reviewer 等） | TC-UT-RM-006 |
| 7 | `remove_member(agent_id, role)` で対象 membership を削除 | TC-UT-RM-007 |
| 8 | 不在 `(agent_id, role)` の `remove_member` は `RoomInvariantViolation(kind='member_not_found')` | TC-UT-RM-008 |
| 9 | members 件数が 50 件超で `RoomInvariantViolation(kind='capacity_exceeded')` | TC-UT-RM-009 |
| 10 | `update_prompt_kit(prompt_kit)` で `prompt_kit` が置換される | TC-UT-RM-010 |
| 11 | `archive()` で `archived = True` の新 Room を返す | TC-UT-RM-011 |
| 12 | `archived == True` の Room に対する `archive()` も新インスタンスを返す（冪等、構造的等価） | TC-UT-RM-012 |
| 13 | `archived == True` の Room への `add_member` / `remove_member` / `update_prompt_kit` は `RoomInvariantViolation(kind='room_archived')` | TC-UT-RM-013 |
| 14 | `RoomInvariantViolation` の `message` / `detail` 内の Discord webhook URL が `<REDACTED:DISCORD_WEBHOOK>` に伏字化される | TC-UT-RM-014 |
| 15 | PromptKit / Room は frozen で構造的等価判定 | TC-UT-RM-015 |
| 16 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 17 | カバレッジが `domain/room/` で 95% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Room.name | "V モデル開発室" 等の表示名 | 低 |
| Room.description | 部屋の用途説明（CEO 任意の自然言語） | 低 |
| PromptKit.prefix_markdown | 部屋固有のシステムプロンプト前置き（自然言語、Markdown） | 中（webhook URL / API key 等が誤って混入し得る、Repository 永続化前マスキング必須） |
| AgentMembership.agent_id / role | 採用済み Agent の参照 + 役割 | 低 |
