# システムテスト設計書

> feature: `http-api-foundation`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準

## 本書の役割

本書は **http-api-foundation 業務概念全体のシステムテスト戦略** を凍結する。各 sub-feature の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**システムテストは本書だけが扱う**（sub-feature の `test-design.md` には書かない）。

## システムテスト スコープ

- http-api sub-feature 単独（本 feature は sub-feature が 1 つのため、境界跨ぎシナリオは lifespan → HTTP レイヤー → 実 DB セッションの統合が中心）
- persistence-foundation の session factory を実際に利用した起動〜リクエスト〜シャットダウンの E2E 動作確認
- 後続 Aggregate HTTP API sub-feature が追加されたとき、本書にシナリオを追記する

## 観察主体

CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本テストでは `httpx.AsyncClient` + 実 SQLite（tempfile）harness を用いて、bakufu HTTP API の稼働状態を観察する。

## システムテストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---|---|---|---|---|
| TC-ST-HAF-001 | ヘルスチェック | `GET /health` を送信する | HTTP 200, Body `{"status": "ok"}` | feature-spec.md §9 #1 |
| TC-ST-HAF-002 | 存在しないパスへのアクセス | `GET /nonexistent` を送信する | HTTP 404, Body `{"error": {"code": "not_found", "message": ...}}` | feature-spec.md §9 #2 |
| TC-ST-HAF-005 | OpenAPI スキーマ生成 | `GET /openapi.json` を送信する | HTTP 200, Body が有効な JSON で `"openapi"` キーを含む | feature-spec.md §9 #5 |
| TC-ST-HAF-009 | lifespan 統合（起動〜シャットダウン） | `AsyncClient` を用いた ASGI lifespan 経由で `GET /health` を送信し、クライアント close まで実行する | 起動時に session factory が初期化され、GET /health が 200 を返し、close 後に engine が dispose される | feature-spec.md §9 #7 |

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（pytest tempdir の `bakufu_test.db`）。persistence-foundation の bootstrap を利用 |
| domain 層 | 実 Aggregate（http-api-foundation では直接参照なし。後続 API PR 追加時に変更）|
| application 層 | 実 application/services/ 骨格（http-api-foundation では空実装）|
| 外部システム | 該当なし（http-api-foundation は Discord / GitHub に依存しない）|

## カバレッジ基準

- 受入基準（[`feature-spec.md §9`](feature-spec.md)）#1 / #2 / #5 / #7 が **システムテストで最低 1 件** 検証される
- lifespan → HTTP リクエスト → セッション take/release → シャットダウンの統合シナリオを 1 件以上含む

## テストディレクトリ構造

```
backend/tests/system/
└── test_http_api_foundation_lifecycle.py    # TC-ST-HAF-NNN
```

## 関連

- [`feature-spec.md §9`](feature-spec.md) — 受入基準（テストの真実源）
- [`http-api/test-design.md`](http-api/test-design.md) — sub-feature 内 IT / UT
- [`../../acceptance-tests/scenarios/`](../../acceptance-tests/scenarios/) — feature 跨ぎの受入シナリオ
