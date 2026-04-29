# システムテスト設計書 — dev-workflow

> feature: `dev-workflow`
> Vモデル階層: 階層 2（feature 業務概念）
> 親 spec: [`feature-spec.md`](feature-spec.md) §9 受入基準 1〜13 / §10 Q-1〜Q-6

## E2E テスト戦略

本 feature は CLI / Git 操作 / CI ワークフロー で構成される。E2E は「開発者ペルソナがリポジトリを clone してフックを有効化し、実際にコミット / push を行う」シナリオで定義する。

### E2E テストの位置付け

- 単体（unit）: 設定ファイル・スクリプトの単体契約（TC-UT-001〜018）→ `domain/test-design.md §ユニットテストケース`
- 結合（integration）: フック配線 × レシピ連携（TC-IT-001〜011）→ `domain/test-design.md §結合テストケース`
- **E2E**: 開発者ペルソナによるブラックボックス検証（TC-E2E-001〜012）→ 本書 + `domain/test-design.md §E2Eテストケース`

### E2E シナリオ一覧

| テストID | ペルソナ | シナリオ概要 | 対応受入基準 |
|---------|---------|-----------|------------|
| TC-E2E-001 | 鎌田 大樹（Linux） | clone → setup → 通常コミット成功 | #1, #2, #10 |
| TC-E2E-002 | 鎌田 大樹 | format 違反コミットを pre-commit が遮断 | #2, #11 |
| TC-E2E-003 | 鎌田 大樹 | Conventional Commits 違反を commit-msg が遮断 | #4, #11 |
| TC-E2E-004 | 鎌田 大樹 | テスト失敗を pre-push が遮断 | #3 |
| TC-E2E-005 | 春日 結衣 | `--no-verify` バイパスを CI 側で検知 | #8 |
| TC-E2E-006 | 鎌田 大樹 | setup スクリプト 2 回連続実行で差分なし | #6 |
| TC-E2E-007 | Windows 開発者 | PowerShell 5.1 起動で即 Fail Fast | #13 |
| TC-E2E-008 | 鎌田 大樹 | secret 混入コミットを pre-commit が遮断 | #12 |
| TC-E2E-009 | 鎌田 大樹 | SHA256 改ざんバイナリを setup が拒否 | Q-1 |
| TC-E2E-010 | Agent-C | AI 生成フッター付きコミットを commit-msg が遮断 | Q-4 |
| TC-E2E-011 | Agent-C（境界） | body 位置の Claude 言及は正規コミット | Q-4 |
| TC-E2E-012 | 鎌田 大樹 | typecheck 違反コミットを pre-commit が遮断 | #2, #11 |

### テスト環境

- OS: Linux x86_64（Ubuntu 22.04 相当）/ macOS 12+（aarch64）/ Windows 10 21H2（PowerShell 7+）
- Git: 2.9+ / Python: 3.12+ / Node: 20 LTS+
- 実 Git コマンドを使用（外部 API は raw fixture で代替）

### トレーサビリティ確認

- 受入基準 #1〜#13: TC-E2E 各ケースで網羅（`domain/test-design.md §カバレッジ基準` 参照）
- 開発者品質基準 Q-1〜Q-6: TC-E2E-009/010/011 + `domain/test-design.md §結合/ユニットテストケース` で網羅
