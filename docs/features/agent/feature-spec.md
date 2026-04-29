# 業務仕様書（feature-spec）— Agent

> feature: `agent`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | [`http-api/`](http-api/)（Issue #59）| ui（将来）
> 関連 Issue: [#10 feat(agent): Agent Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/10) / [#32 feat(agent-repository): Agent SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/32) / [#59 feat(agent-http-api): Agent CRUD HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/59)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Agent / [`value-objects.md`](../../design/domain-model/value-objects.md) §Agent 構成要素

## 本書の役割

本書は **Agent という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Agent という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が Agent という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（不変条件・容量上限・プロバイダ一意・スキル参照・永続性 等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy / FastAPI 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / delete-then-insert / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）

## 1. この feature の位置付け

bakufu インスタンスの組織（Empire）に採用された AI エージェント「Agent」を、ペルソナ（個人開発者 CEO）が役割分担付きで運用できる業務概念として定義する。Agent は Persona（キャラクター設定）/ Role（役割テンプレ）/ LLM プロバイダ設定を持つ採用済み AI エージェントであり、Room の `members` に紐づく中核 Aggregate。

Agent の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | Agent の構造的整合性（不変条件・容量・プロバイダ一意・スキル参照）を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | Agent の状態を再起動跨ぎで保持（永続化）、Persona.prompt_body の secret マスキングを担保 |
| http-api | [`http-api/`](http-api/)（Issue #59） | UI / 外部クライアントから Agent を操作・取得する REST API 経路（Persona.prompt_body を HTTP レスポンスで masked 返却） |
| ui | (将来) | CEO が Agent を直感的に編成する画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #10（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の一環として **Agent Aggregate Root** を実装する。Agent は Persona / Role / LLM プロバイダ設定を持つ採用済み AI エージェントで、Room の `members` に紐づく中核 Aggregate。

> Issue #32（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の後続 Repository PR（empire-repository #25 のテンプレート責務継承）。**Agent Aggregate** の SQLite 永続化を実装する。**Schneier 申し送り #3（`Persona.prompt_body` Repository マスキング）の実適用が本 PR の核心**。

## 3. 背景・痛点

### 現状の痛点

1. bakufu の核心思想「複数 AI エージェントの役割分担」は Agent Aggregate なしには実現できない。Persona / Role / Provider 設定を 1 つの整合性ある単位として扱う Aggregate が必要
2. M1 後段の `room` / `task` Issue は AgentMembership を介して Agent を参照する設計。Agent が無いと Room の `members` を構築できない
3. CEO が Agent を採用しても再起動で状態が消えるなら、業務として成立しない（Agent 採用は持続的な組織概念）
4. **Schneier 申し送り #3**: `Persona.prompt_body` に API key / GitHub PAT が混入した場合、Repository 経由での DB 永続化時に raw 流出する経路が残っている

### 解決されれば変わること

- CEO が Agent を採用し、Persona / Role / Provider を設定して組織に組み込める
- Agent の状態がアプリ再起動を跨いで保持される（CEO は永続化を意識しない）
- `Persona.prompt_body` に CEO が誤って API key / GitHub PAT を貼り付けても DB には `<REDACTED:*>` で永続化（**Schneier 申し送り #3 完了**）

### ビジネス価値

- bakufu の差別化「Persona 注入による Agent の個性化」が Aggregate 単位で扱えるようになる
- マルチプロバイダ対応（Claude Code / Codex / Gemini 等）の切替経路が実装可能になる

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | 直接（将来の UI 経由）/ 間接（domain・repository sub-feature では application 層経由） | Agent を採用し、Persona / Role / Provider を設定してチームに組み込み、再起動跨ぎで状態が保持される |

bakufu システム全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-AG-001 | CEO | Agent を採用できる（Persona / Role / Provider を設定して valid な Agent を構築する）| 必須 | domain |
| UC-AG-002 | CEO | Agent の LLM プロバイダ（既定）を切り替えられる | 必須 | domain |
| UC-AG-003 | CEO | Agent にスキルを追加・削除できる | 必須 | domain |
| UC-AG-004 | CEO | Agent をアーカイブできる（物理削除なし）| 必須 | domain |
| UC-AG-005 | CEO | 業務ルール違反（重複・容量・不変条件違反）の操作が拒否され、Agent 状態は変化しない | 必須 | domain |
| UC-AG-006 | CEO | 採用した Agent の状態がアプリ再起動を跨いで保持される（永続化を意識しない）| 必須 | repository |
| UC-AG-007 | CEO | 同 Empire 内で Agent 名は一意でなければならない（重複採用は拒否される）| 必須 | repository（find_by_name 提供）+ application 層（強制） |
| UC-AG-008 | CEO | HTTP API 経由で Empire に Agent を採用できる（POST /api/empires/{empire_id}/agents） | 必須 | http-api |
| UC-AG-009 | CEO | HTTP API 経由で Empire に属する Agent 一覧を取得できる（GET /api/empires/{empire_id}/agents） | 必須 | http-api |
| UC-AG-010 | CEO | HTTP API 経由で特定 Agent の詳細を取得できる（GET /api/agents/{id}）。Persona.prompt_body は masked 値で返却される（業務ルール R1-9） | 必須 | http-api |
| UC-AG-011 | CEO | HTTP API 経由で Agent の Persona / Role / Provider / Skills を更新できる（PATCH /api/agents/{id}）。providers / skills は非 null 指定時に全置換される | 必須 | http-api |
| UC-AG-012 | CEO | HTTP API 経由で Agent をアーカイブできる（DELETE /api/agents/{id}）。アーカイブ済み Agent への更新は拒否される | 必須 | http-api |

## 6. スコープ

### In Scope

- Agent 業務概念全体で観察可能な業務ふるまい（UC-AG-001〜012）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)
- Agent の HTTP CRUD API（Issue #59）— `agent/http-api/` sub-feature（[`basic-design.md`](http-api/basic-design.md) / [`detailed-design.md`](http-api/detailed-design.md)）

