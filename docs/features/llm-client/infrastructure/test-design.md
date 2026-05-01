# テスト設計書 — llm-client / infrastructure

<!-- feature: llm-client / sub-feature: infrastructure -->
<!-- 配置先: docs/features/llm-client/infrastructure/test-design.md -->
<!-- 対象範囲: REQ-LC-011〜014 / AnthropicLLMClient / OpenAILLMClient / LLMClientConfig / llm_client_factory / MSG-LC-007〜009 + MSG-LC-001〜006（再掲）-->

本 sub-feature は `AnthropicLLMClient` / `OpenAILLMClient` / `LLMClientConfig` / `llm_client_factory` の infrastructure 実装群を対象とする。**外部 LLM API（Anthropic / OpenAI）** への HTTP 呼び出しが外部 I/O の核心であり、テスト実装着手前に **characterization fixture の取得を必須** とする。

**Characterization 先行ルール**: `AnthropicLLMClient` / `OpenAILLMClient` が依存する LLM API の raw fixture が `tests/fixtures/characterization/raw/llm_client/` に存在しない状態でユニット / 結合テストの実装に着手することを禁止する。先に §Characterization 計画の task を完了させること。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 親 spec 受入基準 |
|--------|-------------------|---------------|------------|------|----------------|
| REQ-LC-011（AnthropicLLMClient.complete 正常系）| `AnthropicLLMClient.complete` | TC-UT-AC-001 | ユニット | 正常系 | AC#1 |
| REQ-LC-011（AnthropicLLMClient.complete 異常系 — 全エラー変換）| `AnthropicLLMClient.complete` | TC-UT-AC-002〜005 | ユニット | 異常系 | AC#3, 4, 5 |
| REQ-LC-011（_extract_text — TextBlock あり / なし）| `AnthropicLLMClient._extract_text` | TC-UT-AC-006〜007 | ユニット | 正常系 / 境界値 | AC#1 |
| REQ-LC-011（_convert_messages — system 分離 §確定F）| `AnthropicLLMClient._convert_messages` | TC-UT-AC-008〜011 | ユニット | 正常系 / 異常系 / 境界値 | §確定F |
| REQ-LC-011（max_tokens が SDK にそのまま渡される — R1-5 物理確認）| `AnthropicLLMClient.complete` | TC-UT-AC-012 | ユニット | 正常系 | R1-5 |
| REQ-LC-012（OpenAILLMClient.complete 正常系）| `OpenAILLMClient.complete` | TC-UT-OC-001 | ユニット | 正常系 | AC#1 |
| REQ-LC-012（OpenAILLMClient.complete 異常系 — 全エラー変換）| `OpenAILLMClient.complete` | TC-UT-OC-002〜005 | ユニット | 異常系 | AC#3, 4, 5 |
| REQ-LC-012（_extract_text — content あり / None）| `OpenAILLMClient._extract_text` | TC-UT-OC-006〜007 | ユニット | 正常系 / 境界値 | AC#1 |
| REQ-LC-012（_convert_messages — system role を messages に含めてよい）| `OpenAILLMClient._convert_messages` | TC-UT-OC-008 | ユニット | 正常系 | §確定F |
| REQ-LC-013（LLMClientConfig 正常構築 — anthropic）| `LLMClientConfig` | TC-UT-CONF-001 | ユニット | 正常系 | AC#6 |
| REQ-LC-013（LLMClientConfig 正常構築 — openai）| `LLMClientConfig` | TC-UT-CONF-002 | ユニット | 正常系 | UC-LC-002 |
| REQ-LC-013（BAKUFU_LLM_PROVIDER 未設定 → Fail Fast）| `LLMClientConfig` | TC-UT-CONF-003 | ユニット | 異常系 | — |
| REQ-LC-013（対応プロバイダ API キー未設定 → Fail Fast）| `LLMClientConfig` | TC-UT-CONF-004〜005 | ユニット | 異常系 | — |
| REQ-LC-013（SecretStr マスキング — R1-2）| `LLMClientConfig` | TC-UT-CONF-006 | ユニット | 正常系 | AC#6 |
| REQ-LC-013（timeout_seconds デフォルト 30.0）| `LLMClientConfig` | TC-UT-CONF-007 | ユニット | 境界値 | §確定A |
| REQ-LC-013（model_name デフォルト — §確定C）| `LLMClientConfig` | TC-UT-CONF-008 | ユニット | 正常系 | §確定C |
| REQ-LC-014（llm_client_factory — anthropic）| `llm_client_factory` | TC-UT-FAC-001 | ユニット | 正常系 | AC#2 |
| REQ-LC-014（llm_client_factory — openai）| `llm_client_factory` | TC-UT-FAC-002 | ユニット | 正常系 | AC#2 |
| REQ-LC-014（未知プロバイダ → LLMConfigError — MSG-LC-009）| `llm_client_factory` | TC-UT-FAC-003 | ユニット | 異常系 | — |
| REQ-LC-014（factory 返り値が AbstractLLMClient Protocol を満たす）| `llm_client_factory` | TC-UT-FAC-004 | ユニット | 正常系 | AC#1 |
| MSG-LC-007〜009（[FAIL] プレフィックス + プレースホルダ）| `LLMClientConfig` / `llm_client_factory` | TC-UT-MSG-007〜009 | ユニット | 異常系 | — |
| §確定 A（asyncio.wait_for タイムアウト変換）| `AnthropicLLMClient.complete` | TC-UT-AC-002 | ユニット | 異常系 | §確定A |
| §確定 E（LLMAPIError.raw_error はマスキング済み — T2）| `AnthropicLLMClient.complete` / `OpenAILLMClient.complete` | TC-UT-SEC-001〜002 | ユニット | 異常系 | §確定E |
| R1-2（str(config) で API キーが露出しない）| `LLMClientConfig` | TC-UT-CONF-006 | ユニット | 正常系 | R1-2 |
| §確定 G（__init__.py の公開 API 制限）| `infrastructure/llm/__init__.py` | TC-UT-INIT-001 | ユニット | 正常系 | §確定G |
| 結合（factory → Anthropic client → complete — raw fixture 使用）| `llm_client_factory` + `AnthropicLLMClient` | TC-IT-LC-001 | 結合 | 正常系 | AC#1, 2 |
| 結合（factory → OpenAI client → complete — raw fixture 使用）| `llm_client_factory` + `OpenAILLMClient` | TC-IT-LC-002 | 結合 | 正常系 | AC#1, 2 |
| 結合（provider 切り替え確認）| `LLMClientConfig` + `llm_client_factory` | TC-IT-LC-003 | 結合 | 正常系 | UC-LC-002 |

