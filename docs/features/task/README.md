# `task/` — Task 業務概念の Vモデル設計書群

bakufu インスタンスで CEO directive から生成され、Workflow の Stage を進行しながら Agent が deliverable を commit するワークフロー実行単位「Task」を扱う**業務概念単位**のディレクトリ。Task の業務的なふるまいは複数の実装レイヤー（domain / repository / http-api / ui）に渡るため、要求分析と E2E は本ディレクトリ直下で 1 本ずつ凍結し、各実装レイヤーは sub-feature ディレクトリに分割する。

## 構成

```
task/
├── feature-spec.md         # Task 業務概念全体の業務仕様（業務ルール R1-X、UC-TS-NNN、受入基準）
├── system-test-design.md   # 業務概念単位の E2E 検証戦略
├── README.md               # 本ファイル（sub-feature 一覧 + マイルストーン）
├── domain/                 # M1: Aggregate Root + state machine + 不変条件（Issue #37）
│   ├── basic-design.md     # §モジュール契約 = 機能要件 REQ-TS-001〜011
│   ├── detailed-design.md
│   └── test-design.md
├── repository/             # M2: SQLite 永続化（Issue #35）
│   ├── basic-design.md     # §モジュール契約 = 機能要件 REQ-TR-001〜006
│   ├── detailed-design.md
│   └── test-design.md
├── http-api/               # 将来（M3）: REST endpoint
└── ui/                     # 将来（M4）: Task 進行画面
```

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| [domain](domain/) | M1（ドメイン骨格） | UC-TS-001〜007 | [#37](https://github.com/bakufu-dev/bakufu/issues/37) | 設計済 |
| [repository](repository/) | M2（SQLite 永続化） | UC-TS-008 | [#35](https://github.com/bakufu-dev/bakufu/issues/35) | 設計済 |
| http-api | M3（HTTP API） | (UC は将来確定) | (未起票) | 未着手 |
| ui | M4（フロントエンド） | (UC は将来確定) | (未起票) | 未着手 |

## 着手順序と依存関係

1. **domain** を最初に着手（他 sub-feature の前提）。M1 で Task Aggregate Root + TaskStatus 6 種 state machine（13 遷移）+ BLOCKED 隔離経路 + Deliverable / Attachment VO + TaskInvariantViolation を凍結
2. **repository** は domain と [`feature/persistence-foundation`](../persistence-foundation/) のマージ後に着手。M2 で SQLite 永続化を凍結（`tasks.last_error` / `deliverables.body_markdown` の MaskedText 実適用 + BUG-DRR-001 closure）
3. **http-api** は repository マージ後に着手（M3）
4. **ui** は http-api マージ後に着手（M4、Task 進行 UI + External Review ゲート操作）

## ファイル単位の規律

- **親 `feature-spec.md`** は最初の sub-feature PR（domain）で凍結し、以降の sub-feature PR では引用のみ
- 親 spec の更新が必要な場合は、別 PR で先行して直す
- sub-feature の 3 ファイル（basic-design / detailed-design / test-design）は親 spec を引用しつつ、実装契約に集中する。機能要件（REQ-XX-NNN）は basic-design.md §モジュール契約 に統合
- **システムテストは親 [`system-test-design.md`](system-test-design.md)** だけが扱う。sub-feature の `test-design.md` には書かない（IT / UT のみ）
- 各 sub-feature の `basic-design.md §モジュール契約` 冒頭で **親 spec との依存関係** を明示する

## 関連設計書

- [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Task — 凍結済み Aggregate 設計
- [`docs/design/domain-model/value-objects.md`](../../design/domain-model/value-objects.md) §列挙型一覧（TaskStatus / LLMErrorKind）
- [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §Deliverable / §Attachment / §シークレットマスキング規則
- [`docs/analysis/personas.md`](../../analysis/personas.md) — bakufu システム全体ペルソナ
- [`docs/features/workflow/`](../workflow/) — Task が参照する Stage / Transition の Aggregate（先行 feature）
- [`docs/features/directive/`](../directive/) — Task の起点 Aggregate（先行 feature）