### Out of Scope（参照）

- Agent の管理 UI → 将来の `agent/ui/` sub-feature
- Agent の管理 CLI → 別 feature `feature/admin-cli`（横断的）
- Room / Task との結合（AgentMembership 等） → `feature/room` / `feature/task`
- 永続化基盤の汎用責務（WAL / マイグレーション / masking gateway） → [`feature/persistence-foundation`](../persistence-foundation/)
- LLM Adapter（Agent の Persona を LLM に送信する経路） → 将来の `feature/llm-adapter`
- 「Empire 内 name 一意」の application 層強制 → 将来の `feature/agent-service`（domain と repository の合間に位置）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: Agent 名は 1〜40 文字、空白のみは無効

**理由**: CEO が認識可能な表示名であること。NFC 正規化 + strip 後の Unicode コードポイント数で判定。詳細は [`domain/detailed-design.md §確定 E`](domain/detailed-design.md)。

### 確定 R1-2: providers は 1 件以上、上限 10 件、`provider_kind` 重複なし

**理由**: Agent は必ず LLM プロバイダを持つ。同一プロバイダで複数モデル設定を可能にするため、List 構造で `provider_kind` 重複を禁止。MVP 運用想定規模（1〜3 プロバイダ）の数倍を上限として設定。

### 確定 R1-3: providers のうち `is_default == True` は ちょうど 1 件

**理由**: LLM Adapter が「現在の既定プロバイダ」を一意に決定できるようにする。0 件は LLM 呼び出し不能、2 件以上は非決定的選択の原因になる。これは Aggregate 内不変条件として強制する。

### 確定 R1-4: skills は上限 20 件、`skill_id` 重複なし

**理由**: MVP の実用範囲（1 Agent あたり 5 スキル程度）の数倍を上限に設定。MVP では Skill は Markdown プロンプトの参照のみ（Phase 2 で実体化）。

### 確定 R1-5: アーカイブされた Agent は物理削除しない

**理由**: 監査可能性。過去に採用した Agent の履歴を audit_log（後段 feature）から参照する際、物理削除すると `agent_id` が解決できなくなる。アーカイブは「論理削除フラグ + 履歴保持」とする。

### 確定 R1-6: 同 Empire 内の Agent 名は一意

**理由**: CEO が「役割の重複」に気付かず採用すると、業務上の責任分担が曖昧になる。この不変条件は **Aggregate 外部の集合知識**（同 Empire 内の他 Agent との比較を要する）のため、application 層 `AgentService.hire()` が `AgentRepository.find_by_name(empire_id, name)` 経由で判定する。Aggregate 自身は自分の name の一意性を知らない設計。

### 確定 R1-7: Agent の状態は再起動跨ぎで保持される

