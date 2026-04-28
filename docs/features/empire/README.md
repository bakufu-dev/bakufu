# `empire/` — Empire 業務概念の Vモデル設計書群

bakufu インスタンスの最上位コンテナ「Empire」を扱う**業務概念単位**のディレクトリ。Empire の業務的なふるまいは複数の実装レイヤー（domain / repository / http-api / ui）に渡るため、要求分析と E2E は本ディレクトリ直下で 1 本ずつ凍結し、各実装レイヤーは sub-feature ディレクトリに分割する。

## 構成

```
empire/
├── feature-spec.md     # Empire 業務概念全体の要求分析（業務ルール R1-1〜7、UC-EM-001〜007）
├── system-test-design.md           # 業務概念単位の E2E 検証戦略（受入基準 10, 11）
├── README.md                    # 本ファイル（sub-feature 一覧 + マイルストーン）
├── domain/                      # M1: Aggregate Root + 不変条件（Issue #8）
│   ├── requirements.md
│   ├── basic-design.md
│   ├── detailed-design.md
│   └── test-design.md
├── repository/                  # M2: SQLite 永続化（Issue #25）
│   ├── requirements.md
│   ├── basic-design.md
│   ├── detailed-design.md
│   └── test-design.md
├── http-api/                    # 将来（M3）: REST endpoint
└── ui/                          # 将来（M4）: 画面
```

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| [domain](domain/) | M1（ドメイン骨格） | UC-EM-001〜005 | [#8](https://github.com/bakufu-dev/bakufu/issues/8) | 設計済 |
| [repository](repository/) | M2（SQLite 永続化） | UC-EM-006 | [#25](https://github.com/bakufu-dev/bakufu/issues/25) | 設計済 |
| http-api | M3（HTTP API） | (UC は将来確定) | (未起票) | 未着手 |
| ui | M4（フロントエンド） | (UC は将来確定) | (未起票) | 未着手 |

## 着手順序と依存関係

1. **domain** を最初に着手（他 sub-feature の前提）。M1 で Aggregate Root + RoomRef / AgentRef VO + 不変条件を凍結
2. **repository** は domain と [`feature/persistence-foundation`](../persistence-foundation/) のマージ後に着手。M2 で SQLite 永続化を凍結
3. **http-api** は repository マージ後に着手（M3）
4. **ui** は http-api マージ後に着手（M4）

## ファイル単位の規律

- **親 `feature-spec.md`** は最初の sub-feature PR（domain）で凍結し、以降の sub-feature PR では引用のみ
- 親 ra の更新が必要な場合は、別 PR で先行して直す（[`CLAUDE.md §6`](../../../CLAUDE.md) "設計を変えるべきと判断したら別の設計 PR で先に直す"）
- sub-feature の 4 ファイル（requirements / basic-design / detailed-design / test-design）は親 ra を引用しつつ、実装契約に集中する
- **E2E は親 [`system-test-design.md`](system-test-design.md)** だけが扱う。sub-feature の `test-design.md` には E2E を書かない（IT / UT のみ）
- 各 sub-feature の `requirements.md` 冒頭で **親 ra との依存関係** を明示する（`> 親要求分析: [../feature-spec.md](../feature-spec.md)`）

## 関連設計書

- [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Empire — 凍結済み Aggregate 設計
- [`docs/analysis/personas.md`](../../analysis/personas.md) — bakufu システム全体ペルソナ
- [`docs/features/_template/`](../_template/) — Vモデル 5 設計書のひな形（フラット形式）

階層化形式のテンプレート（業務概念 + sub-feature の 2 階層）は別途 `_template-hierarchical/` として整備予定（本 empire ディレクトリを実物サンプルとして評価後）。
