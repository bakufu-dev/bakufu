# `agent/` — Agent 業務概念の Vモデル設計書群

bakufu インスタンスで採用された AI エージェント「Agent」を扱う**業務概念単位**のディレクトリ。Agent の業務的なふるまいは複数の実装レイヤー（domain / repository / http-api / ui）に渡るため、要求分析と E2E は本ディレクトリ直下で 1 本ずつ凍結し、各実装レイヤーは sub-feature ディレクトリに分割する。

## 構成

```
agent/
├── feature-spec.md         # Agent 業務概念全体の業務仕様（業務ルール R1-X、UC-AG-001〜、受入基準）
├── system-test-design.md   # 業務概念単位の E2E 検証戦略
├── README.md               # 本ファイル（sub-feature 一覧 + マイルストーン）
├── domain/                 # M1: Aggregate Root + 不変条件（Issue #10）
│   ├── basic-design.md     # §モジュール契約 = 機能要件 REQ-AG-001〜006
│   ├── detailed-design.md
│   └── test-design.md
├── repository/             # M2: SQLite 永続化（Issue #32）
│   ├── basic-design.md     # §モジュール契約 = 機能要件 REQ-AGR-001〜005
│   ├── detailed-design.md
│   └── test-design.md
├── http-api/               # 将来（M3）: REST endpoint（Issue #59）
└── ui/                     # 将来（M4）: 画面
```

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| [domain](domain/) | M1（ドメイン骨格） | UC-AG-001〜005 | [#10](https://github.com/bakufu-dev/bakufu/issues/10) | 設計済 |
| [repository](repository/) | M2（SQLite 永続化） | UC-AG-006 | [#32](https://github.com/bakufu-dev/bakufu/issues/32) | 設計済 |
| http-api | M3（HTTP API） | (UC は将来確定) | [#59](https://github.com/bakufu-dev/bakufu/issues/59) | 未着手 |
| ui | M4（フロントエンド） | (UC は将来確定) | (未起票) | 未着手 |

## 着手順序と依存関係

1. **domain** を最初に着手（他 sub-feature の前提）。M1 で Aggregate Root + Persona / ProviderConfig / SkillRef VO + 不変条件を凍結
2. **repository** は domain と [`feature/persistence-foundation`](../persistence-foundation/) のマージ後に着手。M2 で SQLite 永続化を凍結（Schneier 申し送り #3 実適用）
3. **http-api** は repository マージ後に着手（M3）
4. **ui** は http-api マージ後に着手（M4）

## ファイル単位の規律

- **親 `feature-spec.md`** は最初の sub-feature PR（domain）で凍結し、以降の sub-feature PR では引用のみ
- 親 spec の更新が必要な場合は、別 PR で先行して直す
- sub-feature の 3 ファイル（basic-design / detailed-design / test-design）は親 spec を引用しつつ、実装契約に集中する。機能要件（REQ-XX-NNN）は basic-design.md §モジュール契約 に統合
- **システムテストは親 [`system-test-design.md`](system-test-design.md)** だけが扱う。sub-feature の `test-design.md` には書かない（IT / UT のみ）
- 各 sub-feature の `basic-design.md §モジュール契約` 冒頭で **親 spec との依存関係** を明示する

## 関連設計書

- [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Agent — 凍結済み Aggregate 設計
- [`docs/analysis/personas.md`](../../analysis/personas.md) — bakufu システム全体ペルソナ
- [`docs/features/empire/`](../empire/) — 業務概念階層化のサンプル（empire が先行例）