**理由**: Agent 採用は持続的な組織概念であり、アプリ再起動による状態消失は業務として許容できない。永続化は CEO から意識されない透明な責務。

### 確定 R1-8: `Persona.prompt_body` は永続化前にシークレットマスキングを適用する

**理由**: CEO が persona 設計時に `prompt_body` に API key / GitHub PAT を誤って含めた場合、DB 直読み / バックアップ / 監査ログ経路への raw token 流出を防ぐ（**Schneier 申し送り #3 実適用**）。domain 層は raw 文字列を保持し、Repository 層の `MaskedText` TypeDecorator 経由で INSERT/UPDATE 前にマスキングを適用する。

### 確定 R1-9: `Persona.prompt_body` は HTTP API レスポンスで masked 値を返す

**理由**: HTTP レスポンスを受信する全クライアント（外部ツール / ログ / ブラウザキャッシュ等）への raw token 流出を防ぐ。DB への永続化マスキング（R1-8）と独立した防御層として設計する。

- **field_serializer 全パス発火（凍結）**: `PersonaResponse.prompt_body` の `field_serializer` は GET / POST / PATCH 全レスポンスパスで発火する。これが R1-9 の独立防御として機能する根拠である
- **POST / PATCH レスポンス**: in-memory `Persona.prompt_body`（raw 値）を `field_serializer` 経由で `ApplicationMasking.mask(value)` を呼び出して伏字化して返す
- **GET レスポンス**: DB 復元済みの masked 値（`<REDACTED:*>`）に同じ `ApplicationMasking.mask()` を適用する。`ApplicationMasking.mask()` は冪等（`<REDACTED:*>` → `<REDACTED:*>`）のため見た目上は変化しないが、**R1-9 として field_serializer が独立して発火している**。これにより DB に raw token が直接挿入されるバイパス経路が発生しても GET レスポンスには raw token が露出しない
- **masking 関数の配置（凍結）**: `application/security/masking.py` として application 層に昇格。`PersonaResponse.field_serializer` は `from bakufu.application.security.masking import ApplicationMasking` で呼び出す（公開関数 alias なし、interfaces → infrastructure 直接依存なし。TC-UT-AGH-009 の `bakufu.infrastructure` 禁止制約を維持）
- **結果**: いずれの HTTP 経路でも raw API key / token が HTTP レスポンスに現れない。R1-8（永続化 masking）と R1-9（HTTP レスポンス masking）は独立した二重防御を構成する

`prompt_body` は pydantic regex 制約なしのフリーテキストのため、masked 値を保持した Agent に対して `AgentRepository.find_by_id` が `pydantic.ValidationError` を起こすことはない（**workflow R1-16 の EXTERNAL_REVIEW Stage 問題とは構造的に異なる**）。