**マトリクス充足の証拠**:

- REQ-LC-011〜014 すべてに最低 1 件のテストケース
- **エラー変換 4 種（Timeout / RateLimit / Auth / APIError）** を AnthropicLLMClient / OpenAILLMClient の両クライアントで網羅（TC-UT-AC-002〜005 / TC-UT-OC-002〜005）
- **§確定 A（asyncio.wait_for）**: TC-UT-AC-002 で `asyncio.TimeoutError` → `LLMTimeoutError` 変換を物理確認
- **§確定 C（デフォルトモデル名）**: TC-UT-CONF-008 で Anthropic / OpenAI 各プロバイダのデフォルトモデル名を物理確認
- **§確定 E（raw_error マスキング）**: TC-UT-SEC-001〜002 で `LLMAPIError.raw_error` に API キー文字列が含まれないことを物理確認
- **§確定 F（Anthropic system 分離）**: TC-UT-AC-008〜011 で system role 分離 / 複数 system 結合 / system のみ Fail Fast を全パターン網羅
- **R1-5（max_tokens 固定値禁止）**: TC-UT-AC-012 で呼び出し元が指定した `max_tokens` が SDK にそのまま渡されることを物理確認
- **§確定 G（公開 API 制限）**: TC-UT-INIT-001 で `AnthropicLLMClient` / `OpenAILLMClient` が `__init__.py` から直接 export されていないことを物理確認
- **MSG-LC-007〜009 プレフィックス物理保証**: TC-UT-MSG-007〜009 で CI 強制
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **Anthropic API** (`anthropic.AsyncAnthropic.messages.create`)| `AnthropicLLMClient.complete` — 正常応答 | `tests/fixtures/characterization/raw/llm_client/anthropic_complete_success.json` | `AnthropicSDKResponseFactory.build(content='...')` | **要起票** — §未決課題 #1 参照。raw + schema 取得前に UT/IT 実装着手禁止 |
| **Anthropic API**（エラー応答）| 同上 — RateLimitError / AuthenticationError / APIError 応答形式の確認 | `tests/fixtures/characterization/raw/llm_client/anthropic_error_rate_limit.json` / `anthropic_error_auth.json` / `anthropic_error_api.json` | `AnthropicSDKResponseFactory.build_error(kind='rate_limit' / 'auth' / 'api')` | **要起票** |
| **OpenAI API** (`openai.AsyncOpenAI.chat.completions.create`)| `OpenAILLMClient.complete` — 正常応答 | `tests/fixtures/characterization/raw/llm_client/openai_complete_success.json` | `OpenAISDKResponseFactory.build(content='...')` | **要起票** |
| **OpenAI API**（エラー応答）| 同上 — RateLimitError / AuthenticationError / APIError 応答形式の確認 | `tests/fixtures/characterization/raw/llm_client/openai_error_rate_limit.json` / `openai_error_auth.json` / `openai_error_api.json` | `OpenAISDKResponseFactory.build_error(kind='rate_limit' / 'auth' / 'api')` | **要起票** |
| **環境変数** (`BAKUFU_LLM_PROVIDER` 等)| `LLMClientConfig` 構築 | — | `monkeypatch.setenv` で制御 | **不要** |

