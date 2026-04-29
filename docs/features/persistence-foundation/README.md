# `persistence-foundation/` — SQLite 永続化基盤の Vモデル設計書群

SQLite 永続化基盤を扱う **業務概念単位** のディレクトリ。後続 Aggregate Repository PR 群が乗る共通基盤（SQLAlchemy engine / session / Alembic migration / マスキングゲートウェイ / Outbox Dispatcher 骨格 / pid_registry GC / Bootstrap 起動シーケンス）の業務仕様とシステムテストを本ディレクトリ直下で 1 本ずつ凍結し、実装レイヤーは `domain/` sub-feature に分割する。

## 構成

```
persistence-foundation/
├── README.md                         # 本ファイル（sub-feature 一覧 + マイルストーン）
├── feature-spec.md                   # 業務仕様（要件定義相当）
├── system-test-design.md             # システムテスト戦略
└── domain/                           # infrastructure domain sub-feature
    ├── basic-design.md               # モジュール基本設計（§モジュール契約 = REQ-PF-001〜010）
    ├── detailed-design.md            # モジュール詳細設計（索引 + 確定事項サマリ）
    ├── test-design.md                # 結合 + UT
    └── detailed-design/              # トピック別補章（500 行ルール準拠）
        ├── modules.md                # Module 別仕様（14 Module）
        ├── pragma.md                 # PRAGMA + dual connection（確定 D-1〜D-4）
        ├── masking.md                # マスキング契約（確定 A + 確定 F）
        ├── triggers.md               # TypeDecorator 配線 + SQLite トリガ（確定 B / C）
        ├── bootstrap.md              # Bootstrap 起動シーケンス（確定 E / G / J / L）
        ├── outbox.md                 # Outbox Dispatcher Fail Loud（確定 K）
        ├── handoff.md                # Schneier 申し送り + 依存方向（確定 H / I）
        ├── messages.md               # MSG 確定文言表（MSG-PF-001〜008）
        └── persistence-keys.md      # データ構造（永続化キー）
```

`domain/` は infrastructure 実装レイヤーを表す sub-feature。Aggregate 別 Repository（empire / workflow / agent / room / directive / task / external-review-gate）は別 feature として積む。

## sub-feature とマイルストーン

| sub-feature | マイルストーン | 主担当 UC | Issue | ステータス |
|---|---|---|---|---|
| `domain/` | M2 SQLite 永続化基盤 | UC-PF-001〜005 | #19 | 完了 |

後続 Repository 系 sub-feature は本 feature の基盤を共通資産として参照し、各 Aggregate 別 feature として独立 PR で積む。

## 着手順序と依存関係

1. **`domain/`** を最初に着手・完了（Aggregate 別 Repository PR の前提）
2. 後続 Aggregate Repository PR（`feature/empire-repository` 等）は本 feature のマージ後に着手

## ファイル単位の規律

- **親 `feature-spec.md`** は本 PR（Issue #79）で凍結。以降の sub-feature PR では引用のみ
- 親 spec の更新が必要な場合は、別 PR で先行して直す
- `domain/` の 3 ファイル（basic-design / detailed-design / test-design）は親 spec を引用しつつ、実装契約に集中する。機能要件（REQ-PF-001〜010）は `domain/basic-design.md §モジュール契約` に統合
- **システムテストは親 [`system-test-design.md`](system-test-design.md)** だけが扱う（`domain/test-design.md` は IT / UT のみ）
- トピック別補章（`domain/detailed-design/*.md`）は `domain/detailed-design.md` の索引から参照する

## 関連設計書

- [`docs/design/tech-stack.md`](../../design/tech-stack.md) §ORM — SQLAlchemy 2.x / Alembic 採用根拠
- [`docs/design/domain-model/storage.md`](../../design/domain-model/storage.md) §シークレットマスキング規則
- [`docs/design/domain-model/events-and-outbox.md`](../../design/domain-model/events-and-outbox.md) §`domain_event_outbox`
- [`docs/design/threat-model.md`](../../design/threat-model.md) §Schneier 申し送り
- [`docs/analysis/personas.md`](../../analysis/personas.md) — ペルソナ定義
