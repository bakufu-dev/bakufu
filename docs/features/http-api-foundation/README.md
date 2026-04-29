# `http-api-foundation/` — HTTP API 共通基盤の Vモデル設計書群

http-api-foundation（HTTP API 共通基盤）を扱う **業務概念単位** のディレクトリ。FastAPI アプリ初期化・error handler・依存注入・ヘルスチェック・application service 骨格を本 feature で凍結し、後続 Aggregate 別 HTTP API は Issue B〜G として個別に積む。

## 構成

```
http-api-foundation/
├── README.md                       # 本ファイル（sub-feature 一覧 + マイルストーン）
├── feature-spec.md                 # 業務仕様（要件定義相当）
├── system-test-design.md           # システムテスト戦略
└── http-api/                       # interfaces レイヤー sub-feature
    ├── basic-design.md             # モジュール基本設計（§モジュール契約 = 機能要件 REQ-HAF-NNN）
    ├── detailed-design.md          # モジュール詳細設計（確定 A〜G / MSG-HAF-NNN）
    └── test-design.md              # 結合 + UT
```

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| `http-api/` | M3（HTTP API 基盤） | UC-HAF-001〜004 | #55 | 設計済 |

## 着手順序と依存関係

1. **`http-api/`** — Issue #55。persistence-foundation マージ後に着手。後続 Issue B〜G の前提

後続 Issue B〜G（empire / room / workflow / agent / task / external-review-gate HTTP API）は本 Issue #55 マージ後に着手。

## ファイル単位の規律

- **親 `feature-spec.md`** は本 PR（#55 設計 PR）で凍結し、以降の sub-feature PR（後続 B〜G）では引用のみ
- 親 spec の更新が必要な場合は、別 PR で先行して直す
- **システムテストは親 [`system-test-design.md`](system-test-design.md)** だけが扱う（`http-api/test-design.md` には IT / UT のみ）

## 関連設計書

- [`docs/design/architecture.md`](../../design/architecture.md) — interfaces レイヤー構成（本 PR で更新）
- [`docs/design/tech-stack.md`](../../design/tech-stack.md) — FastAPI / uvicorn / Pydantic v2 採用確定
- [`docs/design/threat-model.md`](../../design/threat-model.md) — §A3 ネットワーク経路（CSRF / CORS 対策）
- [`docs/analysis/personas.md`](../../analysis/personas.md) — ペルソナ定義