**ユニットテストでのモック方針**: 全ての SDK 呼び出し（`AsyncAnthropic.messages.create` / `AsyncOpenAI.chat.completions.create`）は `AsyncMock` でスタブ化。返却値は `AnthropicSDKResponseFactory` / `OpenAISDKResponseFactory`（schema 由来）を使用。インライン辞書リテラルは禁止。

**結合テストでのモック方針**: SDK クライアントを raw fixture でスタブ化（`AsyncMock.return_value` に raw fixture の JSON を SDK レスポンスオブジェクトとして注入）。factory 由来データを結合テストで使うことは禁止。

## Characterization 計画

LLM API（Anthropic / OpenAI）の raw fixture を取得する。`RUN_CHARACTERIZATION=1` 環境変数が設定された場合のみ実行（本流 CI から除外）。

### 取得対象 raw fixture

| ファイルパス | 取得対象 API | 取得内容 |
|-----------|------------|--------|
| `tests/fixtures/characterization/raw/llm_client/anthropic_complete_success.json` | Anthropic `messages.create` | 正常応答（`content: [TextBlock(type='text', text='...')]` 形式） |
| `tests/fixtures/characterization/raw/llm_client/anthropic_error_rate_limit.json` | 同上 | HTTP 429 応答時の SDK 例外オブジェクト（`str()` 後マスク済み）+ エラーメタ |
| `tests/fixtures/characterization/raw/llm_client/anthropic_error_auth.json` | 同上 | HTTP 401 応答時 |
| `tests/fixtures/characterization/raw/llm_client/anthropic_error_api.json` | 同上 | HTTP 5xx 応答時 |
| `tests/fixtures/characterization/raw/llm_client/openai_complete_success.json` | OpenAI `chat.completions.create` | 正常応答（`choices[0].message.content` 形式） |
| `tests/fixtures/characterization/raw/llm_client/openai_error_rate_limit.json` | 同上 | HTTP 429 応答時 |
| `tests/fixtures/characterization/raw/llm_client/openai_error_auth.json` | 同上 | HTTP 401 応答時 |
| `tests/fixtures/characterization/raw/llm_client/openai_error_api.json` | 同上 | HTTP 5xx 応答時 |

### raw fixture 形式要件

- `_meta.captured_at`（ISO 8601 UTC）/ `_meta.endpoint` / `_meta.api_version` / `_meta.sdk_version` を必ず含む
- API キーを含むヘッダー / フィールドはマスク済み（例: `"api_key": "sk-***"`)
- エラー応答の `message` フィールドに API キーが含まれる場合は構造保存型マスク

### schema ファイル

| ファイルパス | 内容 |
|-----------|------|
| `tests/fixtures/characterization/schema/llm_client/anthropic_complete.json.schema` | Anthropic 正常応答の型 + 統計（TextBlock 件数分布・`stop_reason` 出現頻度）|
| `tests/fixtures/characterization/schema/llm_client/anthropic_error.json.schema` | エラー応答の型 + エラークラス名出現頻度 |
| `tests/fixtures/characterization/schema/llm_client/openai_complete.json.schema` | OpenAI 正常応答の型 + 統計（`finish_reason` 出現頻度）|
| `tests/fixtures/characterization/schema/llm_client/openai_error.json.schema` | OpenAI エラー応答の型 |

