# テスト設計書

> feature: `<feature-name>` / sub-feature: `<sub-feature>`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)

## 本書の役割

本書は **テストケースで検証可能な単位までトレーサビリティを担保する**。basic-design.md §モジュール契約 の REQ-XX-NNN / detailed-design.md の MSG-XX-NNN / 親 feature-spec.md の受入基準・脅威 を、それぞれ最低 1 件のテストケースで検証する。

**書くこと**:
- REQ-XX-NNN / MSG-XX-NNN / 受入基準 # / T 脅威 # を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（raw fixture / factory / characterization 状態）
- 各レベルのテストケース定義
- カバレッジ基準

**書かないこと**:
- システムテスト → 親 [`../system-test-design.md`](../system-test-design.md)
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-XX-001 | \<実装ファイル\> | TC-UT-XX-001, TC-IT-XX-001 | ユニット / 結合 | 正常系 / 異常系 | feature-spec.md §9 #N |
| REQ-XX-002 | ... | ... | ... | ... | ... |
| MSG-XX-001 | \<例外 message\> | TC-UT-XX-NNN | ユニット | 異常系 | — |
| T1 | \<対策\> | TC-UT-XX-NNN | ユニット | 異常系 | — |

**マトリクス充足の証拠**:
- REQ-XX-001 〜 NNN すべてに最低 1 件のテストケース
- MSG-XX-001 〜 NNN すべてに静的文字列照合
- 親受入基準 1 〜 N の各々がシステムテスト（[`../system-test-design.md`](../system-test-design.md)）または結合テストで検証
- T1 〜 TN すべてに有効性確認ケース
- 孤児要件（マトリクス外要件）なし

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | テスト戦略 |
|---|---|---|---|---|
| \<DB\> | \<永続化\> | `tests/fixtures/...` | `tests/factories/...` | 実 DB（テスト用 tempfile） |
| \<外部 API\> | \<連携\> | — | — | Mock / fake adapter |

## 結合テストケース

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---|---|---|---|---|---|
| TC-IT-XX-001 | ... | ... | ... | ... | ... |

## ユニットテストケース

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---|---|---|---|---|
| TC-UT-XX-001 | \<クラス.メソッド\> | 正常系 | \<入力\> | \<期待\> |
| TC-UT-XX-002 | ... | 異常系 | \<不正入力\> | raises \<DomainException\> |

## カバレッジ基準

- REQ-XX-001 〜 NNN の各要件が **最低 1 件** のテストケースで検証されている
- MSG-XX-001 〜 NNN の各文言が **静的文字列で照合** されている
- 親受入基準（[`../feature-spec.md §9`](../feature-spec.md)）の各々がシステムテストまたは結合テストで検証されている（システムテストは [`../system-test-design.md`](../system-test-design.md) で別途凍結）
- T1 〜 TN の各脅威に対する対策が **最低 1 件のテストケース** で有効性を確認されている
- 行カバレッジ目標: \<例: 80% 以上\>

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑であること
- ローカル: \<セットアップコマンド\> → \<テストコマンド\>

## テストディレクトリ構造

```
backend/tests/
├── fixtures/
│   └── characterization/
├── factories/
│   └── \<factory-name\>.py
├── unit/
│   └── test_<feature-name>_<sub-feature>.py
└── integration/
    └── test_<feature-name>_<sub-feature>.py
```

## 未決課題・要起票 characterization task

| # | タスク | 起票先 |
|---|---|---|
| TBD-1 | ... | Issue（実装着手後に着手） |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ ID）
- [`detailed-design.md`](detailed-design.md) — MSG 確定文言
- [`../feature-spec.md`](../feature-spec.md) — 親業務仕様（受入基準）
- [`../system-test-design.md`](../system-test-design.md) — システムテスト（feature 内）
