# テスト設計書 — llm-client / domain

<!-- feature: llm-client / sub-feature: domain -->
<!-- 配置先: docs/features/llm-client/domain/test-design.md -->
<!-- 対象範囲: REQ-LC-001〜003 / LLMMessage / LLMResponse / MessageRole / LLMClientError 階層 / AbstractLLMClient Protocol / MSG-LC-001〜006 -->

本 sub-feature は `AbstractLLMClient` Protocol・`LLMMessage` / `LLMResponse` frozen VO・`MessageRole` StrEnum・`LLMClientError` 例外階層の型定義層に閉じる。**外部 I/O ゼロ**（SDK 非依存・DB なし・ネットワークなし）のため characterization fixture は不要。純粋な型・不変条件・例外階層の検証が主体。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 親 spec 受入基準 |
|--------|-------------------|---------------|------------|------|----------------|
| REQ-LC-001（AbstractLLMClient Protocol 定義）| `AbstractLLMClient` / `application/ports/llm_client.py` | TC-UT-PROTO-001〜002 | ユニット | 正常系 | AC#1 |
| REQ-LC-002（LLMMessage 構築・バリデーション）| `LLMMessage` + `MessageRole` | TC-UT-LM-001〜006 | ユニット | 正常系 / 異常系 | — |
| REQ-LC-002（LLMMessageValidationError）| `LLMMessage.content` empty | TC-UT-LM-004 | ユニット | 異常系 | — |
| REQ-LC-003（LLMResponse 構築）| `LLMResponse` | TC-UT-RESP-001〜003 | ユニット | 正常系 / 境界値 | — |
| REQ-LC-003（空文字フォールバック: infrastructure 責務）| `LLMResponse` | TC-UT-RESP-002 | ユニット | 境界値 | REQ-LC-003 |
| `LLMClientError` 基底クラス + サブクラス 4 種 | `domain/errors.py` | TC-UT-ERR-001〜011 | ユニット | 正常系 / 異常系 | AC#3, 4, 5 |
| `MessageRole` StrEnum（§確定C: `.value` 変換不要）| `MessageRole` | TC-UT-ROLE-001〜003 | ユニット | 正常系 | §確定C |
| MSG-LC-001〜006（[FAIL]/[WARN] プレフィックス + プレースホルダ）| `LLMClientError` 各サブクラス | TC-UT-MSG-001〜006 | ユニット | 正常系 | R1-3 |
| §確定B（LLMResponse が session_id / compacted を持たない）| `LLMResponse` | TC-UT-RESP-004 | ユニット | 正常系 | §確定B |
| R1-2（API キー SecretStr: domain 層は import しない）| `application/ports/llm_client.py` | TC-UT-PROTO-003 | ユニット | 正常系 | R1-2 |
| 結合シナリオ 1（LLMMessage タプル → stub complete → LLMResponse）| AbstractLLMClient stub 実装 | TC-IT-DOMAIN-001 | 結合 | 正常系 | UC-LC-001 |
| 結合シナリオ 2（エラー経路 stub → LLMClientError 伝播）| AbstractLLMClient stub 実装 | TC-IT-DOMAIN-002 | 結合 | 異常系 | UC-LC-003 |

**マトリクス充足の証拠**:

- REQ-LC-001〜003 すべてに最低 1 件のテストケース
- **MessageRole 3 値全種**（SYSTEM / USER / ASSISTANT）が TC-UT-ROLE-001〜003 で網羅
- **LLMClientError 5 サブクラス全種**の is-a 関係と追加属性を TC-UT-ERR-001〜011 で網羅
- **§確定 B（session_id 非存在）**: TC-UT-RESP-004 で LLMResponse が ai-team `ChatResult` 互換フィールドを持たないことを物理確認
- **§確定 C（StrEnum 文字列等価）**: TC-UT-ROLE-001〜003 で `MessageRole.USER == "user"` を物理確認。SDK 渡し時に `.value` 変換が不要であることを実証
- **MSG-LC-001〜006 プレフィックス物理保証**: TC-UT-MSG-001〜006 で全 MSG が `[FAIL]` / `[WARN]` で始まりプレースホルダが展開されることを CI 強制
- **R1-2 domain 層 SDK 非依存**: TC-UT-PROTO-003 で `application/ports/llm_client.py` が `anthropic` / `openai` を import していないことを物理確認
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | `AbstractLLMClient` Protocol / `LLMMessage` / `LLMResponse` / `LLMClientError` は外部 I/O を一切持たない（SDK import ゼロ）| — | — | **不要（外部 I/O ゼロ）** |

factory の `_meta.synthetic = True` 付与ルールは本 sub-feature でも適用する（既存 domain sub-feature 同パターン）。