### factory 設計方針

| factory / ファクトリメソッド | 出力 | `_meta.synthetic` |
|---|---|---|
| `AnthropicSDKResponseFactory.build(content='合成応答テキスト')` | Anthropic SDK `Message` オブジェクト相当（`content=[TextBlock(text=content)]`）。schema 由来の構造 | `True`（`_meta.synthetic=True` を meta 属性に注入）|
| `AnthropicSDKResponseFactory.build_no_text_block()` | TextBlock を持たない Anthropic 応答オブジェクト（tool_use block のみ等）| `True` |
| `OpenAISDKResponseFactory.build(content='合成応答テキスト')` | OpenAI `ChatCompletion` オブジェクト相当（`choices[0].message.content=content`）| `True` |
| `OpenAISDKResponseFactory.build_null_content()` | `choices[0].message.content == None` の OpenAI 応答 | `True` |

## 結合テストケース

SDK クライアントは raw fixture で mock（`AsyncMock.return_value`）。環境変数は `monkeypatch.setenv` で制御。

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-IT-LC-001 | `llm_client_factory` → `AnthropicLLMClient` → `complete`（raw fixture 使用）| 正常系 | `BAKUFU_LLM_PROVIDER=anthropic` 設定済み。`anthropic_complete_success.json`（raw fixture）を SDK mock の return_value に設定 | 1) `LLMClientConfig()` で config 構築 → 2) `llm_client_factory(config)` → 3) `client.complete(messages, max_tokens=512)` | `LLMResponse` が返り `content` が非空。raw fixture の text block テキストと一致 |
| TC-IT-LC-002 | `llm_client_factory` → `OpenAILLMClient` → `complete`（raw fixture 使用）| 正常系 | `BAKUFU_LLM_PROVIDER=openai` 設定済み。`openai_complete_success.json`（raw fixture）を SDK mock の return_value に設定 | 同上 | `LLMResponse` が返り `content` が非空。raw fixture の `choices[0].message.content` と一致 |
| TC-IT-LC-003 | プロバイダ切り替え確認（anthropic → openai）| 正常系 | `monkeypatch` で `BAKUFU_LLM_PROVIDER` を途中で切り替え | 1) `PROVIDER=anthropic` で `llm_client_factory` → `AnthropicLLMClient` インスタンス → 2) `PROVIDER=openai` で `llm_client_factory` → `OpenAILLMClient` インスタンス | プロバイダごとに異なるクライアントクラスのインスタンスが返る。`isinstance(client, AnthropicLLMClient)` / `isinstance(client, OpenAILLMClient)` で区別可能（factory 経由の型確認）|

## ユニットテストケース

SDK は `AsyncMock` でスタブ化。返却値は factory 由来のみ。

### AnthropicLLMClient（test_anthropic_llm_client.py）

#### complete 正常系・異常系

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-AC-001 | `complete` 正常系 | 正常系 | SDK mock が `AnthropicSDKResponseFactory.build(content='合格')` を返す | `complete((user_msg,), max_tokens=512)` | `LLMResponse(content='合格')` |
| TC-UT-AC-002 | `asyncio.TimeoutError` → `LLMTimeoutError`（§確定A）| 異常系 | SDK mock が `asyncio.TimeoutError` を raise | `complete((user_msg,), max_tokens=512)` | `LLMTimeoutError(timeout_seconds=30.0, provider='anthropic')` が raise。`LLMClientError` として catch 可能 |
| TC-UT-AC-003 | `anthropic.RateLimitError` → `LLMRateLimitError` | 異常系 | SDK mock が `anthropic.RateLimitError` を raise（`retry_after=60` 付き）| 同上 | `LLMRateLimitError(retry_after=60.0, provider='anthropic')` |
| TC-UT-AC-004 | `anthropic.AuthenticationError` → `LLMAuthError` | 異常系 | SDK mock が `anthropic.AuthenticationError` を raise | 同上 | `LLMAuthError(provider='anthropic')` |
| TC-UT-AC-005 | その他 `anthropic.APIError` → `LLMAPIError`（raw_error はマスキング済み）| 異常系 | SDK mock が `anthropic.APIError(status_code=503)` を raise | 同上 | `LLMAPIError(status_code=503, provider='anthropic')` が raise。`exc.raw_error` に API キー文字列が含まれない（T2 / §確定E）|

