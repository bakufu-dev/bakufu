# 業務仕様書（feature-spec）— LLM クライアント基盤

> feature: `llm-client`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`infrastructure/`](infrastructure/)
> 関連 Issue: [#144 feat(llm-client): 横断利用可能な LLM クライアント基盤を独立 feature として導入](https://github.com/bakufu-dev/bakufu/issues/144)
> 凍結済み設計: [`docs/design/tech-stack.md`](../../design/tech-stack.md) §LLM Adapter / [`docs/design/domain-model.md`](../../design/domain-model.md)

## 本書の役割

本書は **LLM クライアント基盤という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を「AI タスク実行に必要な LLM 呼び出し基盤」という業務概念で具体化し、呼び出し元 feature から見て **観察可能な業務ふるまい** を実装レイヤーに依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない。

**書くこと**:
- 呼び出し元 feature（ValidationService 等）がこの基盤で達成できるようになる行為（ユースケース UC-LC-NNN）
- 業務ルール（横断利用契約・エラー分類・API キー管理・タイムアウト、確定 R1-X として凍結）
- 観察可能な事象としての受入基準

**書かないこと**（後段の設計書・別ディレクトリへ追い出す）:
- SDK 統合パターン（asyncio.wait_for / _extract_text / SecretStr 等）→ sub-feature の `detailed-design.md`
- Protocol 定義・VO 型・エラー階層の属性型 → sub-feature の `basic-design.md` / `detailed-design.md`
- factory 関数の実装方針 → `infrastructure/detailed-design.md`

## 1. この feature の位置付け

LLM クライアント基盤は、**AI タスクで LLM API を HTTP で直接呼び出す横断的 Port 抽象** として定義する。bakufu の複数 feature（`ai-validation` の意味検証、将来の `directive` 自動生成、`room` 判定など）が同一インターフェースで Anthropic / OpenAI を利用できる共通基盤を提供する。

本 feature は subprocess CLI ベースの `LLMProviderPort`（coding agent 用）とは **別概念** である。両者の役割区分は [`docs/design/tech-stack.md §LLM Adapter`](../../design/tech-stack.md) §確定 LC-A に凍結する。

業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| application | [`domain/`](domain/) | `AbstractLLMClient` Port 契約 + `LLMMessage` / `LLMResponse` VO + `LLMClientError` 階層を定義。呼び出し元 Service が依存するインターフェース層 |
| infrastructure | [`infrastructure/`](infrastructure/) | Anthropic / OpenAI SDK を用いた具体実装 + Config + factory。Port 契約を実現する I/O 層 |
| ui | 該当なし — 理由: 本 feature は内部 API 基盤のみ。エンドユーザーへの直接 UI は持たない | — |

## 2. 人間の要求

> Issue #144:
>
> `ai-validation`（Issue #123）が LLM API を直接呼び出す設計だが、LLM 接続部分を単一 feature に閉じると各 feature 追加のたびに重複する（DRY 違反）。LLM クライアント基盤を独立 feature として先行設計・実装し、`ai-validation` 以降の全 feature が同一インターフェースで LLM を利用できる共通基盤を整備する。

## 3. 背景・痛点

### 現状の痛点

1. `ai-validation` 設計段階で LLM 呼び出しが feature 内に埋め込まれており、`directive` 自動生成・`room` 判定等の将来 feature が同様の実装を繰り返す構造になっている
2. タイムアウト制御・API Key 管理・`asyncio.wait_for()` パターンがコピーされると SDK 切替時（Anthropic v3 → v4 など）の修正箇所が分散する
3. `AbstractLLMClient` と `LLMProviderPort`（subprocess CLI）の役割区分が `tech-stack.md` に明文化されておらず、将来のエンジニアが「どちらを使うべきか」で混乱する

### 解決されれば変わること

- 各 feature は「何を LLM に聞くか（プロンプト設計）」だけに集中できる。SDK 統合・タイムアウト・エラーハンドリングは本 feature に集約される
- Anthropic → OpenAI 切り替え、SDK バージョンアップが 1 箇所の修正で済む
- `LLMProviderPort`（CLI subprocess）との役割区分が設計書で凍結され、新機能追加時の判断基準が明確になる

### ビジネス価値

- `ai-validation`（Issue #123）の再設計コストを削減し、正しい依存方向で実装を開始できる
- LLM 利用の横断基盤が整備されることで、AI 評価・自動生成系 feature の追加速度が向上する

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|---|---|---|---|
| Application Service 開発者 | bakufu の feature 実装者（内部）| 間接（内部 API 利用）| LLM プロバイダの詳細を知らずに `AbstractLLMClient.complete()` を呼ぶだけで AI 評価・分類を実行したい |
| bakufu オーナー（まこちゃん）| システム設定者 | 間接（設定・運用）| 環境変数で API キーを設定するだけで Anthropic / OpenAI を切り替えて動作させたい |

プロジェクト全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|---|---|---|---|---|
| UC-LC-001 | Application Service 開発者 | `AbstractLLMClient.complete(messages, max_tokens)` を呼び出すと、LLM プロバイダの詳細を知らずにテキスト応答 `LLMResponse` を受け取れる | 必須 | domain / infrastructure |
| UC-LC-002 | bakufu オーナー | 環境変数 `BAKUFU_LLM_PROVIDER` / `BAKUFU_ANTHROPIC_API_KEY` 等を設定するだけで Anthropic / OpenAI を切り替えられる | 必須 | infrastructure |
| UC-LC-003 | Application Service 開発者 | LLM 呼び出しがタイムアウト・レート制限・認証エラーで失敗した場合に `LLMClientError` サブクラスを catch して適切にハンドリングできる | 必須 | domain / infrastructure |

## 6. スコープ

### In Scope

- `AbstractLLMClient` Protocol（`application/ports/llm_client.py`）
- `LLMMessage` / `LLMResponse` Value Object
- `LLMClientError` 例外階層（`LLMTimeoutError` / `LLMRateLimitError` / `LLMAuthError` / `LLMAPIError`）
- `AnthropicLLMClient`（Anthropic SDK direct HTTP API）
- `OpenAILLMClient`（OpenAI SDK direct HTTP API）
- `LLMClientConfig`（環境変数ベース設定 VO）
- `llm_client_factory(config: LLMClientConfig) -> AbstractLLMClient`

### Out of Scope（参照）

- Gemini API 統合 → Phase 2（YAGNI。`tech-stack.md §不採用候補` に根拠）
- ストリーミング応答（`stream=True`）→ Phase 2（MVP は 1 req = 1 resp）
- Tool use / function calling → Phase 2
- subprocess CLI ベースの coding agent 接続 → `LLMProviderPort`（別概念、`tech-stack.md §LLM Adapter` 参照）
- LLM レスポンスのキャッシュ → 将来 feature（YAGNI）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: AbstractLLMClient は横断基盤 — 全 feature から利用可能

`AbstractLLMClient` は `application/ports/` に置き、bakufu 内の全 Application Service が DI で消費できる横断的 Port として定義する。単一 feature の内部実装として埋め込むことは禁止。

**理由**: DRY 原則。`ai-validation` / `directive` / 将来の feature が同一インターフェースを使う。依存方向を `application → infrastructure` に保つため `application/ports/` が適切（既存 Repository Port パターン準拠）。

### 確定 R1-2: API キーは SecretStr で管理し、ログ・永続化では絶対に平文を出力しない

`LLMClientConfig` の API キーフィールドは Pydantic `SecretStr` 型とする。ログ出力・例外メッセージ・DB 保存において `get_secret_value()` を呼ぶことは禁止。

**理由**: `docs/design/threat-model.md` §T2（秘密情報漏洩）対策。`tech-stack.md §subprocess の環境変数ハンドリング` と同一方針の HTTP API 版。

### 確定 R1-3: タイムアウト・エラーは LLMClientError 階層で分類して raise する

具体実装（AnthropicLLMClient 等）は SDK 固有の例外を `LLMClientError` サブクラスに変換して呼び出し元に返す。SDK 例外を直接 propagate させることは禁止（呼び出し元が特定 SDK に依存することを防ぐ）。

**理由**: 依存逆転原則。Application Service が Anthropic SDK の例外型を知るとプロバイダ切替時に Service も修正が必要になる。

### 確定 R1-4: 1 リクエスト = 1 レスポンス（Phase 1 はストリーミング非対応）

`complete()` の戻り値は `LLMResponse`（応答テキスト一括返却）のみ。ストリーミング API（`stream=True` / `AsyncStream`）は Phase 1 では使用しない。

**理由**: MVP 複雑度の最小化（KISS）。評価・分類タスクでは応答全文が必要なためストリーミングの利点が薄い。

### 確定 R1-5: max_tokens は呼び出し元が指定する（固定値禁止）

`complete()` のシグネチャに `max_tokens: int` を含め、呼び出し元 Service がタスクに応じた値を指定する。実装内部で固定値（例: `MAX_TOKENS = 4096`）を強制することは禁止。

**理由**: 評価タスク（512 tokens 程度）とチャットタスク（4096 tokens）で適切値が異なる。固定値にすると将来 feature の呼び出しで無駄なコスト・待ち時間が発生する。

### 確定 R1-6: LLMProviderPort（CLI subprocess）と AbstractLLMClient（HTTP API）は別概念として使い分ける

| | `LLMProviderPort` | `AbstractLLMClient` |
|---|---|---|
| 対象タスク | coding agent 実行（コード生成 / 実行）| AI 評価・分類・自然言語処理 |
| 呼び出し方式 | subprocess CLI（claude / codex）| HTTP API 直接（anthropic SDK / openai SDK）|
| セッション管理 | あり（TTL 2h / 再接続）| なし（1 req = 1 resp）|

将来エンジニアが「どちらを使うか」を判断する際の基準: **コード実行・長時間タスク → `LLMProviderPort`、短時間テキスト評価・分類 → `AbstractLLMClient`**。

**理由**: 両者を混在させると複雑度が指数的に増加する。`tech-stack.md §LLM Adapter` に役割区分を明記することで判断基準を凍結する。

## 8. 制約・前提

| 区分 | 内容 |
|---|---|
| 既存運用規約 | GitFlow / Conventional Commits / 500 行ルール |
| 依存 feature | なし（本 feature が基盤。`ai-validation` Issue #123 は本 feature 完了後に再設計）|
| 外部依存 | `anthropic` SDK（PyPI）/ `openai` SDK（PyPI）を `backend/pyproject.toml` に追加 |
| 対象 OS | macOS / Linux（subprocess CLI 非依存のため Windows でも動作可）|
| Phase 1 非サポート | Gemini API / ストリーミング / Tool use（Out of Scope）|

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 1 | `AnthropicLLMClient` / `OpenAILLMClient` が `AbstractLLMClient` Protocol を実装していることを pyright strict が保証する | UC-LC-001 | CI typecheck |
| 2 | `llm_client_factory(config)` が `BAKUFU_LLM_PROVIDER=anthropic` / `openai` で対応するクライアントを返す | UC-LC-002 | IT（pytest）|
| 3 | Anthropic API タイムアウト時に `LLMTimeoutError` が raise される | UC-LC-003 | UT（pytest + mock）|
| 4 | Anthropic API 429 応答時に `LLMRateLimitError` が raise される | UC-LC-003 | UT（pytest + mock）|
| 5 | Anthropic API 401 応答時に `LLMAuthError` が raise される | UC-LC-003 | UT（pytest + mock）|
| 6 | `LLMClientConfig.api_key` が `SecretStr` であり、`str(config)` でマスキングされる | R1-2 | UT |
| 7 | `max_tokens` を呼び出し元で指定した値が SDK に渡されている | R1-5 | UT（pytest + mock）|

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| # | 基準 | 検証方法 |
|---|---|---|
| Q-1 | 型検査 / lint がエラーゼロ（pyright strict + ruff）| CI lint / typecheck ジョブ |
| Q-2 | UT カバレッジ 80% 以上（モック使用、実際の LLM 呼び出し不要）| pytest --cov |

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | Gemini API 統合（Phase 2）追加時、`LLMClientConfig` の discriminated union 設計が必要か | Issue / 別 PR（Phase 2 着手時）|
| Q-OPEN-2 | `AnthropicLLMClient` のリトライ戦略（exponential backoff）を本 feature に含めるか、呼び出し元 Service に委ねるか | 本 PR レビューで確定 |

## 12. Sub-issue 分割計画

| Sub-issue 名 | 紐付く UC | スコープ | 依存関係 |
|---|---|---|---|
| **A**: `domain` sub-feature（Port + VO + Error 定義）| UC-LC-001, UC-LC-003 | `AbstractLLMClient` Protocol / `LLMMessage` / `LLMResponse` / `LLMClientError` 階層 | なし |
| **B**: `infrastructure` sub-feature（具体実装 + factory）| UC-LC-001, UC-LC-002, UC-LC-003 | `AnthropicLLMClient` / `OpenAILLMClient` / `LLMClientConfig` / `llm_client_factory` | A に依存（Port 定義が必要）|

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|---|---|---|
| `BAKUFU_ANTHROPIC_API_KEY` | Anthropic API キー（環境変数）| 高（`SecretStr` で管理、ログ出力禁止）|
| `BAKUFU_OPENAI_API_KEY` | OpenAI API キー（環境変数）| 高（同上）|
| LLM へのプロンプト内容 | 呼び出し元 feature から渡されるテキスト | 中（呼び出し元の機密分類に従う。本 feature は内容を永続化しない）|
| LLM からの応答テキスト | `LLMResponse.content` | 中（同上。本 feature は内容を永続化しない）|

## 14. 非機能要求

| 区分 | 要求 |
|---|---|
| パフォーマンス | `complete()` のネットワーク I/O 待機は呼び出し元が `asyncio.wait_for()` でタイムアウト制御。デフォルト 30 秒（`LLMClientConfig.timeout_seconds` で変更可）|
| 可用性 | MVP はリトライなし。呼び出し元 Service がリトライ戦略を決定する（YAGNI）|
| 可搬性 | `anthropic` / `openai` SDK の特定バージョンへの依存を本 feature に封じ込め、他 feature が SDK に直接依存しない構造を保証する |
| セキュリティ | API キーは `SecretStr` で管理（R1-2）。プロンプト内容の永続化は本 feature のスコープ外 |