実装詳細: [`http-api/detailed-design.md §確定A-masking / §確定I`](http-api/detailed-design.md) で凍結。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Agent 業務概念は外部通信を持たない（永続化はローカル SQLite） |
| 依存 feature | M1 開始時点: chore #7 マージ済み / M2 開始時点: M1 `agent/domain` + [`feature/persistence-foundation`](../persistence-foundation/) マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | valid な Agent が構築でき、Persona / Role / Provider / Skills を持つ | UC-AG-001 | TC-UT-AG-001（[`domain/test-design.md`](domain/test-design.md)） |
| 2 | name が業務ルール R1-1（1〜40 文字、空白のみ無効）に違反する Agent は構築できない | UC-AG-005 | TC-UT-AG-002 |
| 3 | providers に `is_default == True` が 0 件で構築しようとすると拒否される | UC-AG-005 | TC-UT-AG-003 |
| 4 | providers に `is_default == True` が 2 件以上で構築しようとすると拒否される | UC-AG-005 | TC-UT-AG-004 |
| 5 | `set_default_provider` で既定プロバイダが切り替わり、他は False になる | UC-AG-002 | TC-UT-AG-005 |
| 6 | 存在しない `provider_kind` での `set_default_provider` は拒否される | UC-AG-005 | TC-UT-AG-006 |
| 7 | `add_skill` でスキルを追加でき、重複 skill_id は拒否される | UC-AG-003 | TC-UT-AG-007, 008 |
| 8 | `remove_skill` でスキルを削除でき、未登録 skill_id は拒否される | UC-AG-003 | TC-UT-AG-009 |
| 9 | `archive()` で `archived = True` の新 Agent が返る（冪等） | UC-AG-004 | TC-UT-AG-010, 020 |
| 10 | 採用した Agent の状態がアプリ再起動跨ぎで保持される（業務ルール R1-7） | UC-AG-006 | TC-E2E-AG-001（[`system-test-design.md`](system-test-design.md)） |
| 11 | 同 Empire 内で同名 Agent を採用しようとすると拒否される（業務ルール R1-6） | UC-AG-007 | TC-E2E-AG-002 |
| 12 | `Persona.prompt_body` に API key を含めて永続化すると DB には `<REDACTED:*>` で保存される（業務ルール R1-8）| UC-AG-006 | TC-IT-AGR-006-masking（[`repository/test-design.md`](repository/test-design.md)） |
| 13 | HTTP API POST /api/empires/{empire_id}/agents で Agent が採用でき 201 が返る。レスポンスの `persona.prompt_body` は masked 値で返る（業務ルール R1-9） | UC-AG-008 | TC-E2E-AG-004（[`system-test-design.md`](system-test-design.md)） |
| 14 | HTTP API GET /api/empires/{empire_id}/agents で Empire に属する Agent 一覧が返る | UC-AG-009 | TC-E2E-AG-004 |
| 15 | HTTP API GET /api/agents/{id} レスポンスの `persona.prompt_body` は masked 値（`<REDACTED:*>`）で返る（業務ルール R1-9） | UC-AG-010 | TC-E2E-AG-004 |
| 16 | HTTP API PATCH /api/agents/{id} でフィールドを部分更新でき、レスポンスの `persona.prompt_body` は masked で返る（R1-9） | UC-AG-011 | TC-E2E-AG-004 |
| 17 | HTTP API DELETE /api/agents/{id} でアーカイブされ 204 が返る。アーカイブ後の PATCH は 409 で拒否される | UC-AG-012 | TC-E2E-AG-004 |
| 18 | HTTP API 経由で採用した Agent の状態がアプリ再起動跨ぎで保持される（R1-7 + R1-9 の複合確認） | UC-AG-008, UC-AG-010 | TC-E2E-AG-004 |

E2E（受入基準 10, 11, 13〜18）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜9 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 12 は repository sub-feature の IT で検証。受入基準 13〜18 は TC-E2E-AG-004 で検証（http-api sub-feature が完成した時点で実行可能）。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/agent.py` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。

## 11. 開放論点 (Open Questions)

業務ルール R1 レベルの論点はなし — R1-1〜9 全件が §7 に凍結済み。

実装レベルの開放論点は `http-api/detailed-design.md §開放論点` に分離して管理する（Q-OPEN-1: archived フィルタクエリパラメータ / Q-OPEN-3: 個別 provider / skill CRUD API）。これらは業務概念への変更を伴わないため本書の更新対象外。masking 関数の配置（旧 Q-OPEN-2）は本 PR で `application/security/masking.py` 昇格として凍結済み（`detailed-design.md §確定I`）。

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Agent.name | "ダリオ" / "イーロン" 等の表示名 | 低 |
| Persona.display_name | Agent の表示名 | 低 |
| Persona.archetype | "イーロン・マスク風 CEO" 等のキャラクター説明 | 低 |
| Persona.prompt_body | LLM システムプロンプト（自然言語） | **中**（API key / GitHub PAT が混入し得る、Schneier #3 実適用、Repository 層でマスキング必須） |
| ProviderConfig.model | "sonnet" / "gpt-5-codex" 等 | 低 |
| SkillRef.path | スキル markdown ファイルパス | 低（H1〜H10 検証で path traversal 防御済み） |
| 永続化テーブル群（agents / agent_providers / agent_skills） | 上記の永続化先 | 低（`agents.prompt_body` のみ MaskedText、その他は masking 対象なし） |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 業務ふるまい呼び出しの応答が CEO 視点で「即時」（数 ms 以内）と感じられること。MVP 想定規模（providers ≤ 10、skills ≤ 20）で domain 層 1ms 未満、永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも Agent 状態が破損しない |
| 可搬性 | 純 Python のみ。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | 業務ルール違反は早期に拒否される（Fail Fast）。`Persona.prompt_body` の API key / GitHub PAT は `MaskedText` で永続化前マスキング（業務ルール R1-8、Schneier 申し送り #3 実適用）。SkillRef.path の path traversal 防御は VO レベル（H1〜H10）+ 将来の `feature/skill-loader` での realpath 解決で Defense in Depth |