#### _extract_text

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AC-006 | `_extract_text` — TextBlock あり | 正常系 | `AnthropicSDKResponseFactory.build(content='テキスト応答')` | `'テキスト応答'` が返る |
| TC-UT-AC-007 | `_extract_text` — TextBlock なし → MSG-LC-006 + フォールバック | 境界値 | `AnthropicSDKResponseFactory.build_no_text_block()` | `LLM_FALLBACK_RESPONSE_TEXT`（`"(LLM returned no text response)"`）が返る。MSG-LC-006 が `logger.warning` で出力される |

#### _convert_messages（§確定F Anthropic system 分離）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AC-008 | `_convert_messages` — system + user → system 引数に分離 | 正常系 | `(SYSTEM:'評価者役割指示', USER:'成果物テキスト')` | `system == '評価者役割指示'` かつ `messages == [{'role': 'user', 'content': '成果物テキスト'}]` |
| TC-UT-AC-009 | `_convert_messages` — system メッセージ 2 件 → 改行 `\n\n` で結合 | 境界値 | `(SYSTEM:'指示1', SYSTEM:'指示2', USER:'内容')` | `system == '指示1\n\n指示2'` かつ `messages` に system なし |
| TC-UT-AC-010 | `_convert_messages` — system なし → system パラメータ渡さない | 正常系 | `(USER:'内容のみ',)` | `system is None` かつ `messages == [{'role': 'user', 'content': '内容のみ'}]` |
| TC-UT-AC-011 | `_convert_messages` — system のみ（user なし）→ Fail Fast | 異常系 | `(SYSTEM:'指示のみ',)` | `LLMMessageValidationError`（system 除外後に messages リストが空になるため Fail Fast） |

#### R1-5 物理確認（max_tokens 固定値禁止）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-AC-012 | `max_tokens=256` が SDK call にそのまま渡される（固定値上書き禁止）| 正常系 | `complete((user_msg,), max_tokens=256)` で SDK mock の `messages.create` を call | `sdk_mock.messages.create.call_args.kwargs['max_tokens'] == 256` で物理確認。`max_tokens` が内部で固定値に変更されていないことを assert |

### OpenAILLMClient（test_openai_llm_client.py）

| テストID | 対象 | 種別 | 前提条件 | 操作 | 期待結果 |
|---------|-----|------|---------|------|---------|
| TC-UT-OC-001 | `complete` 正常系 | 正常系 | SDK mock が `OpenAISDKResponseFactory.build(content='応答')` を返す | `complete((user_msg,), max_tokens=1024)` | `LLMResponse(content='応答')` |
| TC-UT-OC-002 | `asyncio.TimeoutError` → `LLMTimeoutError` | 異常系 | SDK mock が `asyncio.TimeoutError` を raise | `complete` 呼び出し | `LLMTimeoutError(provider='openai')` |
| TC-UT-OC-003 | `openai.RateLimitError` → `LLMRateLimitError` | 異常系 | SDK mock が `openai.RateLimitError` を raise | 同上 | `LLMRateLimitError(provider='openai')` |
| TC-UT-OC-004 | `openai.AuthenticationError` → `LLMAuthError` | 異常系 | SDK mock が `openai.AuthenticationError` を raise | 同上 | `LLMAuthError(provider='openai')` |
| TC-UT-OC-005 | その他 `openai.APIError` → `LLMAPIError` | 異常系 | SDK mock が `openai.APIError(status_code=500)` を raise | 同上 | `LLMAPIError(status_code=500, provider='openai')` |
| TC-UT-OC-006 | `_extract_text` — `choices[0].message.content` あり | 正常系 | `OpenAISDKResponseFactory.build(content='結果テキスト')` | `'結果テキスト'` が返る |
| TC-UT-OC-007 | `_extract_text` — content が None → フォールバック | 境界値 | `OpenAISDKResponseFactory.build_null_content()` | `LLM_FALLBACK_RESPONSE_TEXT` が返る。MSG-LC-006 がログ出力される |
| TC-UT-OC-008 | `_convert_messages` — system role を messages に含めてよい（OpenAI 仕様）| 正常系 | `(SYSTEM:'指示', USER:'内容')` | `messages == [{'role': 'system', 'content': '指示'}, {'role': 'user', 'content': '内容'}]`（Anthropic とは異なり system 分離しない）|

