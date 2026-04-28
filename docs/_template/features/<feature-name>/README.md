# `<feature-name>/` — \<業務概念名\> の Vモデル設計書群

\<業務概念名\> を扱う **業務概念単位** のディレクトリ。\<業務概念\> の業務的なふるまいは複数の実装レイヤー（domain / repository / http-api / ui）に渡るため、業務仕様とシステムテストは本ディレクトリ直下で 1 本ずつ凍結し、各実装レイヤーは sub-feature ディレクトリに分割する。

## 構成

```
<feature-name>/
├── README.md                       # 本ファイル（sub-feature 一覧 + マイルストーン）
├── feature-spec.md                 # 業務仕様（要件定義相当）
├── system-test-design.md           # システムテスト戦略
└── <sub-feature>/                  # 実装レイヤー別 sub-feature
    ├── basic-design.md             # モジュール基本設計（§モジュール契約 = 機能要件 REQ-XX-NNN）
    ├── detailed-design.md          # モジュール詳細設計
    └── test-design.md              # 結合 + UT
```

`<sub-feature>` は実装レイヤーごとに作成（例: `domain/` / `repository/` / `http-api/` / `ui/`）。

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| \<sub-feature 1\> | \<マイルストーン\> | UC-XX-NNN | #N | 未着手 / 設計済 / 実装中 / 完了 |
| \<sub-feature 2\> | \<マイルストーン\> | UC-XX-NNN | #N | ... |

## 着手順序と依存関係

1. **\<sub-feature 1\>** を最初に着手（他 sub-feature の前提）
2. **\<sub-feature 2\>** は \<sub-feature 1\> マージ後に着手
3. ...

## ファイル単位の規律

- **親 `feature-spec.md`** は最初の sub-feature PR で凍結し、以降の sub-feature PR では引用のみ
- 親 spec の更新が必要な場合は、別 PR で先行して直す
- sub-feature の 3 ファイル（basic-design / detailed-design / test-design）は親 spec を引用しつつ、実装契約に集中する。機能要件（REQ-XX-NNN）は basic-design.md §モジュール契約 に統合される
- **システムテストは親 [`system-test-design.md`](system-test-design.md)** だけが扱う（sub-feature の `test-design.md` には IT / UT のみ）
- 各 sub-feature の `basic-design.md §モジュール契約` 冒頭で **親 spec との依存関係** を明示する

## 関連設計書

- [親 docs/_template/](../../) — Vモデル全体テンプレート
- [`docs/design/domain-model.md`](../../design/domain-model.md) — ドメインモデル
- [`docs/analysis/personas.md`](../../analysis/personas.md) — ペルソナ定義
