# 要求分析書

> feature: `directive`
> Issue: [#24 feat(directive): Directive Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/24)
> 凍結済み設計: [`docs/architecture/domain-model/aggregates.md`](../../architecture/domain-model/aggregates.md) §Directive / [`value-objects.md`](../../architecture/domain-model/value-objects.md) §ID 型一覧（`DirectiveId` は既存）

## 人間の要求

> Issue #24:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の **5 番目の Aggregate** として **Directive Aggregate Root** を実装する。Directive は CEO（リポジトリオーナー）が発行する指令で、`$` プレフィックスから始まるテキストと委譲先 Room を持つ。Directive から Task が生成され、MVP の核心ユースケース「CEO directive → Task 起票 → 各 Stage を Agent が処理 → 外部レビューで人間が承認/差し戻し → DONE」の**起点**を担う。

## 背景・目的

### 現状の痛点

1. M1 ドメイン骨格 4 兄弟（empire / workflow / agent / room）が PR #15 / #16 / #17 / #22 で完走したが、**CEO directive の起点 Aggregate がないため Task 起票経路が宙に浮いている**。`mvp-scope.md` §M7「V モデル E2E」へ至る経路が Directive で塞がれている
2. M1 後段の `task` Issue は `directive_id` を介して Directive を参照する設計（`aggregates.md` §Task 属性表）。Directive がないと Task 構築の参照整合性検査が成立しない
3. UI の MVP（普通の Tailwind ダッシュボード）は「Room チャネルで `$` プレフィックスのメッセージを送信 → directive 起票 → Task 生成」を中核ユースケースに据える。Directive の attribute / 不変条件が決まっていないと UI 側のチャット欄入力 → API 経路も着手できない

### 解決されれば変わること

- `task` Issue が Directive 参照を前提に実装可能になる（`directive_id` 必須属性が確定する）
- UI のチャット欄 → directive 発行 → Task 生成のシーケンスが API 仕様確定前でも domain 契約から逆算できる
- empire / workflow / agent / room の確立済みパターン（pre-validate / frozen Pydantic v2 / `_validate_*` helper / 例外 auto-mask / ディレクトリ層分離 / 例外型統一規約 / MSG 2 行構造）を **5 例目**として揃え、後続 task / external-review-gate の実装パターンを完全固定する

### ビジネス価値

- bakufu の核心思想「CEO directive → Vモデル工程進行 → 外部レビューで人間が承認」のうち最初の **CEO directive 起点** を Aggregate 単位で表現する。これが揃うと task / external-review-gate を直線消化できる経路が確立される
- 「`$` プレフィックスで CEO 入力を識別する」ai-team 由来の運用慣習を Aggregate 内で正規化し、UI / API レイヤと application 層の責務を明確に分離する

## 議論結果

### 設計担当による採用前提

- Directive Aggregate は **Pydantic v2 BaseModel + `model_config.frozen=True` + `model_validator(mode='after')`**（empire / workflow / agent / room と同じ規約）
- `text` は **NFC 正規化のみ、strip しない**（`Persona.prompt_body` / `PromptKit.prefix_markdown` と同規約。CEO の改行を含む長文 directive を保持するため）
- `target_room_id` の存在検証は **application 層責務**（`DirectiveService.issue()` で `RoomRepository.find_by_id` 確認）。Aggregate 内では UUID 型として valid までしか守らない
- `task_id is None` から有効 TaskId への遷移は **1 回のみ許可**（Aggregate 内不変条件 `_validate_task_link_immutable`、再リンクは `DirectiveInvariantViolation(kind='task_already_linked')`）
- ディレクトリ層分離は room と同パターン（`backend/src/bakufu/domain/directive/` 配下に `directive.py` / `aggregate_validators.py` / `__init__.py`）
- 状態変更ふるまいは新インスタンス返却の pre-validate 方式（agent §確定 D / room §確定 D 踏襲、冪等は「結果状態の同値性」で担保）
- `DirectiveInvariantViolation` は workflow / agent / room と同じく **`mask_discord_webhook` + `mask_discord_webhook_in` を `super().__init__` 前に強制適用**（`text` フィールドに CEO が webhook URL を貼り付け得る経路の防衛線）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| Aggregate 内で `text.startswith('$')` を強制 | UI / API 入力経路で CEO が毎回 `$` を打つ煩雑さを排除する責務は application 層が吸収すべき。agent §確定 I の `provider_kind` MVP gate と同じ責務分離 |
| `spawn_task() -> Task` を Directive 内で実装し Task インスタンスを直接生成 | **Aggregate 境界違反**（Aggregate Root のトランザクション境界は 1 Tx で 1 Aggregate）。Workflow / Room との結合度が過剰になる。`DirectiveService.issue()` の application 層が Task を生成し `directive.link_task(task_id)` で紐付ける責務に分離 |
| `task_id` を List に変えて 1 Directive → N Task の関係を許容 | MVP 範囲外。`aggregates.md` §Directive で「task_id: TaskId \| None — 生成された Task（未着手なら None）」と単一参照で凍結済み。複数 Task は別 Directive で発行する設計 |
| `text` に strip 適用 | CEO の長文 directive で末尾改行や前置詞の改行を保持する必要がある。`Persona.prompt_body` / `PromptKit.prefix_markdown` と同規約で NFC のみ |
| `created_at` を Aggregate 内で `datetime.now(timezone.utc)` 自動生成 | テスト容易性が下がる（freezegun が要る）。application 層 `DirectiveService.issue()` で生成して引数渡しする方が clean |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: `$` プレフィックス検査の責務分離

`aggregates.md` §Directive で「`$` プレフィックスから始まる」と概念定義されているが、**Aggregate 内不変条件として強制しない**。`DirectiveService.issue(raw_text, target_room_id)` の application 層で以下を実行:

1. `text = raw_text if raw_text.startswith('$') else '$' + raw_text` で正規化
2. `Directive(id=..., text=text, target_room_id=..., created_at=now(), task_id=None)` で構築

理由:

- UI / API 入力経路で CEO が `$` を打ち忘れた場合の自動付加が運用上自然（毎回打つのは煩雑）
- Aggregate は valid な text しか受け取らない契約で清潔（`$` 付きを保証された状態で扱う）
- agent §確定 I の `provider_kind` MVP gate を `AgentService.hire()` に押し出した先例と同じ責務分離パターン

#### 確定 R1-B: `spawn_task` ではなく `link_task` に変更（イーロン承認済み）

`aggregates.md` §Directive で「`spawn_task() -> Task`」と記述されているが、**Aggregate 境界違反**のため本 feature では以下に変更する:

1. **Aggregate 内ふるまい**: `link_task(task_id: TaskId) -> Directive` — 生成済み Task の id を関連付ける（pre-validate 方式で新インスタンス返却）
2. **application 層責務**: `DirectiveService.issue(raw_text, target_room_id)` が
   - Directive 構築（task_id=None）
   - DirectiveRepository.save(directive)
   - 同一 Tx 内で Task 構築 → TaskRepository.save(task)
   - directive.link_task(task.id) で紐付け → DirectiveRepository.save(updated_directive)

理由:

- Task は別 Aggregate Root のため、Directive 内で Task インスタンスを直接生成すると 1 Tx で 2 Aggregate 更新になり凝集境界が崩れる
- `link_task` は Aggregate 内不変条件（`task_id` 一意遷移）に閉じる責務
- `aggregates.md` §Directive の「`spawn_task() -> Task`」記述は概念的な意図で、実装パターンとしては application 層の use case に分解される

#### 確定 R1-C: `task_id` 二重リンク禁止（イーロン承認済み）

`task_id is None` から有効 TaskId への遷移は **1 回のみ許可**:

| 入力 Directive 状態 | `link_task(new_task_id)` 呼び出し結果 |
|---|---|
| `task_id is None` | 新 Directive（`task_id = new_task_id`、ペンディング解除）|
| `task_id == 既存有効 TaskId` | `DirectiveInvariantViolation(kind='task_already_linked', detail={'directive_id': ..., 'existing_task_id': ..., 'attempted_task_id': ...})` を Fail Fast |

`_validate_task_link_immutable` helper で `model_validator(mode='after')` 内で守る。Directive 1 件 → Task 1 件の関係を Aggregate 内で物理保証する。

#### 確定 R1-D: `DirectiveInvariantViolation` の auto-mask

CEO が directive `text` に webhook URL を貼り付け得るため、agent / workflow / room と同パターンで:

1. `super().__init__` 前に `mask_discord_webhook(message)` を message に適用
2. `detail` に対し `mask_discord_webhook_in(detail)` を再帰的に適用
3. `kind` は enum 文字列のため mask 対象外
4. その後 `super().__init__(masked_message)` を呼ぶ

#### 確定 R1-E: 例外型統一規約と MSG 2 行構造（room §確定 I 踏襲）

| 違反種別 | 例外型 | 発生レイヤ | kind |
|---|---|---|---|
| 構造的不変条件違反 | `DirectiveInvariantViolation` | Aggregate `model_validator(mode='after')` | `text_range` / `task_already_linked` |
| 型違反 / 必須欠落 | `pydantic.ValidationError` | Pydantic 型バリデーション | — |
| application 層の参照整合性違反 | `RoomNotFoundError` / `WorkflowNotFoundError` / `DirectiveNotFoundError` | `DirectiveService` / `RoomService` | — |

MSG-DR-001〜005 は **2 行構造**（`[FAIL] failure` + `Next: action`）で凍結し、test-design.md の TC-UT-DR-NNN で `assert "Next:" in str(exc)` を CI 物理保証する規約（room §確定 I 踏襲）。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（堀川さん想定） | bakufu インスタンスのオーナー、リポジトリ所有者 | GitHub / Docker / CLI 日常使用 | UI のチャット欄に `$ ブログのアクセス分析機能を作って` と入力 → Directive 起票 → Vモデル工程が走る | 1 行の指令で Vモデル開発フローを起動する |
| 後続 Issue 担当（バックエンド開発者） | `feature/task` PR の実装者 | DDD 経験あり、SQLAlchemy 2.x async / Pydantic v2 経験あり | 本 PR の設計書を真実源として読み、Task の `directive_id` 参照経路を実装 | 設計書の確定 R1-B / R1-C を素直に実装するだけで、後段レビューで責務散在を指摘されない |

##### ペルソナ別ジャーニー（個人開発者 CEO）

1. **directive 発行**: UI のチャット欄に `$ ブログのアクセス分析機能を作って` と入力 → Enter
2. **正規化**: application 層が `$` 付きを保証（既に `$` で始まれば変更なし、なければ自動付加）
3. **Directive 構築**: `Directive(id=uuid4(), text='$ ブログ...', target_room_id=current_room_id, created_at=now(), task_id=None)`
4. **永続化**: `DirectiveRepository.save(directive)` で SQLite に書き込み
5. **Task 生成**: 同一 Tx 内で Task を作り `directive.link_task(task_id)` で紐付け
6. **Vモデル工程開始**: Room の Workflow から Task が起票され、`current_stage_id` が初期 Stage に設定される

##### ジャーニーから逆算した受入要件

- ジャーニー 1: `text` は CEO の改行・絵文字・複数段落を保持できる必要がある（NFC のみ、strip しない）
- ジャーニー 3: `task_id is None` で構築できる（Directive 起票時点では Task 未生成）
- ジャーニー 5: `link_task(task_id)` で 1 回だけ紐付け可能、再リンクは Fail Fast
- ジャーニー全般: directive `text` に webhook URL が混入しても永続化前にマスキング、例外経路でも auto-mask（agent §確定 D 踏襲）

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
| REQ-DR-001 | Directive 構築 | コンストラクタで `id` / `text` / `target_room_id` / `created_at` / `task_id`（既定 None）を受け取り、不変条件検査を経て valid な Directive を返す | 必須 |
| REQ-DR-002 | Task 紐付け | `link_task(task_id)` で `task_id` を有効 TaskId に遷移。既に紐付け済みなら Fail Fast | 必須 |
| REQ-DR-003 | 不変条件検査 | コンストラクタ末尾と状態変更ふるまい末尾で実行。`text` 1〜10000 文字 / `task_id` 一意遷移 / `target_room_id` UUID 型 | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 4 設計書 + 実装 + ユニットテストを完結させる。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-DR-001〜003 | Directive Aggregate + ユニットテスト | M1 4 兄弟（PR #15/#16/#17/#22）+ M2 永続化基盤（PR #23）マージ済み |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(1)（属性数固定）。1ms 未満 |
| 可用性 | 該当なし — domain 層 |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 95% 以上（4 兄弟実績水準） |
| 可搬性 | 純 Python のみ |
| セキュリティ | `text` に webhook URL / API key が混入し得る。永続化前にマスキング規則の適用対象（[`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則）。`DirectiveInvariantViolation` は webhook URL auto-mask（4 兄弟と同パターン）。詳細は [`threat-model.md`](../../architecture/threat-model.md) §A04 |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `Directive(id, text, target_room_id, created_at)` で valid な Directive が構築される（task_id=None 既定） | TC-UT-DR-001 |
| 2 | text が 0 文字 / 10001 文字以上で `DirectiveInvariantViolation(kind='text_range')` | TC-UT-DR-002 |
| 3 | text の NFC 正規化が適用される（合成形 / 分解形が同一長で扱われる） | TC-UT-DR-003 |
| 4 | text の strip が**適用されない**（前後改行を保持） | TC-UT-DR-004 |
| 5 | `link_task(task_id)` で `task_id` が None → 有効 TaskId に遷移、新 Directive を返す | TC-UT-DR-005 |
| 6 | 既に紐付け済み（`task_id is not None`）の Directive で `link_task` は `DirectiveInvariantViolation(kind='task_already_linked')` | TC-UT-DR-006 |
| 7 | `DirectiveInvariantViolation` の `message` / `detail` 内の Discord webhook URL が `<REDACTED:DISCORD_WEBHOOK>` に伏字化される | TC-UT-DR-007 |
| 8 | Directive は frozen で構造的等価判定 | TC-UT-DR-008 |
| 9 | エラーメッセージは 2 行構造（`[FAIL] ...` + `Next: ...`）で `assert "Next:" in str(exc)` が pass | TC-UT-DR-001〜007 全件 |
| 10 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck |
| 11 | カバレッジが `domain/directive/` で 95% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Directive.text | CEO directive 本文（自然言語、`$` プレフィックス付き） | 中（webhook URL / API key 等が誤って混入し得る、Repository 永続化前マスキング必須、storage.md §逆引き表に追記対象） |
| Directive.target_room_id | 委譲先 Room の参照 | 低 |
| Directive.created_at | UTC 発行時刻 | 低 |
| Directive.task_id | 生成された Task の参照（None or 有効 TaskId） | 低 |