### LLMClientConfig（test_config.py）

| テストID | 対象 | 種別 | 入力（環境変数）| 期待結果 |
|---------|-----|------|-------------|---------|
| TC-UT-CONF-001 | 正常構築（provider=anthropic）| 正常系 | `LLM_PROVIDER=anthropic, ANTHROPIC_API_KEY=sk-test, LLM_MODEL_NAME=claude-3-5-sonnet-20241022` | `config.provider == LLMProviderEnum.ANTHROPIC` |
| TC-UT-CONF-002 | 正常構築（provider=openai）| 正常系 | `LLM_PROVIDER=openai, OPENAI_API_KEY=sk-test, LLM_MODEL_NAME=gpt-4o-mini` | `config.provider == LLMProviderEnum.OPENAI` |
| TC-UT-CONF-003 | `BAKUFU_LLM_PROVIDER` 未設定 → Fail Fast（MSG-LC-007）| 異常系 | `LLM_PROVIDER` なし | `pydantic.ValidationError` または `LLMConfigError`（設計決定に従う）。アプリ起動前に検出 |
| TC-UT-CONF-004 | `provider=anthropic` + `ANTHROPIC_API_KEY` 未設定 → Fail Fast（MSG-LC-008）| 異常系 | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` なし | `LLMConfigError(MSG-LC-008)` |
| TC-UT-CONF-005 | `provider=openai` + `OPENAI_API_KEY` 未設定 → Fail Fast（MSG-LC-008）| 異常系 | `LLM_PROVIDER=openai`, `OPENAI_API_KEY` なし | `LLMConfigError(MSG-LC-008)` |
| TC-UT-CONF-006 | `SecretStr` マスキング（R1-2）— `str(config)` で API キーが露出しない | 正常系 | `ANTHROPIC_API_KEY=sk-realkey-secret123` | `str(config)` の出力に `sk-realkey-secret123` が含まれない。`repr(config.anthropic_api_key)` が `SecretStr('**********')` 相当 |
| TC-UT-CONF-007 | `timeout_seconds` デフォルト = 30.0（§確定A）| 境界値 | `LLM_TIMEOUT_SECONDS` 未設定 | `config.timeout_seconds == 30.0` |
| TC-UT-CONF-008 | `model_name` デフォルト値（§確定C）| 正常系 | `LLM_PROVIDER=anthropic`, `LLM_MODEL_NAME` 未設定 | `config.model_name == 'claude-3-5-sonnet-20241022'`（Anthropic デフォルト確定値）|

### llm_client_factory（test_factory.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-FAC-001 | `provider=anthropic` → `AnthropicLLMClient` を返す | 正常系 | `config.provider = LLMProviderEnum.ANTHROPIC` | `type(client).__name__ == 'AnthropicLLMClient'` |
| TC-UT-FAC-002 | `provider=openai` → `OpenAILLMClient` を返す | 正常系 | `config.provider = LLMProviderEnum.OPENAI` | `type(client).__name__ == 'OpenAILLMClient'` |
| TC-UT-FAC-003 | 未知のプロバイダ → `LLMConfigError`（MSG-LC-009）| 異常系 | `LLMProviderEnum` に存在しない値を強制設定（テスト内部でのみ）| `LLMConfigError` が raise される。`exc.message` に `[FAIL]` と未知プロバイダ名が含まれる |
| TC-UT-FAC-004 | factory 返り値が `AbstractLLMClient` Protocol を満たす | 正常系 | `provider=anthropic` で `llm_client_factory(config)` | `hasattr(client, 'complete')` かつ `asyncio.iscoroutinefunction(client.complete)` で Protocol 適合を実行時確認 |

### MSG 確定文言（test_messages.py）

| テストID | 対象 MSG | 発生条件 | 検証内容 |
|---------|---------|---------|---------|
| TC-UT-MSG-007 | MSG-LC-007（PROVIDER 未設定）| `LLMClientConfig` 構築時に `BAKUFU_LLM_PROVIDER` なし | エラーメッセージに `[FAIL]` と `BAKUFU_LLM_PROVIDER` が含まれる |
| TC-UT-MSG-008 | MSG-LC-008（API キー未設定）| `provider=anthropic` + `ANTHROPIC_API_KEY` なし | エラーメッセージに `[FAIL]` と `provider={provider}` の展開済み値と `BAKUFU_ANTHROPIC_API_KEY` が含まれる |
| TC-UT-MSG-009 | MSG-LC-009（未知プロバイダ）| `llm_client_factory` に未知プロバイダ config を渡す | エラーメッセージに `[FAIL]` と `anthropic, openai` がサポート対象として含まれる |

### セキュリティ — §確定E / T2（test_security.py）

| テストID | 対象 | 種別 | 発生条件 | 検証内容 |
|---------|-----|------|---------|---------|
| TC-UT-SEC-001 | `LLMAPIError.raw_error` に API キーが含まれない（Anthropic）| 異常系 | `BAKUFU_ANTHROPIC_API_KEY=sk-realkey-secret` を設定した `AnthropicLLMClient` が `anthropic.APIError` を catch | `exc.raw_error` を検査し `sk-realkey-secret` が含まれない。`masking.mask_secrets()` 相当の処理が経由されていることを assert |
| TC-UT-SEC-002 | `LLMAPIError.raw_error` に API キーが含まれない（OpenAI）| 異常系 | `BAKUFU_OPENAI_API_KEY=sk-realkey-secret` を設定した `OpenAILLMClient` が `openai.APIError` を catch | 同上（OpenAI 版）|

### §確定G 公開 API 制限（test_init.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-INIT-001 | `AnthropicLLMClient` / `OpenAILLMClient` が `__init__.py` から直接 import できない | 正常系 | `from bakufu.infrastructure.llm import AnthropicLLMClient` を試みる | `ImportError` または `AttributeError`（`__init__.py` が export していないため）。factory 経由のみが正規ルートであることを物理確認 |

## カバレッジ基準

- REQ-LC-011〜014 すべてに最低 1 件のテストケース
- **エラー変換 4 種（Timeout / RateLimit / Auth / APIError）** を Anthropic / OpenAI 両クライアントで物理確認（TC-UT-AC-002〜005 / TC-UT-OC-002〜005）
- **§確定 A（asyncio.wait_for 変換）**: TC-UT-AC-002 / TC-UT-OC-002 で物理確認
- **§確定 C（デフォルトモデル名）**: TC-UT-CONF-008 で物理確認
- **§確定 E（raw_error マスキング）**: TC-UT-SEC-001〜002 で物理確認
- **§確定 F（Anthropic system 分離全パターン）**: TC-UT-AC-008〜011 で 4 パターン全網羅（分離 / 複数結合 / system なし / system のみ Fail Fast）
- **§確定 G（公開 API 制限）**: TC-UT-INIT-001 で物理確認
- **R1-5（max_tokens 固定値禁止）**: TC-UT-AC-012 で SDK call args を直接検証して物理確認
- **MSG-LC-007〜009 全プレフィックス + プレースホルダ展開**: TC-UT-MSG-007〜009 で CI 強制
- C0 目標: `infrastructure/llm/` 配下の全モジュールで **90% 以上**

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で typecheck / lint / test-backend 全ジョブが緑
- ローカル（ユニット）: `cd backend && uv run pytest tests/unit/infrastructure/llm/ -v` → 全緑
- ローカル（結合）: `cd backend && uv run pytest tests/integration/infrastructure/llm/ -v` → 全緑
- プロバイダ切り替えの目視確認: `BAKUFU_LLM_PROVIDER=openai BAKUFU_OPENAI_API_KEY=... python -c "from bakufu.infrastructure.llm import llm_client_factory, LLMClientConfig; c = llm_client_factory(LLMClientConfig()); print(type(c).__name__)"` → `OpenAILLMClient` が出力される
- API キーマスク確認: `str(config)` で `**` 表示されることを目視

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      llm_sdk_response.py             # AnthropicSDKResponseFactory / OpenAISDKResponseFactory
    fixtures/
      characterization/
        raw/
          llm_client/
            anthropic_complete_success.json   # 要起票
            anthropic_error_rate_limit.json
            anthropic_error_auth.json
            anthropic_error_api.json
            openai_complete_success.json      # 要起票
            openai_error_rate_limit.json
            openai_error_auth.json
            openai_error_api.json
        schema/
          llm_client/
            anthropic_complete.json.schema    # 要起票
            anthropic_error.json.schema
            openai_complete.json.schema       # 要起票
            openai_error.json.schema
    characterization/
      test_llm_client_characterization.py    # RUN_CHARACTERIZATION=1 で実行。本流 CI 除外
    unit/
      infrastructure/
        llm/
          __init__.py
          test_anthropic_llm_client.py       # TC-UT-AC-001〜012
          test_openai_llm_client.py          # TC-UT-OC-001〜008
          test_config.py                     # TC-UT-CONF-001〜008
          test_factory.py                    # TC-UT-FAC-001〜004
          test_messages.py                   # TC-UT-MSG-007〜009
          test_security.py                   # TC-UT-SEC-001〜002
          test_init.py                       # TC-UT-INIT-001
    integration/
      infrastructure/
        llm/
          __init__.py
          test_llm_client_integration.py     # TC-IT-LC-001〜003（raw fixture + monkeypatch）
```

