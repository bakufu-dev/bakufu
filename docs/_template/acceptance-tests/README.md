# `acceptance-tests/` — 受入テスト戦略（Vモデル右上）

プロジェクト全体の **業務シナリオを End-to-End で検証する受入テスト** を凍結するディレクトリ。Vモデル工程の最上位（要求分析 ↔ 受入テスト）に対応する。

## 本ディレクトリの役割

各 feature 配下の `system-test-design.md` は **feature 業務概念に閉じたシステムテスト** を担当する。本ディレクトリは **複数 feature を跨ぐ業務シナリオ（受入テスト）** を担当する。

```
Vモデル対応:

要求分析 ── analysis/ + requirements/                    ↔ 受入テスト   : acceptance-tests/scenarios/
要件定義 ── features/<name>/feature-spec.md              ↔ システムテスト : features/<name>/system-test-design.md
基本設計 ── features/<name>/<sub>/basic-design.md        ↔ 結合テスト    : features/<name>/<sub>/test-design.md §結合
詳細設計 ── features/<name>/<sub>/detailed-design.md     ↔ ユニットテスト : features/<name>/<sub>/test-design.md §UT
```

## 真実源

| フェーズ | 受入基準の真実源 | 担当シナリオ命名 |
|---|---|---|
| MVP（v0.1.0） | [`../requirements/acceptance-criteria.md`](../requirements/acceptance-criteria.md) | `scenarios/SC-MVP-NNN-*.md` |
| Phase 2 以降 | （ロードマップ確定時に対応文書を新設） | `scenarios/SC-P2-NNN-*.md`（将来） |

## 用語

| 本書の呼称 | 同義の業界用語 | 対象 |
|---|---|---|
| **受入テスト**（Acceptance Test） | シナリオテスト / 総合テスト / システムテスト（広義） | ペルソナの業務シナリオを End-to-End で検証 |
| **シナリオ**（Scenario） | テストケース / E2E テスト / ジャーニーテスト | 受入テストの 1 単位（ペルソナの 1 業務行為の連続） |

各 feature 配下の `system-test-design.md` は呼称上「システムテスト」（Vモデル正規）。本ディレクトリの「受入テスト」（feature 跨ぎ）と命名で区別する。

## ディレクトリ構造

```
acceptance-tests/
├── README.md                       # 本ファイル
└── scenarios/
    └── SC-XXX-NNN-<scenario-name>.md  # 各シナリオファイル
```

## シナリオの書き方

各シナリオファイル（`scenarios/SC-XXX-NNN-*.md`）は以下の構造を持つ:

1. **ペルソナと前提**: 観察主体と起動状態
2. **業務シナリオ**: ペルソナの業務行為の連続（番号付きステップ）
3. **観察可能事象**: 各ステップで観察される事象（UI / CLI / DB / 外部 API）
4. **カバーする受入基準**: `../requirements/acceptance-criteria.md` への紐付け
5. **関連 feature**: 各ステップで動く feature の `system-test-design.md` への参照
6. **検証手段**: 自動テスト（pytest / Playwright 等）か手動オペレーションか
7. **想定実装ファイル**: 実装パス
8. **カバレッジ基準と未決課題**

詳細は [`scenarios/SC-XX-NNN-template.md`](scenarios/SC-XX-NNN-template.md) をテンプレートとする。

## 起票タイミング規律

- 受入テストは **MVP の後段マイルストーン** で実装される
- 設計文書（本ディレクトリ）は **早期段階で先に凍結** し、各 feature が「うちの feature の責務外」として越権する経路を断つ

## 受入基準カバレッジ表

`../requirements/acceptance-criteria.md` の各受入基準が少なくとも 1 シナリオでカバーされていることを担保する:

| # | 受入基準（要旨） | カバーシナリオ |
|---|---|---|
| 1 | \<受入基準 1\> | SC-XXX-NNN |
| 2 | \<受入基準 2\> | SC-XXX-NNN |
| ... | ... | ... |

孤児受入基準（カバーシナリオなし）はゼロ。

## 関連

- [`../requirements/acceptance-criteria.md`](../requirements/acceptance-criteria.md) — 受入基準の真実源
- [`../analysis/personas.md`](../analysis/personas.md) — シナリオの観察主体
- [`../requirements/use-cases.md`](../requirements/use-cases.md) — 主要ユースケース
- [`../features/`](../features/) — 各 feature の Vモデル設計書（system-test-design.md を持つ）