**factory（合成データ）**:

| factory / ファクトリメソッド | 出力 | `_meta.synthetic` |
|---|---|---|
| `LLMMessageFactory.build(role=MessageRole.USER, content='テストメッセージ')` | `LLMMessage`（frozen）| `True` |
| `LLMResponseFactory.build(content='テスト応答テキスト')` | `LLMResponse`（frozen）| `True` |
| `StubLLMClientFactory.build(response=...)` | `AbstractLLMClient` Protocol を満たす `AsyncMock` stub。`complete()` が指定 `LLMResponse` を返す | `True` |
| `StubLLMClientFactory.build_raises(exc=LLMTimeoutError(...))` | `complete()` が指定例外を raise する stub | `True` |

## 結合テストケース

domain 層単独のため「結合」は **Protocol stub + VO 連携 + lifecycle 完走シナリオ** と定義。外部 I/O ゼロ。

| テストID | 対象モジュール連携 | 使用 factory | 前提条件 | 操作 | 期待結果 |
|---------|-----------------|------------|---------|------|---------|
| TC-IT-DOMAIN-001 | AbstractLLMClient stub + LLMMessage タプル → complete → LLMResponse | StubLLMClientFactory + LLMMessageFactory + LLMResponseFactory | stub が `LLMResponseFactory.build()` を返すよう設定 | 1) `LLMMessage` × 2 件（SYSTEM + USER）をタプルにして stub.complete(messages, max_tokens=512) を呼ぶ | `LLMResponse` が返り、`content` が factory の値と一致。stub が実際に `complete` を 1 度呼ばれたことを `assert_called_once` で確認 |
| TC-IT-DOMAIN-002 | AbstractLLMClient stub エラー経路 → LLMClientError 伝播 | StubLLMClientFactory + LLMMessageFactory | stub が `LLMTimeoutError(message=..., provider='anthropic', timeout_seconds=30.0)` を raise するよう設定 | stub.complete(messages, max_tokens=512) を呼ぶ | `LLMTimeoutError` が呼び出し元に伝播する。`LLMClientError` として catch 可能（is-a 確認）|

## ユニットテストケース

### AbstractLLMClient Protocol（test_protocol.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-PROTO-001 | Protocol を満たす最小 stub が Protocol 型として機能する | 正常系 | `complete(messages, max_tokens)` を実装した stub クラス | pyright strict が `AbstractLLMClient` として型チェック通過（CI の typecheck ジョブで保証。runtime では `isinstance` チェックしない — 設計方針通り）|
| TC-UT-PROTO-002 | `complete` のシグネチャ検証（tuple[LLMMessage, ...], int → LLMResponse）| 正常系 | stub の `complete` に正しい型引数を渡す | 型エラーなし。戻り値が `LLMResponse` 型 |
| TC-UT-PROTO-003 | `application/ports/llm_client.py` が `anthropic` / `openai` を import していない（R1-2 domain SDK 非依存）| 正常系 | `importlib` / `ast.parse` 等で `llm_client.py` のソースを検査 | `"anthropic"` / `"openai"` 文字列が import 文に含まれない。domain 層の SDK ゼロ依存を物理確認 |

### LLMMessage VO（test_value_objects.py）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-LM-001 | `LLMMessage` 正常構築（role=USER）| 正常系 | `role=MessageRole.USER, content='こんにちは'` | 構築成功。`message.role == MessageRole.USER`, `message.content == 'こんにちは'` |
| TC-UT-LM-002 | `LLMMessage` 正常構築（role=SYSTEM）| 正常系 | `role=MessageRole.SYSTEM, content='You are...'` | 構築成功 |
| TC-UT-LM-003 | `LLMMessage` 正常構築（role=ASSISTANT）| 正常系 | `role=MessageRole.ASSISTANT, content='了解です'` | 構築成功 |
| TC-UT-LM-004 | `content` 空文字 → バリデーション失敗 | 異常系 | `role=MessageRole.USER, content=''` | `pydantic.ValidationError`（`min_length=1` 制約違反）|
| TC-UT-LM-005 | frozen 不変性 | 異常系 | `message.content = '変更'` 直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）|
| TC-UT-LM-006 | extra='forbid' | 異常系 | `LLMMessage.model_validate({..., 'extra_field': 'x'})` | `pydantic.ValidationError`（extra 違反）|

