# 業務仕様書（feature-spec）— Room

> feature: `room`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | http-api（将来）| ui（将来）
> 関連 Issue: [#18 feat(room): Room Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/18) / [#33 feat(room-repository): Room SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/33)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Room / [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §AgentMembership

## 本書の役割

本書は **Room という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Room という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

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
| http-api | (将来) | UI / 外部クライアントから Room を操作・取得する経路 |
| ui | (将来) | CEO が Room を直感的に編成する画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #18（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の 4 番目の Aggregate として **Room Aggregate Root** を実装する。Room は Empire 配下の編成空間（"Vモデル開発室"、"アジャイル開発室"、"雑談部屋" 等）で、特定の Workflow を採用し、複数の Agent を Role 付きで編成する。CEO directive は最終的に Room を委譲先として Task を起票するため、Room は MVP のユースケースの中核を担う。

> Issue #33（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。**Room Aggregate** の SQLite 永続化を実装する。**`PromptKit.prefix_markdown` の Repository マスキング実適用**（room §確定 G 踏襲）が本 PR の核心。

## 3. 背景・痛点

### 現状の痛点

1. M1 ドメイン骨格 3 兄弟（empire / workflow / agent）が完走したが、**3 者を編成して実用に供する Room がないと CEO directive を起点とする E2E が立ち上がらない**
2. M1 後段の `directive` は `target_room_id` を持ち、`task` は `room_id` を介して Workflow を解決する。Room がないと両 Aggregate の参照整合性検査が宙に浮く
3. UI の MVP は「Room 一覧 → Room 詳細」を中核ナビゲーションに据える設計で、Room の attribute / 不変条件が決まっていないと UI 側の画面・API も着手できない
4. CEO が Room を編成しても再起動で状態が消えるなら業務として成立しない（Room 設立は持続的な組織概念）
5. **room §確定 G 申し送り**: `PromptKit.prefix_markdown` に API key / GitHub PAT が混入した場合、Repository 経由での DB 永続化時に raw 流出する経路が残っている

### 解決されれば変わること

- CEO が Room を設立し、Workflow / Agent / PromptKit を設定して組織に組み込める
- `directive` / `task` Issue が Room 参照を前提に実装可能になる
- Room の状態がアプリ再起動を跨いで保持される
- `PromptKit.prefix_markdown` に CEO が誤って API key / webhook URL を貼り付けても DB には `<REDACTED:*>` で永続化（**room §確定 G 実適用完了**）

### ビジネス価値

- bakufu の核心思想「Room First / DAG Workflow / External Review Gate」のうち最初の **Room First** を Aggregate 単位で表現する
- 同一 Empire 内で複数 Room（V モデル開発室 / 雑談部屋 / ブログ編集部 等）を持てる構造が確定し、ai-team でのチャネル衝突運用を脱却する経路を確保する

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | 直接（将来の UI 経由）/ 間接（domain・repository sub-feature では application 層経由） | Room を設立し、Workflow / Agent / PromptKit を設定してチームに組み込み、再起動跨ぎで状態が保持される |

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

## 6. スコープ

### In Scope

- Room 業務概念全体で観察可能な業務ふるまい（UC-RM-001〜007）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)

### Out of Scope（参照）

- Room の HTTP API → 将来の `room/http-api/` sub-feature
- Room の管理 UI → 将来の `room/ui/` sub-feature
- Room の管理 CLI → 別 feature `feature/admin-cli`（横断的）
- Directive / Task との結合（target_room_id 等） → `feature/directive` / `feature/task`
- 永続化基盤の汎用責務（WAL / マイグレーション / masking gateway） → [`feature/persistence-foundation`](../persistence-foundation/)
- LLM Adapter（Room の PromptKit を LLM に送信する経路） → 将来の `feature/llm-adapter`
- 「Empire 内 name 一意」の application 層強制 → 将来の `feature/empire-application`（domain と repository の合間に位置）
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

**理由**: CEO が「部屋の重複」に気付かず設立すると、業務上の役割分担が曖昧になる。この不変条件は **Aggregate 外部の集合知識**（同 Empire 内の他 Room との比較を要する）のため、application 層 `EmpireService.establish_room()` が `RoomRepository.find_by_name(empire_id, name)` 経由で判定する。Aggregate 自身は自分の name の一意性を知らない設計。

### 確定 R1-9: `PromptKit.prefix_markdown` は永続化前にシークレットマスキングを適用する

**理由**: CEO が PromptKit 設計時に `prefix_markdown` に Discord webhook URL / API key を誤って含めた場合、DB 直読み / バックアップ / 監査ログ経路への raw token 流出を防ぐ（**room §確定 G 実適用**）。domain 層は raw 文字列を保持し、Repository 層の `MaskedText` TypeDecorator 経由で INSERT/UPDATE 前にマスキングを適用する。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Room 業務概念は外部通信を持たない（永続化はローカル SQLite） |
| 依存 feature | M1 開始時点: empire / workflow / agent の M1 マージ済み / M2 開始時点: M1 `room/domain` + [`feature/persistence-foundation`](../persistence-foundation/) + empire-repo / workflow-repo / agent-repo マージ済み |

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
| 14 | 業務ルール違反のエラーメッセージに Discord webhook URL が含まれていた場合、`<REDACTED:DISCORD_WEBHOOK>` として伏字化される（domain 層での多層防御、受入基準 18 の repository 層マスキングとは独立） | UC-RM-001 | TC-UT-RM-014 |
| 16 | 設立した Room の状態がアプリ再起動跨ぎで保持される（業務ルール R1-7） | UC-RM-006 | TC-E2E-RM-001（[`system-test-design.md`](system-test-design.md)） |
| 17 | 同 Empire 内で同名 Room を設立しようとすると拒否される（業務ルール R1-8） | UC-RM-007 | TC-E2E-RM-002 |
| 18 | `PromptKit.prefix_markdown` に webhook URL を含めて永続化すると DB には `<REDACTED:*>` で保存される（業務ルール R1-9） | UC-RM-006 | TC-IT-RR-008-masking（[`repository/test-design.md`](repository/test-design.md)） |

E2E（受入基準 16, 17）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜14 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 18 は repository sub-feature の IT で検証。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/room/` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。

## 11. 開放論点 (Open Questions)

凍結時点で未確定の論点はなし — R1 レビューで全件凍結済み。確定 R1-1〜9 として §7 に集約。

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
| セキュリティ | 業務ルール違反は早期に拒否される（Fail Fast）。`PromptKit.prefix_markdown` の Discord webhook URL / API key は `MaskedText` で永続化前マスキング（業務ルール R1-9、room §確定 G 実適用）。`RoomInvariantViolation` の例外経路での webhook URL 漏洩は webhook auto-mask で防御（多層防御） |
