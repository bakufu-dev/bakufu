# 業務仕様書（feature-spec）— Room

> feature: `room`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | [`http-api/`](http-api/) | ui（将来）
> 関連 Issue: [#18 feat(room): Room Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/18) / [#33 feat(room-repository): Room SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/33) / [#57 feat(room-http-api): Room + Agent assignment HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/57)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Room / [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §AgentMembership

## 本書の役割

本書は **Room という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Room という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / [`http-api/`](http-api/) / 将来の ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が Room という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・容量上限・メンバー一意・PromptKit 規約・永続性 等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy / FastAPI 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / delete-then-insert / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）

## 1. この feature の位置付け

bakufu インスタンスの組織（Empire）配下の編成空間「Room」を、ペルソナ（個人開発者 CEO）が Workflow と Agent を組み合わせて運用できる業務概念として定義する。Room は特定の Workflow を採用し、複数の Agent を Role 付きで編成する空間であり、CEO directive の委譲先として Task を起票する中核 Aggregate。

Room の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | Room の構造的整合性（不変条件・メンバー一意・容量・PromptKit 規約・archived terminal）を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | Room の状態を再起動跨ぎで保持（永続化）、PromptKit.prefix_markdown の secret マスキングを担保 |
| http-api | [`http-api/`](http-api/) | 外部クライアントから Room を操作・取得する経路（7 エンドポイント：CRUD + Agent 割り当て/解除）|
| ui | (将来) | CEO が Room を直感的に編成する画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #18（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の 4 番目の Aggregate として **Room Aggregate Root** を実装する。Room は Empire 配下の編成空間（"Vモデル開発室"、"アジャイル開発室"、"雑談部屋" 等）で、特定の Workflow を採用し、複数の Agent を Role 付きで編成する。CEO directive は最終的に Room を委譲先として Task を起票するため、Room は MVP のユースケースの中核を担う。

> Issue #33（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。**Room Aggregate** の SQLite 永続化を実装する。**`PromptKit.prefix_markdown` の Repository マスキング実適用**（room §確定 G 踏襲）が本 PR の核心。

> Issue #57（M3 http-api）:
>
> bakufu MVP（v0.1.0）M3「HTTP API」の Room エンドポイント群を実装する。Room CRUD（作成 / 一覧 / 単件取得 / 更新 / アーカイブ）および Agent の Room 割り当て / 解除の 7 エンドポイントを提供し、外部クライアント（将来の UI / CLI / テスト）が HTTP 経由で Room を操作できるようにする。

## 3. 背景・痛点

### 現状の痛点

1. M1 ドメイン骨格 3 兄弟（empire / workflow / agent）が完走したが、**3 者を編成して実用に供する Room がないと CEO directive を起点とする E2E が立ち上がらない**
2. M1 後段の `directive` は `target_room_id` を持ち、`task` は `room_id` を介して Workflow を解決する。Room がないと両 Aggregate の参照整合性検査が宙に浮く
3. UI の MVP は「Room 一覧 → Room 詳細」を中核ナビゲーションに据える設計で、Room の attribute / 不変条件が決まっていないと UI 側の画面・API も着手できない
4. CEO が Room を編成しても再起動で状態が消えるなら業務として成立しない（Room 設立は持続的な組織概念）
5. **room §確定 G 申し送り**: `PromptKit.prefix_markdown` に API key / GitHub PAT が混入した場合、Repository 経由での DB 永続化時に raw 流出する経路が残っている
6. domain / repository が完成しても **HTTP API がなければ UI / テストが Room を操作できない**。curl / SDK / 将来の UI すべてが HTTP API 経由で Room CRUD を行う

### 解決されれば変わること

- CEO が Room を設立し、Workflow / Agent / PromptKit を設定して組織に組み込める
- `directive` / `task` Issue が Room 参照を前提に実装可能になる
- Room の状態がアプリ再起動を跨いで保持される
- `PromptKit.prefix_markdown` に CEO が誤って API key / webhook URL を貼り付けても DB には `<REDACTED:*>` で永続化（**room §確定 G 実適用完了**）
- HTTP API 経由で Room の CRUD と Agent 編成が外部クライアントから操作可能になる

### ビジネス価値

- bakufu の核心思想「Room First / DAG Workflow / External Review Gate」のうち最初の **Room First** を Aggregate 単位で表現する
- 同一 Empire 内で複数 Room（V モデル開発室 / 雑談部屋 / ブログ編集部 等）を持てる構造が確定し、ai-team でのチャネル衝突運用を脱却する経路を確保する

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | 直接（将来の UI 経由）/ 間接（domain・repository sub-feature では application 層経由）/ HTTP API（M3） | Room を設立し、Workflow / Agent / PromptKit を設定してチームに組み込み、再起動跨ぎで状態が保持される |

bakufu システム全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-RM-001 | CEO | Room を設立できる（Workflow と任意の PromptKit を設定して valid な Room を構築する） | 必須 | domain |
| UC-RM-002 | CEO | Room にメンバー（Agent + Role）を追加できる | 必須 | domain |
| UC-RM-003 | CEO | Room からメンバーを削除できる | 必須 | domain |
| UC-RM-004 | CEO | Room の PromptKit を更新できる | 必須 | domain |
| UC-RM-005 | CEO | Room をアーカイブできる（物理削除なし、terminal 状態） | 必須 | domain |
| UC-RM-006 | CEO | 設立した Room の状態がアプリ再起動を跨いで保持される（永続化を意識しない） | 必須 | repository |
| UC-RM-007 | CEO | 同 Empire 内で Room 名は一意でなければならない（重複設立は拒否される） | 必須 | repository（find_by_name 提供）+ application 層（強制） |
| UC-RM-008 | CEO | HTTP API 経由で Room を作成できる（POST /api/empires/{empire_id}/rooms）| 必須 | http-api |
| UC-RM-009 | CEO | HTTP API 経由で Empire 内の Room 一覧を取得できる（GET /api/empires/{empire_id}/rooms）| 必須 | http-api |
| UC-RM-010 | CEO | HTTP API 経由で Room を単件取得できる（GET /api/rooms/{room_id}）| 必須 | http-api |
| UC-RM-011 | CEO | HTTP API 経由で Room を更新できる（name / description / prompt_kit の部分更新、PATCH /api/rooms/{room_id}）| 必須 | http-api |
| UC-RM-012 | CEO | HTTP API 経由で Room をアーカイブできる（DELETE /api/rooms/{room_id}、論理削除）| 必須 | http-api |
| UC-RM-013 | CEO | HTTP API 経由で Room に Agent を割り当てられる（POST /api/rooms/{room_id}/agents）| 必須 | http-api |
| UC-RM-014 | CEO | HTTP API 経由で Room の Agent 割り当てを解除できる（DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/{role}）| 必須 | http-api |
| UC-RM-015 | CEO | Agent を Room に割り当てる際、その Role が Workflow の全 Stage で要求される必須成果物テンプレートを提供できるかが自動検証される（業務ルール R1-11）| 必須 | deliverable-template/room-matching（#120） |
| UC-RM-016 | CEO | 特定 Room において特定 Role の DeliverableTemplate 提供セットを Empire デフォルト（RoleProfile）からオーバーライドできる（PUT / DELETE /api/rooms/{room_id}/role-overrides/{role}）| 必須 | deliverable-template/room-matching（#120） |
| UC-RM-017 | CEO | Room に設定されている Role オーバーライドの一覧を確認できる（GET /api/rooms/{room_id}/role-overrides）| 必須 | deliverable-template/room-matching（#120） |

## 6. スコープ

### In Scope

- Room 業務概念全体で観察可能な業務ふるまい（UC-RM-001〜017）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- HTTP API 経由の Room CRUD + Agent 割り当て/解除（UC-RM-008〜014）
- Agent 割り当て時の DeliverableTemplate カバレッジ自動検証（UC-RM-015）
- Room × Role の DeliverableTemplate オーバーライド機構（UC-RM-016〜017）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- Room の管理 UI → 将来の `room/ui/` sub-feature
- Room の管理 CLI → 別 feature `feature/admin-cli`（横断的）
- Directive / Task との結合（target_room_id 等） → `feature/directive` / `feature/task`
- 永続化基盤の汎用責務（WAL / マイグレーション / masking gateway） → [`feature/persistence-foundation`](../persistence-foundation/)
- LLM Adapter（Room の PromptKit を LLM に送信する経路） → 将来の `feature/llm-adapter`
- 「Empire 内 name 一意」の application 層強制 → `RoomService.create` で担保（本 http-api sub-feature スコープ内）
- leader 必須性（Workflow が要求する場合）の application 層強制 → 将来の `feature/room-application`

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: Room 名は 1〜80 文字、空白のみは無効

**理由**: CEO が認識可能な表示名であること。NFC 正規化 + strip 後の Unicode コードポイント数で判定。詳細は [`domain/detailed-design.md §確定 B`](domain/detailed-design.md)。

### 確定 R1-2: description は 0〜500 文字

**理由**: UI の Room カード表示で 2〜3 行に収まる長さ。長文の方針記述は PromptKit.prefix_markdown（10000 文字まで）に分離する責務分担。

### 確定 R1-3: `(agent_id, role)` ペアの重複は禁止、同一 agent_id の異なる Role は許容

**理由**: ai-team で「leader 兼 ux」のような兼任は実運用で頻出。`agent_id` 単独を一意キーにすると兼任が不可能になる（YAGNI 違反）。`AgentMembership.joined_at` を Role ごとに持てる構造も維持される。詳細は [`domain/detailed-design.md §確定 F`](domain/detailed-design.md)。

### 確定 R1-4: members 件数は 0〜50 件

**理由**: MVP の想定規模（V モデル開発室で 5 名、雑談部屋で 20 名程度）の数倍を上限に設定。Phase 2 で運用実績を見て調整。

### 確定 R1-5: アーカイブされた Room への状態変更は拒否される（archived terminal）

**理由**: アーカイブは soft delete 相当の終端状態。`add_member` / `remove_member` / `update_prompt_kit` を archived Room に呼ぶと業務ルール違反として拒否。`archive()` 自身は冪等で通過（既 archived でも新インスタンスを返す）。

### 確定 R1-6: アーカイブされた Room は物理削除しない

**理由**: 監査可能性。過去に設立した Room の履歴を audit_log（後段 feature）から参照する際、物理削除すると `room_id` が解決できなくなる。アーカイブは「論理削除フラグ + 履歴保持」とする。

### 確定 R1-7: Room の状態は再起動跨ぎで保持される

**理由**: Room 設立は持続的な組織概念であり、アプリ再起動による状態消失は業務として許容できない。永続化は CEO から意識されない透明な責務。

### 確定 R1-8: 同 Empire 内の Room 名は一意

**理由**: CEO が「部屋の重複」に気付かず設立すると、業務上の役割分担が曖昧になる。この不変条件は **Aggregate 外部の集合知識**（同 Empire 内の他 Room との比較を要する）のため、application 層 `RoomService.create()` が `RoomRepository.find_by_name(empire_id, name)` 経由で判定する。Aggregate 自身は自分の name の一意性を知らない設計。

### 確定 R1-9: `PromptKit.prefix_markdown` は永続化前にシークレットマスキングを適用する

**理由**: CEO が PromptKit 設計時に `prefix_markdown` に Discord webhook URL / API key を誤って含めた場合、DB 直読み / バックアップ / 監査ログ経路への raw token 流出を防ぐ（**room §確定 G 実適用**）。domain 層は raw 文字列を保持し、Repository 層の `MaskedText` TypeDecorator 経由で INSERT/UPDATE 前にマスキングを適用する。

### 確定 R1-10: HTTP API の path parameter は FastAPI に型検証を委ねる

**理由**: `empire_id` / `room_id` / `agent_id` はすべて UUID 型で受け取り、不正形式（非 UUID 文字列）には `RequestValidationError` → 422 を返す（500 ではない）。empire-http-api BUG-EM-SEC-001 解消方針に準拠。

### 確定 R1-11: Agent 役割割り当て時に DeliverableTemplate カバレッジを自動検証する（Issue #120）

CEO が `POST /api/rooms/{room_id}/agents` で Agent に Role を割り当てる際、application 層は以下の検証を行う:

1. その Role に対する「有効 refs」を決定する（優先順位: リクエスト時 custom_refs → Room レベルオーバーライド → Empire RoleProfile → 空）
2. Room が採用している Workflow の全 Stage について、`required_deliverables`（`optional=False` のみ）が有効 refs の `template_id` セットに含まれているかを検査する
3. 1 件でも不足が検出された場合は `RoomDeliverableMatchingError`（422）を raise し、不足している Stage / template の詳細を一括報告する

**理由**: Role の設定ミス（RoleProfile に必要なテンプレートが登録されていない）を Room 編成時（run-time より早い段階）に検出し、後続の Task 完了時に突然 deliverable 不整合が発覚する事故を防ぐ（Fail Fast 原則）。CEO が Room を設立した時点で必要な成果物が提供されることを保証することが bakufu の品質向上戦略の核心。

`optional=True` の `DeliverableRequirement` は検証対象外とする（任意提出 deliverable の提供能力は Room 編成時の必須条件ではない）。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Room 業務概念は外部通信を持たない（永続化はローカル SQLite） |
| 依存 feature | M3 開始時点: M1 `room/domain` + M2 `room/repository` + `http-api-foundation`（Issue #55 マージ済み）+ `empire/http-api` マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | 0 メンバー / 空 PromptKit の最小 Room が構築できる | UC-RM-001 | TC-UT-RM-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | name が業務ルール R1-1（1〜80 文字、空白のみ無効）に違反する Room は構築できない | UC-RM-001 | TC-UT-RM-002 |
| 3 | description が業務ルール R1-2（0〜500 文字）に違反すると拒否される | UC-RM-001 | TC-UT-RM-003 |
| 4 | `add_member(agent_id, role)` で members に追加できる | UC-RM-002 | TC-UT-RM-004 |
| 5 | 同一 `(agent_id, role)` ペアの `add_member` は拒否される（業務ルール R1-3） | UC-RM-002 | TC-UT-RM-005 |
| 6 | 同一 `agent_id` でも異なる `role` での追加は許容される（leader 兼 reviewer 等、業務ルール R1-3） | UC-RM-002 | TC-UT-RM-006 |
| 7 | `remove_member(agent_id, role)` で対象 membership を削除できる | UC-RM-003 | TC-UT-RM-007 |
| 8 | 不在の `(agent_id, role)` ペアの `remove_member` は拒否される | UC-RM-003 | TC-UT-RM-008 |
| 9 | members 件数が業務ルール R1-4（50 件上限）を超えると拒否される | UC-RM-002 | TC-UT-RM-009 |
| 10 | `update_prompt_kit(prompt_kit)` で prompt_kit が置換される | UC-RM-004 | TC-UT-RM-010 |
| 11 | `archive()` で `archived = True` の新 Room が返る | UC-RM-005 | TC-UT-RM-011 |
| 12 | `archived == True` の Room への `archive()` も新インスタンスを返す（冪等、業務ルール R1-5） | UC-RM-005 | TC-UT-RM-012 |
| 13 | `archived == True` の Room への `add_member` / `remove_member` / `update_prompt_kit` は拒否される（業務ルール R1-5） | UC-RM-001〜004 | TC-UT-RM-013 |
| 14 | 業務ルール違反のエラーメッセージに Discord webhook URL が含まれていた場合、`<REDACTED:DISCORD_WEBHOOK>` として伏字化される（domain 層での多層防御） | UC-RM-001 | TC-UT-RM-014 |
| 16 | 設立した Room の状態がアプリ再起動跨ぎで保持される（業務ルール R1-7） | UC-RM-006 | TC-E2E-RM-001（[`system-test-design.md`](system-test-design.md)） |
| 17 | 同 Empire 内で同名 Room を設立しようとすると拒否される（業務ルール R1-8） | UC-RM-007 | TC-E2E-RM-002 |
| 18 | `PromptKit.prefix_markdown` に webhook URL を含めて永続化すると DB には `<REDACTED:*>` で保存される（業務ルール R1-9） | UC-RM-006 | TC-IT-RR-008-masking（[`repository/test-design.md`](repository/test-design.md)） |
| 19 | HTTP API 経由で Room を作成できる（POST /api/empires/{empire_id}/rooms → 201 + RoomResponse）| UC-RM-008 | TC-IT-RM-HTTP-001（[`http-api/test-design.md`](http-api/test-design.md)） |
| 20 | 同 Empire 内で同名 Room を HTTP API 経由で作成しようとすると 409 が返る（業務ルール R1-8）| UC-RM-008 | TC-IT-RM-HTTP-002 |
| 21 | 存在しない Empire への Room 作成（POST /api/empires/{empire_id}/rooms）は 404 が返る | UC-RM-008 | TC-IT-RM-HTTP-003 |
| 22 | HTTP API 経由で Empire 内 Room 一覧を取得できる（GET /api/empires/{empire_id}/rooms → 200 + RoomListResponse）| UC-RM-009 | TC-IT-RM-HTTP-004 |
| 23 | HTTP API 経由で Room を単件取得できる（GET /api/rooms/{room_id} → 200 + RoomResponse）| UC-RM-010 | TC-IT-RM-HTTP-005 |
| 24 | 不在 Room への GET は 404 が返る | UC-RM-010 | TC-IT-RM-HTTP-006 |
| 25 | HTTP API 経由で Room を部分更新できる（PATCH /api/rooms/{room_id} → 200 + RoomResponse）| UC-RM-011 | TC-IT-RM-HTTP-007 |
| 26 | アーカイブ済み Room への PATCH は 409 が返る（業務ルール R1-5）| UC-RM-011 | TC-IT-RM-HTTP-008 |
| 27 | HTTP API 経由で Room をアーカイブできる（DELETE /api/rooms/{room_id} → 204）| UC-RM-012 | TC-IT-RM-HTTP-009 |
| 28 | HTTP API 経由で Agent を Room に割り当てられる（POST /api/rooms/{room_id}/agents → 201 + RoomResponse）| UC-RM-013 | TC-IT-RM-HTTP-010 |
| 29 | アーカイブ済み Room への Agent 割り当ては 409 が返る（業務ルール R1-5）| UC-RM-013 | TC-IT-RM-HTTP-011 |
| 30 | HTTP API 経由で Agent 割り当てを解除できる（DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/{role} → 204）| UC-RM-014 | TC-IT-RM-HTTP-012 |
| 31 | 不正な UUID パスパラメータ（empire_id / room_id / agent_id）は 422 が返る（業務ルール R1-10）| UC-RM-008〜014 | TC-IT-RM-HTTP-013 |
| 32 | Agent 割り当て時に RoleProfile が Workflow の必須 deliverable を全て充足していれば 201 が返る（業務ルール R1-11）| UC-RM-015 | TC-IT-RM-MATCH-001（[`../../deliverable-template/room-matching/test-design.md`](../../deliverable-template/room-matching/test-design.md)） |
| 33 | Agent 割り当て時に RoleProfile が不足している場合 422 が返り、不足 Stage / template の詳細が `error.detail.missing` に列挙される（業務ルール R1-11）| UC-RM-015 | TC-IT-RM-MATCH-002 |
| 34 | `custom_refs` を指定して assign_agent を呼ぶと、Empire RoleProfile の代わりに `custom_refs` でマッチング検証が行われ、かつその設定が Room レベルオーバーライドとして永続化される（業務ルール R1-11）| UC-RM-015, UC-RM-016 | TC-IT-RM-MATCH-003 |
| 35 | HTTP API 経由で Room の Role オーバーライドを設定できる（PUT /api/rooms/{room_id}/role-overrides/{role} → 200）| UC-RM-016 | TC-IT-RM-MATCH-010 |
| 36 | Room の Role オーバーライドを削除できる（DELETE /api/rooms/{room_id}/role-overrides/{role} → 204）| UC-RM-016 | TC-IT-RM-MATCH-011 |
| 37 | HTTP API 経由で Room の Role オーバーライド一覧を取得できる（GET /api/rooms/{room_id}/role-overrides → 200）| UC-RM-017 | TC-IT-RM-MATCH-012 |
| 38 | `workflow_id` を省略して Room を作成できる（POST /api/empires/{id}/rooms `{"name":"X"}` → 201、業務ルール R1-12）| UC-RM-008 | TC-IT-RM-HTTP-014（[`http-api/test-design.md`](http-api/test-design.md)）|
| 39 | PATCH /api/rooms/{room_id} で `workflow_id` を後付け設定できる（201 → `workflow_id` 非 null になる、業務ルール R1-12）| UC-RM-011 | TC-IT-RM-HTTP-015 |
| 40 | `workflow_id = null` の Room に Directive を投入しようとすると 422 が返る（`RoomWorkflowNotAssignedError`、業務ルール R1-12 server-side 強制）| UC-RM-008, UC-RM-011 | TC-IT-DR-HTTP-001a（[`../../directive/http-api/test-design.md`](../../directive/http-api/test-design.md)）|
| 41 | `PATCH /api/rooms/{room_id}` で `"workflow_id": null` を明示送信すると 422 が返る（`WorkflowDetachmentForbiddenError`、業務ルール R1-12 Workflow 解除禁止）| UC-RM-011 | TC-IT-RM-HTTP-016（[`http-api/test-design.md`](http-api/test-design.md)）|

E2E（受入基準 16, 17）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜14 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 18 は repository IT（TC-IT-RR-008）と E2E（TC-E2E-RM-003）の両方で検証。受入基準 19〜31, 38〜39, 41 は http-api sub-feature の IT で検証（[`http-api/test-design.md`](http-api/test-design.md)）。受入基準 40 は directive http-api sub-feature の IT で検証（[`../../directive/http-api/test-design.md`](../../directive/http-api/test-design.md)）。受入基準 32〜37 は deliverable-template/room-matching sub-feature の IT で検証（[`../../deliverable-template/room-matching/test-design.md`](../../deliverable-template/room-matching/test-design.md)）。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/room/` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。

### 確定 R1-12: Room 作成時の `workflow_id` は任意（後付け紐付け可）

**理由（Issue #183 Fix、2026-05-07 確定）**: 新規 Empire ではまず Room を設立してから Workflow を設計・紐付けする運用ユースケースが存在する。`workflow_id` を必須にすると「Room 作成 → Workflow 作成」のブートストラップ循環が発生し、CEO が HTTP API のみでは Empire の初期設定を完了できない。Domain 層・Pydantic スキーマ・Frontend 仕様はすべて `workflow_id = None` を許容しており、DB 側もこれに揃える（DDD 原則：Domain の意図に DB を合わせる）。

- `workflow_id = None` の Room は Directive 投入不可（対象 Workflow が未決定のため Task を起票できない）。フロントは Workflow 未設定 Room を「Directive 投入不可」として視覚的に明示する（将来 UI sub-feature の責務）
- 後付けで `PATCH /api/rooms/{room_id}` を通じて `workflow_id` を設定できる（業務ルール R1-11 の Agent 割り当て検証はこの時点で実行）
- **一度紐付けた Workflow の解除（`PATCH` に `"workflow_id": null` を明示送信）は業務上禁止**。Workflow を変更したい場合は Room をアーカイブして新規 Room を作成する（sentinel pattern による Workflow 入れ替えは Phase 2 検討課題、[`http-api/detailed-design.md §Q-OPEN-4`](http-api/detailed-design.md) 参照）
- `workflow_id` が `None` の状態での Agent 割り当ては業務上許容されない（R1-11 検証の前提 Workflow が存在しないため）。この制約は application 層で強制（後続 PR 責務）

## 11. 開放論点 (Open Questions)

凍結時点で未確定の論点はなし — R1 レビューで全件凍結済み。確定 R1-1〜12 として §7 に集約。

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Room.name | "V モデル開発室" 等の表示名 | 低 |
| Room.description | 部屋の用途説明（CEO 任意の自然言語） | 低 |
| PromptKit.prefix_markdown | 部屋固有のシステムプロンプト前置き（自然言語、Markdown） | **中**（webhook URL / API key 等が誤って混入し得る、Repository 永続化前マスキング必須） |
| AgentMembership.agent_id / role | 採用済み Agent の参照 + 役割 | 低 |
| 永続化テーブル群（rooms / room_members） | 上記の永続化先 | 低〜中（`rooms.prompt_kit_prefix_markdown` のみ MaskedText、その他は masking 対象なし） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 業務ふるまい呼び出しの応答が CEO 視点で「即時」（数 ms 以内）と感じられること。MVP 想定規模（members ≤ 50）で domain 層 1ms 未満、永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Room 状態が破損しない |
| 可搬性 | 純 Python のみ。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | 業務ルール違反は早期に拒否される（Fail Fast）。`PromptKit.prefix_markdown` の Discord webhook URL / API key は `MaskedText` で永続化前マスキング（業務ルール R1-9、room §確定 G 実適用）。`RoomInvariantViolation` の例外経路での webhook URL 漏洩は webhook auto-mask で防御（多層防御）。HTTP path parameter は FastAPI UUID 型検証で不正値 → 422（業務ルール R1-10）|
