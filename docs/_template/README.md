# `_template/` — Vモデル全体構造 portable テンプレート

bakufu / 任意のリポジトリで設計書を作成する際の真実源テンプレート。Vモデル工程（要求分析・要件定義・基本設計・詳細設計・受入テスト・システムテスト）に対応するディレクトリ構造とファイル雛形を提供する。

エージェント（Claude Code 等）がこの `_template/` を読み込めば、各工程の役割と所収ファイル、書くべき内容と書かないべき内容を機械的に把握して設計書作成を進められる。

## 配置の考え方

`_template/` を **最上位 (`docs/_template/`)** に配置する理由:

1. Vモデル全体構造（feature 単位を超える）を再現する必要がある
2. **portable**: 他リポジトリにコピーすれば即座に利用可能
3. エージェントが `_template/` 全体を一括で認知できる

## 構成

```
_template/
├── README.md                       # 本ファイル（テンプレ全体構成）
├── process.md                      # 開発プロセス（Vモデル ライフサイクル、工程ガイド）
├── analysis/                       # 要求分析（Vモデル左上 1）
│   ├── README.md
│   ├── personas.md
│   ├── business-context.md
│   ├── pain-points.md
│   └── business-vision.md
├── requirements/                   # 要件定義（Vモデル左上 2）
│   ├── README.md
│   ├── system-context.md
│   ├── use-cases.md
│   ├── functional-scope.md
│   ├── non-functional.md
│   ├── external-integrations.md
│   ├── milestones.md
│   └── acceptance-criteria.md
├── design/                         # 基本設計（Vモデル左 3）
│   ├── README.md
│   ├── architecture.md
│   ├── domain-model.md
│   ├── tech-stack.md
│   ├── threat-model.md
│   └── migration-plan.md
├── acceptance-tests/               # 受入テスト戦略（Vモデル右上）
│   ├── README.md
│   └── scenarios/
│       └── SC-XX-NNN-template.md
└── features/                       # 詳細設計（Vモデル左 4、業務概念単位）
    └── <feature-name>/
        ├── README.md
        ├── feature-spec.md         # 業務仕様（要件定義相当）
        ├── system-test-design.md   # システムテスト
        └── <sub-feature>/
            ├── basic-design.md     # モジュール基本設計（§モジュール契約 = 機能要件）
            ├── detailed-design.md  # モジュール詳細設計
            └── test-design.md      # 結合 + UT
```

## Vモデル工程対応

| Vモデル工程 | 設計文書 | 対応テスト |
|---|---|---|
| **要求分析** | `analysis/` + `requirements/` | `acceptance-tests/scenarios/` |
| **要件定義（業務）** | `features/<name>/feature-spec.md` | `features/<name>/system-test-design.md` |
| **要件定義（機能）** | `features/<name>/<sub>/basic-design.md §モジュール契約` | (システムテストで検証) |
| **基本設計** | `features/<name>/<sub>/basic-design.md` | `features/<name>/<sub>/test-design.md §結合` |
| **詳細設計** | `features/<name>/<sub>/detailed-design.md` | `features/<name>/<sub>/test-design.md §UT` |

## 利用方法

### 新規プロジェクトでの初期セットアップ

```bash
# テンプレ各ディレクトリを docs/ にコピー
cp -r docs/_template/analysis docs/
cp -r docs/_template/requirements docs/
cp -r docs/_template/design docs/
cp -r docs/_template/acceptance-tests docs/
mkdir -p docs/features
```

各テンプレの `<placeholder>` を実プロジェクトの内容に書き換える。

### 新規 feature の追加

```bash
# 業務概念名でリネーム
cp -r 'docs/_template/features/<feature-name>' docs/features/<your-feature-name>

# sub-feature をリネーム（実装レイヤー別）
cd docs/features/<your-feature-name>
mv '<sub-feature>' domain    # または repository / http-api / ui 等
```

各ファイルの `<placeholder>` を実 feature の内容に書き換える。

## 各テンプレの役割

| ディレクトリ / ファイル | 役割 | README / 詳細 |
|---|---|---|
| [`process.md`](process.md) | **開発プロセス**（Vモデル ライフサイクル、工程ガイド、内部レビューゲート、設計 PR / 実装 PR 分割） | (本ファイル単独) |
| [`analysis/`](analysis/) | 要求分析（誰が・何のために・なぜ） | [README](analysis/README.md) |
| [`requirements/`](requirements/) | 要件定義（システムが何を提供すべきか） | [README](requirements/README.md) |
| [`design/`](design/) | 基本設計（階層 1: システム全体）| [README](design/README.md) |
| [`acceptance-tests/`](acceptance-tests/) | 受入テスト戦略（業務シナリオ） | [README](acceptance-tests/README.md) |
| [`features/<feature-name>/`](features/) | 詳細設計（業務概念単位、階層 3: モジュール基本/詳細設計を含む） | (feature の README) |

## ID 命名規則

| プレフィックス | 用途 |
|---|---|
| `UC-XX-NNN` | ユースケース（feature-spec.md §ユースケース） |
| `REQ-XX-NNN` | 機能要件（sub-feature/basic-design.md §モジュール契約） |
| `MSG-XX-NNN` | ユーザー向けメッセージ（detailed-design.md §MSG 確定文言） |
| `TC-UT-XX-NNN` | ユニットテスト |
| `TC-IT-XX-NNN` | 結合テスト |
| `TC-E2E-XX-NNN` | E2E（業務概念内） |
| `SC-XXX-NNN` | 受入シナリオ（acceptance-tests/scenarios/） |
| `R1-N` | 要求分析確定（feature-spec.md §業務ルールの確定） |

`XX` は feature 略号 2 文字（例: `EM` = Empire、`RM` = Room）。

## 規律

- 各テンプレに「## 本書の役割」節があり、書くこと / 書かないこと が凍結されている
- ID 命名規則に従い孤児要件を作らない（test-design.md のマトリクスで検証）
- 設計書は **書き換える**（READ → EDIT）。Issue 番号ベースのディレクトリは作らない（古い設計が蓄積するため）
- 疑似コード・サンプル実装（言語コードブロック）を設計書に書かない（ソースと二重管理になる）
- 図は mermaid に統一（classDiagram / sequenceDiagram / erDiagram / flowchart）
