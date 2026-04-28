# `room/` — Room 業務概念の Vモデル設計書群

bakufu インスタンスの編成空間「Room」を扱う**業務概念単位**のディレクトリ。Room の業務的なふるまいは複数の実装レイヤー（domain / repository / http-api / ui）に渡るため、要求分析と E2E は本ディレクトリ直下で 1 本ずつ凍結し、各実装レイヤーは sub-feature ディレクトリに分割する。

## 構成

```
room/
├── feature-spec.md         # Room 業務概念全体の業務仕様（業務ルール R1-X、UC-RM-001〜、受入基準）
├── system-test-design.md   # 業務概念単位の E2E 検証戦略
├── README.md               # 本ファイル（sub-feature 一覧 + マイルストーン）
├── domain/                 # M1: Aggregate Root + 不変条件（Issue #18）
│   ├── basic-design.md     # §モジュール契約 = 機能要件 REQ-RM-001〜006
│   ├── detailed-design.md
│   └── test-design.md
├── repository/             # M2: SQLite 永続化（Issue #33）
│   ├── basic-design.md     # §モジュール契約 = 機能要件 REQ-RR-001〜006
│   ├── detailed-design.md
│   └── test-design.md
├── http-api/               # 将来（M3）: REST endpoint
└── ui/                     # 将来（M4）: 画面
```

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| [domain](domain/) | M1（ドメイン骨格） | UC-RM-001〜005 | [#18](https://github.com/bakufu-dev/bakufu/issues/18) | 設計済 |
| [repository](repository/) | M2（SQLite 永続化） | UC-RM-006 | [#33](https://github.com/bakufu-dev/bakufu/issues/33) | 設計済 |
| http-api | M3（HTTP API） | (UC は将来確定) | (未起票) | 未着手 |
| ui | M4（フロントエンド） | (UC は将来確定) | (未起票) | 未着手 |

## 着手順序と依存関係

1. **domain** を最初に着手（他 sub-feature の前提）。M1 で Room Aggregate Root + PromptKit VO + 不変条件を凍結
2. **repository** は domain と [`feature/persistence-foundation`](../persistence-foundation/) のマージ後に着手。M2 で SQLite 永続化を凍結（room §確定 G 実適用: PromptKit.prefix_markdown マスキング）
3. **http-api** は repository マージ後に着手（M3）
4. **ui** は http-api マージ後に着手（M4）

## ファイル単位の規律

- **親 `feature-spec.md`** は最初の sub-feature PR（domain）で凍結し、以降の sub-feature PR では引用のみ
- 親 spec の更新が必要な場合は、別 PR で先行して直す
- sub-feature の 3 ファイル（basic-design / detailed-design / test-design）は親 spec を引用しつつ、実装契約に集中する。機能要件（REQ-XX-NNN）は basic-design.md §モジュール契約 に統合
- **システムテストは親 [`system-test-design.md`](system-test-design.md)** だけが扱う。sub-feature の `test-design.md` には書かない（IT / UT のみ）
- 各 sub-feature の `basic-design.md §モジュール契約` 冒頭で **親 spec との依存関係** を明示する

## 関連設計書

- [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Room — 凍結済み Aggregate 設計
- [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §AgentMembership — 既存 VO（再利用）
- [`docs/analysis/personas.md`](../../analysis/personas.md) — bakufu システム全体ペルソナ
- [`docs/features/agent/`](../agent/) — AgentMembership を通じた Room 編成の依存先
- [`docs/features/empire/`](../empire/) — Room の親 Aggregate