## 未決課題・要起票 characterization task

| # | タスク | 優先度 | 着手条件 | 備考 |
|---|-------|-------|---------|------|
| #1 | **LLM Client Characterization fixture 取得**（最優先・ブロッカー）| **最優先** | `BAKUFU_ANTHROPIC_API_KEY` および `BAKUFU_OPENAI_API_KEY` が利用可能な環境 | Anthropic + OpenAI 両プロバイダ × 正常 + エラー 4 種 = 計 8 raw fixture + 4 schema を `RUN_CHARACTERIZATION=1 pytest tests/characterization/test_llm_client_characterization.py` で取得。取得前に UT / IT の実装を開始してはならない |
| #2 | `masking.mask_secrets()` の仕様確認 — `LLMAPIError.raw_error` に API キーが含まれる前提で `mask_secrets()` がどの文字列をマスクするかを確認し、TC-UT-SEC-001〜002 の assert 条件を確定させる | 高 | UT 実装前 | `bakufu.infrastructure.security.masking` モジュールが存在しない場合は先に起票 |
| #3 | `BAKUFU_LLM_MODEL_NAME` 未設定時のデフォルト値選択ロジック確認 — `provider=anthropic` 時は `claude-3-5-sonnet-20241022`、`provider=openai` 時は `gpt-4o-mini` を返すべきかを実装前に確定させる（TC-UT-CONF-008 の前提）| 中 | UT 実装前 | `LLMClientConfig.model_name` のデフォルト値が provider によって異なる場合、factory 側での制御か config 側での制御かを確定すること |

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-LC-011〜014 すべてに最低 1 件のテストケース（孤児要件ゼロ）
- [ ] **エラー変換 4 種（Timeout / RateLimit / Auth / APIError）** を Anthropic / OpenAI 両クライアントで網羅（TC-UT-AC-002〜005 / TC-UT-OC-002〜005）
- [ ] **§確定 A（asyncio.wait_for 変換）**: TC-UT-AC-002 / TC-UT-OC-002 で物理確認
- [ ] **§確定 E（raw_error マスキング）**: TC-UT-SEC-001〜002 で API キー非混入を物理確認
- [ ] **§確定 F（Anthropic system 分離全 4 パターン）**: TC-UT-AC-008〜011 で網羅
- [ ] **§確定 G（公開 API 制限）**: TC-UT-INIT-001 で `AnthropicLLMClient` 直接 import 不可を物理確認
- [ ] **R1-5（max_tokens 固定値禁止）**: TC-UT-AC-012 で SDK call args を直接検証
- [ ] **MSG-LC-007〜009 プレフィックス + プレースホルダ**: TC-UT-MSG-007〜009 で CI 強制
- [ ] 外部 I/O 依存マップの全項目が「済」または「不要」になっている（LLM API raw fixture が「要起票」のまま実装着手は却下）
- [ ] ユニットテストで raw fixture を直接読んでいない（factory 経由必須）
- [ ] 結合テストで factory 由来合成データを使っていない（raw fixture のみ）
- [ ] `_meta.synthetic: True` が factory 出力に埋め込まれている
- [ ] raw fixture に `_meta.captured_at` / `endpoint` / `api_version` / `sdk_version` が存在する
- [ ] Anthropic / OpenAI の `_convert_messages` の差分（system 分離あり / なし）が独立ケースで網羅