### LLMResponse VO（test_value_objects.py に同梱）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RESP-001 | `LLMResponse` 正常構築（non-empty content）| 正常系 | `content='評価結果テキスト'` | 構築成功 |
| TC-UT-RESP-002 | `LLMResponse` は空文字を受け付ける（infrastructure がフォールバック責務を持つ）| 境界値 | `content=''` | 構築成功。domain VO 自体は空文字を拒否しない（REQ-LC-003 設計方針確認）|
| TC-UT-RESP-003 | frozen 不変性 | 異常系 | `response.content = '変更'` 直接代入 | `pydantic.ValidationError` |
| TC-UT-RESP-004 | §確定B: `session_id` / `compacted` フィールドを持たない | 正常系 | `LLMResponse` インスタンスを inspect | `hasattr(response, 'session_id')` が `False`、`hasattr(response, 'compacted')` が `False` |

### MessageRole StrEnum（§確定C 物理確認）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-ROLE-001 | `MessageRole.USER == "user"`（§確定C: SDK に渡す際に `.value` 変換不要）| 正常系 | `MessageRole.USER == "user"` | `True` |
| TC-UT-ROLE-002 | `MessageRole.SYSTEM == "system"` | 正常系 | `MessageRole.SYSTEM == "system"` | `True` |
| TC-UT-ROLE-003 | `MessageRole.ASSISTANT == "assistant"` | 正常系 | `MessageRole.ASSISTANT == "assistant"` | `True` |

### LLMClientError 例外階層（test_errors.py）

#### is-a 関係 + 追加属性

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-ERR-001 | `LLMTimeoutError` は `LLMClientError` のサブクラス | 正常系 | `isinstance(LLMTimeoutError(...), LLMClientError)` | `True` |
| TC-UT-ERR-002 | `LLMRateLimitError` は `LLMClientError` のサブクラス | 正常系 | `isinstance(LLMRateLimitError(...), LLMClientError)` | `True` |
| TC-UT-ERR-003 | `LLMAuthError` は `LLMClientError` のサブクラス | 正常系 | `isinstance(LLMAuthError(...), LLMClientError)` | `True` |
| TC-UT-ERR-004 | `LLMAPIError` は `LLMClientError` のサブクラス | 正常系 | `isinstance(LLMAPIError(...), LLMClientError)` | `True` |
| TC-UT-ERR-005 | `LLMMessageValidationError` は `LLMClientError` のサブクラス | 正常系 | `isinstance(LLMMessageValidationError(...), LLMClientError)` | `True` |
| TC-UT-ERR-006 | `LLMTimeoutError.timeout_seconds` を持つ | 正常系 | `LLMTimeoutError(message='...', provider='anthropic', timeout_seconds=30.0)` | `exc.timeout_seconds == 30.0` |
| TC-UT-ERR-007 | `LLMRateLimitError.retry_after` が None | 正常系 | `LLMRateLimitError(message='...', provider='anthropic', retry_after=None)` | `exc.retry_after is None` |
| TC-UT-ERR-008 | `LLMRateLimitError.retry_after` が float | 正常系 | `LLMRateLimitError(message='...', provider='anthropic', retry_after=60.0)` | `exc.retry_after == 60.0` |
| TC-UT-ERR-009 | `LLMAPIError.status_code` / `raw_error` を持つ | 正常系 | `LLMAPIError(message='...', provider='openai', status_code=500, raw_error='masked error')` | `exc.status_code == 500`, `exc.raw_error == 'masked error'` |
| TC-UT-ERR-010 | `LLMAPIError.status_code` が None | 境界値 | `LLMAPIError(..., status_code=None, raw_error='...')` | `exc.status_code is None` |
| TC-UT-ERR-011 | `LLMMessageValidationError.field` を持つ | 正常系 | `LLMMessageValidationError(message='...', provider='anthropic', field='content')` | `exc.field == 'content'` |

### MSG 確定文言 / プレフィックス物理保証（test_messages.py）

| テストID | 対象 MSG | 例外型 | 発生条件 | 検証内容 |
|---------|---------|-------|---------|---------|
| TC-UT-MSG-001 | MSG-LC-001（LLMTimeoutError）| `LLMTimeoutError` | `timeout_seconds=30.0`, `provider='anthropic'` | `exc.message.startswith('[FAIL]')` かつ `'30.0' in exc.message` かつ `'anthropic' in exc.message` |
| TC-UT-MSG-002 | MSG-LC-002（LLMRateLimitError）| `LLMRateLimitError` | `retry_after=60.0`, `provider='anthropic'` | `exc.message.startswith('[FAIL]')` かつ `'60.0' in exc.message` かつ `'anthropic' in exc.message` |
| TC-UT-MSG-003 | MSG-LC-003（LLMAuthError）| `LLMAuthError` | `provider='openai'` | `exc.message.startswith('[FAIL]')` かつ `'openai' in exc.message` かつ `'API key' in exc.message`（設定確認を促す文言）|
| TC-UT-MSG-004 | MSG-LC-004（LLMAPIError）| `LLMAPIError` | `provider='anthropic', status_code=503` | `exc.message.startswith('[FAIL]')` かつ `'503' in exc.message` かつ `'anthropic' in exc.message` |
| TC-UT-MSG-005 | MSG-LC-005（LLMMessageValidationError）| `LLMMessageValidationError` | `field='content'` | `exc.message.startswith('[FAIL]')` かつ `'content' in exc.message` |
| TC-UT-MSG-006 | MSG-LC-006（[WARN] フォールバック）— ログ文言 | `str` 文言検証 | MSG-LC-006 の確定文言文字列を直接検証 | `'[WARN]' in MSG_LC_006_TEXT` かつ `'no text blocks' in MSG_LC_006_TEXT` |

