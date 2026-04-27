# テスト設計書

<!-- feature 単位で 1 ファイル。requirements.md の REQ-XX-NNN / detailed-design.md の MSG-XX-NNN / requirements-analysis.md の受入基準と T 脅威 を、それぞれ最低 1 件のテストケースで検証する。 -->
<!-- 配置先: docs/features/<feature-name>/test-design.md -->

## テストマトリクス

<!-- REQ ID と実装アーティファクトとテストケース ID を 1:N で対応付ける。マトリクスに乗らない要件は「孤児要件」として禁止。 -->

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-XX-001 | ... | TC-UT-001, TC-IT-001 | ユニット / 結合 | 正常系 / 異常系 | 1 |
| REQ-XX-002 | ... | TC-IT-002, TC-E2E-001 | 結合 / E2E | 異常系 | 2 |

## 外部 I/O 依存マップ

<!-- 外部サービス（GitHub / pypi / npm / LLM CLI / DB / OS API）の挙動を「raw fixture（実観測の凍結）」と「factory（パラメータ化されたテスト入力生成）」で扱う。assumed mock を禁じる。 -->

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| ... | ... | `tests/fixtures/characterization/raw/...` | `tests/factories/...` | 済 / **要起票 (Issue TBD-N)** |

**空欄（要起票）の扱い**: TBD-N の Issue が完了するまで、該当項目に関わる unit/integration は「assumed mock」を禁じる。外部観測値に代わる raw fixture が未整備のまま unit を書くと、仕様誤引用に対する検出力ゼロのテストになる。

## E2E テストケース

<!-- 「ペルソナの受入基準をブラックボックスで検証する」層。DB 直接確認・内部状態参照・テスト用裏口は禁止。 -->

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| TC-E2E-001 | <ペルソナ名> | <受入基準 N の検証> | 1. ... 2. ... | exit 0 / HTTP 200 / UI 表示 ... |

## 結合テストケース

<!-- 「複数モジュール間の連携」層。実 API endpoint + 実 DB（テスト用 SQLite）+ raw fixture で検証する。外部 LLM / Discord / GitHub は mock。 -->

| テストID | 対象モジュール連携 | 使用 raw fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|----------------|---------|------|---------|
| TC-IT-001 | ... | ... | ... | ... | ... |

## ユニットテストケース

<!-- 「単一クラス・単一関数の契約」層。factory 経由で入力バリエーションを網羅する。raw fixture 直読は禁止（factory 経由で正規化）。 -->

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-001 | `Aggregate.method_a()` | 正常系 | <typical input factory> | exit 0 |
| TC-UT-002 | `Aggregate.method_a()` | 異常系 | <invalid input factory> | raises `DomainException` |

## カバレッジ基準

<!-- C0/C1 等の伝統的指標 + bakufu 独自のトレーサビリティ充足 -->

- REQ-XX-001 〜 NNN の各要件が**最低 1 件**のテストケースで検証されている
- MSG-XX-001 〜 NNN の各文言が**静的文字列で照合**されている
- 受入基準 1 〜 N の各々が**最低 1 件の E2E テストケース**で検証されている
- T1 〜 TN の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている
- C0（行カバレッジ）目標: 80% 以上（domain 層は 95% 以上）

## 人間が動作確認できるタイミング

<!-- レビュワー / オーナーが PR をマージする前に手元で動作確認するための手順。 -->

- CI 統合後: `gh pr checks` で 7 ジョブ緑であること
- ローカル: `bash scripts/setup.sh` → `just check-all` → 該当 feature 固有の確認コマンド

## テストディレクトリ構造

```
tests/
  fixtures/
    characterization/
      raw/
        <upstream-source>_<version>.<ext>
      schema/
        (raw の型 + 統計。factory 設計ソース)
  factories/
    <factory-name>.py / <factory-name>.ts
  e2e/
    test_<scenario>.py
  integration/
    test_<module-pair>.py
  unit/
    test_<unit>.py
```

## 未決課題・要起票 characterization task

| # | タスク | 起票先 |
|---|-------|--------|
| TBD-1 | ... | Issue（実装着手後に着手） |
