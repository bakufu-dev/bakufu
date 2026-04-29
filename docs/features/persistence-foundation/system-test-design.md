# システムテスト戦略 — persistence-foundation

> 関連: [`feature-spec.md §9`](feature-spec.md) 受入基準 1〜13（Q-1 / Q-2 は CI ジョブ担保 — [`domain/test-design.md`](domain/test-design.md) §カバレッジ基準）
> 対象: infrastructure 層単独（CLI / HTTP API / UI のいずれの公開エントリポイントも持たない）

本ドキュメントは persistence-foundation **業務概念全体** のシステムテスト戦略を凍結する。`domain/` sub-feature の IT / UT は [`domain/test-design.md`](domain/test-design.md) が担当する。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は infrastructure 層単独で、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`feature-spec.md §6`](feature-spec.md) Out of Scope で明記）
- Bootstrap が起動する FastAPI / WebSocket リスナは段階 8 で「listening」に至るのみで、実 HTTP リクエストを処理する handler は本 PR の範囲外
- 受入基準 §9 #1〜#13 はすべて unit / integration テストで検証可能（`domain/test-design.md` が担保）
- 後続 `feature/admin-cli` / `feature/http-api` が公開 I/F を実装した時点で E2E（`bakufu admin retry-event` 等で実 SQLite に書き込み確認）を起票する

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 | 紐付く受入基準 |
|---------|---------|---------|---------|---------|-------------|
| （N/A） | — | 該当なし — infrastructure 層のため公開 I/F なし | — | — | — |

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（`pytest.tmp_path` 配下の `bakufu.db`）|
| domain 層 | infrastructure 層の直接呼び出し（application 層経由なし） |
| application 層 | 該当なし（本 feature は application 層を持たない） |
| 外部システム | 該当なし（外部 URL fetch なし） |

受入基準 #1〜#13 の検証はすべて [`domain/test-design.md`](domain/test-design.md) の IT / UT が担保する。E2E は後続 feature で追加する。

## カバレッジ基準

- 受入基準（[`feature-spec.md §9`](feature-spec.md)）の #1〜#13 が **`domain/test-design.md`** の IT / UT で最低 1 件ずつ検証される
- Q-1（lint/typecheck）/ Q-2（カバレッジ 90%）は CI ジョブで担保（[`feature-spec.md §10`](feature-spec.md)）

## テストディレクトリ構造

```
backend/tests/
└── （E2E なし — 後続 feature/admin-cli 等で追加予定）
```

## 関連

- [`feature-spec.md §9`](feature-spec.md) — 受入基準（テストの真実源）
- [`domain/test-design.md`](domain/test-design.md) — sub-feature 内 IT / UT（受入基準 #1〜#13 を担保）
- [`../../acceptance-tests/scenarios/`](../../acceptance-tests/scenarios/) — feature 跨ぎの受入シナリオ
