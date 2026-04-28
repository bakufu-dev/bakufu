# 要求分析書

> feature: `room`
> Issue: [#18 feat(room): Room Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/18)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Room / [`value-objects.md`](../../design/domain-model/value-objects.md) §AgentMembership

## 人間の要求

> Issue #18:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の 4 番目の Aggregate として **Room Aggregate Root** を実装する。Room は Empire 配下の編成空間（"Vモデル開発室"、"アジャイル開発室"、"雑談部屋" 等）で、特定の Workflow を採用し、複数の Agent を Role 付きで編成する。CEO directive は最終的に Room を委譲先として Task を起票するため、Room は MVP のユースケースの中核を担う。

## 背景・目的

### 現状の痛点

1. M1 ドメイン骨格 3 兄弟（empire / workflow / agent）が PR #15 / #16 / #17 で完走したが、**3 者を編成して実用に供する Room がないと CEO directive を起点とする E2E が立ち上がらない**。`requirements/milestones.md` §M7「V モデル E2E」へ至る経路が Room で塞がれている
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
- `AgentMembership` は既存 VO（[`value-objects.md`](../../design/domain-model/value-objects.md) §AgentMembership）を流用する。本 feature で再定義しない
- `PromptKit` VO は本 feature で属性を確定する（[`aggregates.md`](../../design/domain-model/aggregates.md) §Room で「部屋固有のシステムプロンプト（前置き）」と概念のみ定義された VO）
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

#### 確定 R1-D: Room ユースケースの application 層責務凍結（EmpireService と RoomService の境界）

Room に関わる application 層ユースケースは **2 つの service** に責務分離する。**境界を本 PR で凍結**し、後続 `feature/empire-application` / `feature/room-application` PR は本節の境界に従う。

##### 責務分割表（凍結）

| ユースケース | 起点 service | 委譲先 service | 責務範囲 |
|---|---|---|---|
| Room 設立（新規作成） | `EmpireService.establish_room()` | `RoomService.create()` | Empire の `rooms` リスト追加 + Room Aggregate 構築。Empire 集合知識（同 Empire 内 name 一意）は `EmpireService` 責務、Workflow 参照整合性 + 初期 leader 必須性は `RoomService.create()` 責務 |
| Room アーカイブ | `EmpireService.archive_room()` | `RoomService.archive()` | Empire の `RoomRef.archived` 更新 + Room Aggregate `archive()` 呼び出し |
| メンバー追加 | `RoomService.add_member()` | — | Agent 存在検証 + Workflow leader 必須性検査 + Aggregate `add_member()` |
| メンバー削除 | `RoomService.remove_member()` | — | leader 削除後 0 件にならないかの検査 + Aggregate `remove_member()` |
| PromptKit 更新 | `RoomService.update_prompt_kit()` | — | Aggregate `update_prompt_kit()` のみ。検証は VO 構築時に完了 |

##### `EmpireService.establish_room(empire_id, name, description, workflow_id, prompt_kit)` の手順

1. `EmpireRepository.find_by_id(empire_id)` で Empire 取得（不在なら `EmpireNotFoundError`）
2. `RoomRepository.find_by_name(empire_id, name)` で Empire 内 name 重複検査（ヒットなら `RoomNameAlreadyExistsError`）
3. `RoomService.create(empire_id, name, description, workflow_id, prompt_kit)` を委譲（Workflow / Agent 検証はここで）
4. Empire の `establish_room(room_ref)` で `rooms` 追加 → 新 Empire を保存
5. Domain Event `RoomEstablished` を Outbox に追記（M2 永続化基盤完了後）

##### `RoomService.create(empire_id, name, description, workflow_id, prompt_kit)` の手順

1. `WorkflowRepository.find_by_id(workflow_id)` で Workflow 取得（不在なら `WorkflowNotFoundError`）
2. Workflow が leader を要求する（任意 Stage の `LEADER ∈ required_role`）場合、本 create 時点では **members 空のまま許容**（後続 add_member で leader 追加するまでは Workflow 側の leader 要求と整合しない過渡状態を許容）。Phase 2 で `RoomService.publish(room_id)` ユースケースを追加して「Room を運用可能状態にロックする時点で leader 必須」を強制する経路に拡張可能
3. `Room(...)` Aggregate を構築（pre-validate 通過）
4. `RoomRepository.save(room)` で永続化

##### `RoomService.add_member(room_id, agent_id, role)` の手順

1. `RoomRepository.find_by_id(room_id)` で Room 取得（不在なら `RoomNotFoundError`）
2. Room が `archived == True` なら早期 Fail Fast（Aggregate 側の `room_archived` 違反を待たず application 層で MSG-RM-006 相当のエラーを返す）
3. `AgentRepository.find_by_id(agent_id)` で Agent 存在検証（不在なら `AgentNotFoundError`）
4. Agent が当該 Empire 配下であることを `Empire.agents` で確認（`AgentNotInEmpireError`）
5. `WorkflowRepository.find_by_id(room.workflow_id)` で Workflow 取得
6. Workflow が leader を要求する場合、追加後の `members` で `role == LEADER` が 1 件以上残ることを保証（追加自体が LEADER なら自明、追加が他 Role でも既存 members に LEADER がいれば OK）
7. `room.add_member(agent_id, role, joined_at=now())` で Aggregate 内検査（`(agent_id, role)` 重複 / capacity / archived terminal）
8. `RoomRepository.save(updated_room)` で永続化
9. Domain Event `RoomMemberAdded` を Outbox に追記

##### `RoomService.remove_member(room_id, agent_id, role)` の手順

1. `RoomRepository.find_by_id(room_id)` で Room 取得
2. Workflow 取得
3. Workflow が leader を要求する場合、削除後の `members` で `role == LEADER` が 1 件以上残ることを検査（残らないなら `LeaderRequiredError` を Fail Fast）
4. `room.remove_member(agent_id, role)` で Aggregate 内検査
5. `RoomRepository.save(updated_room)` で永続化
6. Domain Event `RoomMemberRemoved` を Outbox に追記

##### 「Aggregate 内検査と application 層検査の二重定義」を許容する理由

`(agent_id, role)` 重複は Aggregate 内（構造的不変条件）、Workflow leader 必須性は application 層（外部知識依存）。両者は**検査対象が異なる** — 重複は Aggregate 集合のみで判定可能、leader 必須性は Workflow 全体を見ないと判定不能。よって責務散在ではなく**正しい責務分離**。

#### 確定 R1-F: 例外型統一規約 — `RoomInvariantViolation` vs `pydantic.ValidationError`

application 層 / 上位レイヤが catch する例外型を**統一**する:

| 違反種別 | 例外型 | 発生レイヤ |
|---|---|---|
| 構造的不変条件違反（`(agent_id, role)` 重複 / capacity / archived terminal / name range / description range） | `RoomInvariantViolation`（`kind` 別） | Aggregate `model_validator(mode='after')` |
| 型違反（None 渡し / 型不一致） | `pydantic.ValidationError` | Pydantic 型バリデーション（`mode='after'` より前） |
| application 層の参照整合性違反（Workflow / Agent 不在 / Empire 不在 / leader 必須） | 個別例外（`WorkflowNotFoundError` / `AgentNotFoundError` / `LeaderRequiredError`） | `RoomService` / `EmpireService` |

##### `update_prompt_kit` の例外型確定

PromptKit VO の長さ違反は **`PromptKit` の `model_validator` で `pydantic.ValidationError`** を raise（VO 構築時に完了）。`Room.update_prompt_kit(prompt_kit)` を呼ぶ時点では既に valid な VO のため、ここで raise されるのは `RoomInvariantViolation(kind='room_archived')` のみ（archived terminal 違反）。

つまり呼び出し側は:

1. `PromptKit(prefix_markdown=...)` 構築時 → `ValidationError`（型 / 長さ）
2. `room.update_prompt_kit(pk)` 呼び出し時 → `RoomInvariantViolation(kind='room_archived')` のみ

の 2 段階で catch する。例外型の揺れなし、責務境界が明確。

##### MSG ID と例外型の対応（凍結）

| MSG ID | 例外型 | kind |
|---|---|---|
| MSG-RM-001 | `RoomInvariantViolation` | `name_range` |
| MSG-RM-002 | `RoomInvariantViolation` | `description_too_long` |
| MSG-RM-003 | `RoomInvariantViolation` | `member_duplicate` |
| MSG-RM-004 | `RoomInvariantViolation` | `capacity_exceeded` |
| MSG-RM-005 | `RoomInvariantViolation` | `member_not_found` |
| MSG-RM-006 | `RoomInvariantViolation` | `room_archived` |
| MSG-RM-007 | `pydantic.ValidationError` | （PromptKit VO 経由） |

#### 確定 R1-E: PromptKit の構造（属性確定）

[`aggregates.md`](../../design/domain-model/aggregates.md) §Room で「部屋固有のシステムプロンプト（前置き）」と概念のみ定義された VO の構造を本 feature で確定する:

| 属性 | 型 | 制約 |
|----|----|----|
| `prefix_markdown` | `str` | 0〜10000 文字（NFC 正規化のみ、strip しない — Markdown の前後改行を保持） |

agent の `Persona.prompt_body` と完全に同じ規約（§確定 E 適用範囲表）。Phase 2 で variables / sections / role-specific prefix の追加余地を残すため VO 化を維持。永続化前マスキングは [`storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則の適用先一覧に追記する（同 PR で更新）。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー、リポジトリ所有者 | GitHub / Docker / CLI 日常使用、Python は読める / 書けないライン、Pydantic / SQLAlchemy 未経験 | 自宅 PC で `bakufu` を起動 → Web UI で Room を編成 → CEO directive を発行 → Discord で外部レビュー判定 → Task 完了を確認するループを 1 日数回繰り返す | 「V モデル開発室で要件定義 → 基本設計 → 実装 → テスト → 外部レビューを 1 日 1 タスク完走」を再現可能な操作で実現する |
| 後続 Issue 担当（バックエンド開発者） | `feature/room-repository` / `feature/room-application` PR の実装者 | DDD 経験あり、SQLAlchemy 2.x async / Pydantic v2 経験あり | 本 PR の設計書を真実源として読み、Aggregate を実装 → Repository を実装 → Service を実装 | 設計書の確定 R1-D / R1-E / R1-F を素直に実装するだけで、後段レビューで責務散在を指摘されない |
| 内部レビュー担当（Schneier） | セキュリティ視点で Room 設計を検査 | 永続化 / マスキング / 信頼境界に精通 | PR レビュー時に「PromptKit に webhook URL 混入経路が塞がれているか」を確認 | 例外経路 / Repository 永続化経路で webhook URL が漏洩しないことを 30 分以内に確認できる |

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **初回起動**: `bakufu` 起動 → UI に「Empire を作成」ダイアログ → Empire 構築完了
2. **Room 設立**: 「+ 新規 Room」ボタン → name="V モデル開発室" / description="3-2-3 process" / Workflow="V モデルプリセット" を選択 → 確定
3. **メンバー採用**: Agent 一覧から「ダリオ（leader）」「Norman（reviewer）」「Schneier（security）」をドラッグ → Role 選択 → 確定
4. **PromptKit 編集**: 「部屋固有の方針」テキストエリアに「全成果物は Vモデル左側 4 種を必ず生成すること」を入力 → 保存
5. **directive 発行**: チャット欄に `$ ブログのアクセス分析機能を作って` と入力 → Task 起票 → Stage 進行を観察
6. **アーカイブ**: タスク完了後、UI の「アーカイブ」ボタンを押下 → 状態が `archived` になり、members の追加・削除・PromptKit 編集が UI 上で disable される（バックエンドは MSG-RM-006 を返す）

##### ジャーニーから逆算した受入要件

- ジャーニー 2: name 重複時のエラーメッセージは「次の行動」hint 付き（MSG-RM-001 系で「Choose a different name within this Empire」）
- ジャーニー 3: 同一 Agent を leader + reviewer で兼任できる（`(agent_id, role)` 一意、`agent_id` 単独不可ではない）
- ジャーニー 4: PromptKit に webhook URL を貼り付けても永続化前にマスキング（`<REDACTED:DISCORD_WEBHOOK>`）、UI 表示も伏字
- ジャーニー 6: archived Room への操作を試みた際のエラーメッセージは「次の行動」hint 付き（MSG-RM-006 系で「Create a new Room; unarchive is not supported in MVP (Phase 2)」）

bakufu システム全体のペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

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
| セキュリティ | `PromptKit.prefix_markdown` は LLM システムプロンプト前置きに展開される。永続化前にマスキング規則の適用対象（[`storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則）。`RoomInvariantViolation` は webhook URL auto-mask（agent / workflow と同パターン）。詳細は [`threat-model.md`](../../design/threat-model.md) §A04 |

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
