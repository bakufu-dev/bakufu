# 業務仕様書（feature-spec）— http-api-foundation

> feature: `http-api-foundation`（業務概念単位）
> sub-features: [`http-api/`](http-api/)
> 関連 Issue: [#55 feat(http-api-foundation): FastAPI application foundation (M3)](https://github.com/bakufu-dev/bakufu/issues/55)
> 凍結済み設計: [`docs/design/tech-stack.md`](../../design/tech-stack.md) §Backend / §ネットワーク / §TLS / [`docs/design/threat-model.md`](../../design/threat-model.md) §A3 / [`docs/design/architecture.md`](../../design/architecture.md) §レイヤー構成

## 本書の役割

本書は **http-api-foundation という業務概念全体の業務仕様** を凍結する。プロジェクト全体の要求分析（[`docs/analysis/`](../../analysis/)）を HTTP API 共通基盤という観点で具体化し、ペルソナから見て **観察可能な業務ふるまい** を実装レイヤーに依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない。

**書くこと**:
- ペルソナが http-api-foundation で達成できるようになる行為（ユースケース UC-HAF-NNN）
- 業務ルール（エラーレスポンス形式・CORS・lifespan 管理・CSRF 対策等、全 sub-feature を貫く凍結）
- 観察可能な事象としての受入基準（システムテストの真実源）

**書かないこと**（後段の設計書・別ディレクトリへ追い出す）:
- 採用技術スタック → `http-api/basic-design.md` / [`docs/design/tech-stack.md`](../../design/tech-stack.md)
- 実装方式の比較・選定議論 → `http-api/detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → `http-api/basic-design.md` / `http-api/detailed-design.md`
- pyright strict / カバレッジ閾値 → §10 開発者品質基準（CI 担保、業務要求とは分離）

## 1. この feature の位置付け

http-api-foundation は **bakufu MVP M3 の横断基盤** として定義する。後続 Issue B〜G（empire / room / workflow / agent / task / external-review-gate HTTP API）が全て本 feature に依存するため、M3 の起点 Issue として最初に完了させる。

業務的なライフサイクルは単一の実装レイヤーに閉じる:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| interfaces | [`http-api/`](http-api/) | FastAPI アプリ初期化・error handler・依存注入・ヘルスチェック・application service 骨格 |
| ui | (将来) | CEO が bakufu の状態を観察・操作する Web 画面 |

## 2. 人間の要求

> Issue #55:
>
> M3（HTTP API）フェーズの基盤となる FastAPI アプリケーション共通設定を実装する。後続 Issue B〜G が全て本 Issue に依存するため、最初に完了させること。`GET /health` が `{"status": "ok"}` を返すこと、`/openapi.json` が生成されること、lint/typecheck/test-backend がグリーンであること。

## 3. 背景・痛点

### 現状の痛点

1. M2 永続化基盤・M1 ドメイン骨格が揃っているが、**HTTP 経由でアクセスする経路が存在しない**。CEO は bakufu の状態を確認・操作できない
2. 後続 HTTP API Issue を並行着手すると、**エラーレスポンス形式 / 依存注入ファクトリ / lifespan 管理が各 PR で個別に決まり衝突する**
3. CSRF・CORS・プロキシヘッダ処理などのセキュリティ横断設定が分散すると漏れが生じる

### 解決されれば変わること

- 後続 empire/room 等の HTTP API PR が共通の error handler / session factory / DI ファクトリを参照できる
- CEO が `GET /health` で bakufu の稼働状態を確認できる
- `/openapi.json` から API 仕様を自動生成し、後続 API 開発の足場となる

### ビジネス価値

- M3〜M7 の全 HTTP API 開発の起点を確保する。本 feature なしに後続 API は着手不能
- エラーレスポンス形式を 1 箇所で凍結し、クライアント（Frontend / CEO）が一貫した形式でエラーを処理できる

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|---|---|---|---|
| CEO | bakufu のオーナー・運用者 | 直接 | GET /health で bakufu が動いているか確認する |
| API 開発者（AI エージェント） | 後続 HTTP API の実装者 | 直接 | 共通 error handler / DI ファクトリを参照して個別 API を実装する |

プロジェクト全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|---|---|---|---|---|
| UC-HAF-001 | CEO | bakufu が正常起動しているか `GET /health` で確認したい | 必須 | http-api |
| UC-HAF-002 | CEO / API 開発者 | リクエストが失敗したとき、コードとメッセージを含む統一されたエラーレスポンスを受け取りたい | 必須 | http-api |
| UC-HAF-003 | API 開発者 | `/openapi.json` および `/docs` から API 仕様を確認したい | 必須 | http-api |
| UC-HAF-004 | API 開発者 | 後続 HTTP API が DB セッション・Repository・Service を DI ファクトリ経由で取得したい | 必須 | http-api |

## 6. スコープ

### In Scope

- `GET /health` エンドポイント（UC-HAF-001）
- 統一エラーレスポンス形式（UC-HAF-002）
- `/openapi.json` 生成（UC-HAF-003）
- 依存注入ファクトリ（UC-HAF-004）
- lifespan による session factory の初期化・クリーンアップ
- `application/services/` の thin CRUD service 骨格（後続 API PR が肉付け）
- `backend/src/bakufu/main.py` uvicorn エントリポイント

### Out of Scope（参照）

- 個別 Aggregate の CRUD HTTP API → 後続 Issue B〜G（empire / room / workflow / agent / task / external-review-gate HTTP API）
- 認証・セッション管理（Cookie / OAuth） → Phase 2
- WebSocket エンドポイント → Phase 2
- Frontend UI → Phase 2

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: エラーレスポンスは `{"error": {"code": str, "message": str}}` 形式に統一する

**理由**: クライアントがエラー種別をコード値で機械的に判定できるようにする。FastAPI デフォルトの `{"detail": ...}` 形式は構造が不定でパース困難。全 HTTP API が一貫した形式を使う契約を本 feature で凍結することで、後続 PR の形式バラつきを防ぐ。

### 確定 R1-2: lifespan で SQLAlchemy async_sessionmaker を管理する

**理由**: FastAPI の `lifespan` コンテキストマネージャは startup/shutdown ロジックを 1 箇所に集約できる（`@app.on_event` は非推奨）。session factory は `app.state` に保持し、`get_session()` DI ファクトリ経由で各リクエストに yield する。これにより session の open/close が DI フレームワークの管理下に置かれ、close 漏れを防ぐ。

### 確定 R1-3: CORS はアクセス元を `BAKUFU_ALLOWED_ORIGINS` 環境変数で制御する。未設定時は `["http://localhost:5173"]`（Vite 開発サーバー）のみ許可する

**理由**: loopback バインド前提（threat-model.md §A3）のため、ワイルドカード `*` は許可しない。本番環境で reverse proxy を立てる場合は環境変数で明示設定を要求する。

### 確定 R1-4: 状態変更 API（POST / PUT / PATCH / DELETE）は `Origin` ヘッダを検証する

**理由**: threat-model.md §A3 の CSRF 対策（T2 攻撃者）。MVP では Cookie セッションを採用しないが、検証ロジックを先に配線しておく多層防御を確保する。`Origin` ヘッダが存在しない場合、または許可 Origin 一覧に含まれない場合は 403 Forbidden を返す。

### 確定 R1-5: `application/services/` の各サービスクラスは Repository Port を受け取る純粋なファサードとする。DB / ORM の実装詳細に依存しない

**理由**: Clean Architecture の Port パターン。後続 PR が individual CRUD を実装する際、application 層が infrastructure の型（`AsyncSession` 等）を直接参照する依存汚染を防ぐ。

## 8. 制約・前提

| 区分 | 内容 |
|---|---|
| 既存運用規約 | GitFlow / Conventional Commits / CODEOWNERS 保護 |
| ライセンス | MIT |
| 対象 OS | Linux / macOS（開発）|
| 依存 feature | `persistence-foundation`（SQLAlchemy engine / session factory 基盤）|
| バインドアドレス | `127.0.0.1:8000` 既定（`BAKUFU_BIND_HOST` / `BAKUFU_BIND_PORT` 環境変数で変更可）|
| Python バージョン | 3.12+ |

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 1 | `GET /health` が HTTP 200 と `{"status": "ok"}` を返す | UC-HAF-001 | TC-ST-HAF-001 |
| 2 | 存在しないパスへの GET が `{"error": {"code": "not_found", "message": ...}}` と HTTP 404 を返す | UC-HAF-002 | TC-ST-HAF-002 |
| 3 | リクエスト Body の Pydantic バリデーション失敗が `{"error": {"code": "validation_error", "message": ...}}` と HTTP 422 を返す | UC-HAF-002 | TC-IT-HAF-003 |
| 4 | ハンドルされない例外が `{"error": {"code": "internal_error", "message": ...}}` と HTTP 500 を返す（スタックトレースを含まない） | UC-HAF-002 | TC-IT-HAF-004 |
| 5 | `GET /openapi.json` が HTTP 200 で JSON スキーマを返す | UC-HAF-003 | TC-ST-HAF-005 |
| 6 | `get_session()` DI が `AsyncSession` を yield し、リクエスト完了後に close される | UC-HAF-004 | TC-IT-HAF-006 |
| 7 | lifespan が起動時に session factory を初期化し、シャットダウン時に engine を dispose する | UC-HAF-001 | TC-IT-HAF-007 |
| 8 | 許可 Origin 以外からの POST リクエストが HTTP 403 を返す | （セキュリティ） | TC-IT-HAF-008 |

## 10. 開発者品質基準（CI 担保、業務要求ではない）

業務受入基準（§9）ではなく、CI が強制する開発者向けの品質基準。各 sub-feature の `test-design.md §カバレッジ基準` で参照する正式定義を以下に凍結する。

| 基準 ID | 名称 | 内容 |
|---|---|---|
| Q-1 | 型検査 / lint エラーゼロ | `pyright --strict` + `ruff check` が CI でエラーゼロであること |
| Q-2 | カバレッジ | interfaces 実装ファイル群 90% 以上（CI `pytest --cov` で担保）|
| Q-3 | 内部実装契約の物理保証 | エラーレスポンス形式（`{"error": {"code": ..., "message": ...}}`）/ 依存方向（interfaces 層から domain 層への直接 import ゼロ）/ T2 脅威（CSRF Origin 検証が 403 を返す）/ T3 脅威（レスポンスにスタックトレース非露出）— いずれも CI の実行時テストで物理確認する |

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | Phase 2 で Cookie セッション（Secure / HttpOnly / SameSite=Strict）を追加する際の `BAKUFU_TRUST_PROXY` 連動設計 | Phase 2 Issue |
| Q-OPEN-2 | WebSocket エンドポイントの Origin 検証（`Sec-WebSocket-Origin`）は本 feature の error_handlers と別配線が必要か | Phase 2 Issue |

## 12. Sub-issue 分割計画

| Sub-issue 名 | 紐付く UC | スコープ | 依存関係 |
|---|---|---|---|
| **A**: http-api（本 Issue #55） | UC-HAF-001〜004 | app.py / dependencies.py / error_handlers.py / schemas/common.py / routers/health.py / application/services/ 骨格 / main.py | persistence-foundation に依存 |

後続 Issue B〜G は本 Issue マージ後に着手（Individual Aggregate HTTP API）。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|---|---|---|
| HTTP リクエスト / レスポンス Body | JSON 形式の業務データ（後続 API で具体化） | 中（内容による） |
| `BAKUFU_ALLOWED_ORIGINS` | 許可 Origin リスト（環境変数） | 低 |
| エラーレスポンス | `{"error": {"code": ..., "message": ...}}`（スタックトレースを含まない） | 低 |

## 14. 非機能要求

| 区分 | 要求 |
|---|---|
| パフォーマンス | API 応答 p95 200ms 以下（[`docs/requirements/non-functional.md`](../../requirements/non-functional.md) §API 応答時間）|
| 可用性 | `GET /health` が uvicorn 起動後 5 秒以内に応答できること |
| 可搬性 | Python 3.12 / Linux / macOS。Windows は対象外 |
| セキュリティ | loopback バインド / CORS 制御 / CSRF Origin 検証 / エラー詳細（スタックトレース）の非露出（[`docs/design/threat-model.md`](../../design/threat-model.md) §A3）|
