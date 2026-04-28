# システムテスト設計書

> feature: `<feature-name>`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準

## 本書の役割

本書は **\<業務概念名\> 業務概念全体のシステムテスト戦略** を凍結する。各 sub-feature の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**システムテストは本書だけが扱う**（sub-feature の `test-design.md` には書かない）。

## システムテスト スコープ

- \<sub-feature 1\> から \<sub-feature 2\> への業務シナリオの End-to-End
- 将来 sub-feature 追加時に本書に追記

## 観察主体

\<ペルソナ\>（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本テストでは \<harness の説明\> を用いて、\<業務シナリオ\> を観察する。

## システムテストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---|---|---|---|---|
| TC-ST-XX-001 | \<シナリオ名\> | 1) \<操作\> 2) \<操作\> | \<期待される観察事象\> | feature-spec.md §9 #N |
| TC-ST-XX-002 | ... | ... | ... | ... |

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | \<実 DB / モック\> |
| domain 層 | \<実 Aggregate\> |
| application 層 | \<直接呼び出し / API 経由\> |
| 外部システム | \<Mock / fake adapter / 専用テスト環境\> |

## カバレッジ基準

- 受入基準（[`feature-spec.md §9`](feature-spec.md)）が **システムテストで最低 1 件** 検証される
- sub-feature 跨ぎのシナリオを 1 件以上含む

## テストディレクトリ構造

```
backend/tests/system/
└── test_<feature-name>_lifecycle.py    # TC-ST-XX-NNN
```

## 関連

- [`feature-spec.md §9`](feature-spec.md) — 受入基準（テストの真実源）
- [`<sub-feature 1>/test-design.md`](<sub-feature 1>/test-design.md) — sub-feature 内 IT / UT
- [`<sub-feature 2>/test-design.md`](<sub-feature 2>/test-design.md) — sub-feature 内 IT / UT
- [`../../acceptance-tests/scenarios/`](../../acceptance-tests/scenarios/) — feature 跨ぎの受入シナリオ