## E2E テストケース

E2E は親 [`../system-test-design.md`](../system-test-design.md) が管理する。本 sub-feature（domain Port 定義）は外部 I/O を持たないため E2E テストケースは定義しない。

## カバレッジ基準

- REQ-LC-001〜003 すべてに最低 1 件のテストケース
- **MessageRole 3 値全種** SYSTEM / USER / ASSISTANT が TC-UT-LM-001〜003 で正常構築、TC-UT-ROLE-001〜003 で StrEnum 等価を物理確認
- **LLMClientError 5 サブクラス全種** の is-a 関係と追加属性を TC-UT-ERR-001〜011 で網羅
- **§確定 B（session_id 非存在）**: TC-UT-RESP-004 で物理確認
- **§確定 C（StrEnum == 文字列）**: TC-UT-ROLE-001〜003 で物理確認
- **R1-2 domain SDK 非依存**: TC-UT-PROTO-003 で `anthropic` / `openai` import なしを物理確認
- **MSG-LC-001〜006 プレフィックス物理保証**: TC-UT-MSG-001〜006 で CI 強制
- **frozen 不変性**: LLMMessage / LLMResponse 両 VO で独立検証
- **LLMResponse 空文字許容（infrastructure フォールバック責務）**: TC-UT-RESP-002 で物理確認

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で typecheck / lint / test-backend ジョブが緑
- ローカル: `cd backend && uv run pytest tests/unit/domain/llm_client/ -v` → 全テスト緑
- Protocol 準拠の確認: `uv run pyright backend/src/bakufu/application/ports/llm_client.py` で strict モード通過
- SDK 非依存の目視確認: `grep -n 'anthropic\|openai' backend/src/bakufu/application/ports/llm_client.py` → マッチなし

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      llm_client.py           # LLMMessageFactory / LLMResponseFactory / StubLLMClientFactory
    unit/
      domain/
        llm_client/
          __init__.py
          test_protocol.py    # TC-UT-PROTO-001〜003
          test_value_objects.py  # TC-UT-LM-001〜006 / TC-UT-RESP-001〜004 / TC-UT-ROLE-001〜003
          test_errors.py      # TC-UT-ERR-001〜011
          test_messages.py    # TC-UT-MSG-001〜006
      integration/
        domain/
          llm_client/
            __init__.py
            test_protocol_integration.py  # TC-IT-DOMAIN-001〜002（stub + VO 連携）
```

## 未決課題・要起票

| # | タスク | 優先度 | 備考 |
|---|-------|-------|------|
| #1 | `domain/value_objects.py` / `domain/errors.py` が既存ファイルへの **追記** であることを実装前に確認（既存VO・例外との命名衝突チェック）| 高 | 実装 PR 前に grep で確認 |
| #2 | `LLM_FALLBACK_RESPONSE_TEXT` 定数（§確定D）が `domain/value_objects.py` に定義され、infrastructure が参照していることを TC-IT-DOMAIN-001 で確認 | 中 | 定数が重複定義されていないかを確認 |

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-LC-001〜003 すべてに最低 1 件のテストケース
- [ ] **MessageRole 3 値全種** が構築正常系で網羅
- [ ] **LLMClientError 5 サブクラス** の is-a 関係と追加属性が全種網羅（TC-UT-ERR-001〜011）
- [ ] **§確定 B（session_id 非存在）**: TC-UT-RESP-004 で物理確認
- [ ] **§確定 C（StrEnum 文字列等価）**: TC-UT-ROLE-001〜003 で物理確認
- [ ] **R1-2 domain SDK 非依存**: TC-UT-PROTO-003 で `anthropic` / `openai` import なしを物理確認
- [ ] **MSG-LC-001〜006 全プレフィックス + プレースホルダ展開**: TC-UT-MSG-001〜006 で CI 強制
- [ ] frozen 不変性 / extra='forbid' が LLMMessage / LLMResponse 両 VO で独立検証
- [ ] LLMResponse 空文字許容（TC-UT-RESP-002）で infrastructure フォールバック責務が domain VO に誤って混入していないことを確認
