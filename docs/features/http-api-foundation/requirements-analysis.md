# 要求分析書

> feature: `http-api-foundation`
> Issue: [#55 feat(http-api-foundation): FastAPI application foundation (M3)](https://github.com/bakufu-dev/bakufu/issues/55)
> 関連: [`docs/architecture/tech-stack.md`](../../architecture/tech-stack.md) §Backend / §ネットワーク・TLS方針 / §Admin CLI運用方針 / [`docs/architecture/context.md`](../../architecture/context.md) §8 非機能要件 / [`docs/architecture/mvp-scope.md`](../../architecture/mvp-scope.md) §M3完了基準

## 人間の要求

> Issue #55:
>
> M3 HTTP API フェーズの基盤となる FastAPI アプリケーション基盤を実装する。
> 具体的には FastAPI app 初期化・DI コンテナ・統一エラーハンドリング・ヘルスチェックエンドポイントを整備し、
> 後続 Issue B〜G（各 Aggregate HTTP API）の共通基盤を提供する。

## 背景・目的

### 現状の痛点

1. M2 完了で 7 Aggregate Repository が揃ったが、HTTP API 層が未実装のため UI 開発が開始できない
2. B〜G の各 Aggregate HTTP API が共通の DI/エラー処理/ページネーション基盤を必要とするが未統一であり、各担当者が独自実装するとコードの一貫性が失われるリスクがある

### 解決されれば変わること

- `/openapi.json` が生成され M4（Frontend）開発が開始できる
- B〜G の実装者が共通基盤（`dependencies.py` / `error_handlers.py` / `schemas/common.py`）を利用できる

### ビジネス価値

- M3 完了 → M4（WebSocket）→ M5（LLM Adapter）へのアンブロック
- MVP E2E フローのフロントエンド接続可能化

## 議論結果

### 設計担当による採用前提

- FastAPI + Pydantic v2（tech-stack.md 凍結済み）
- lifespan 方式でのエンジン・セッションファクトリ初期化（§確定 R1-A）
- request スコープ session（§確定 R1-B）
- offset ページネーション（§確定 R1-C）
- 環境変数バインド（§確定 R1-D）

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| `@app.on_event("startup")` | FastAPI 0.95+ で deprecated。lifespan の非同期コンテキストマネージャが公式推奨 |
| cursor-based pagination | MVP スケール（シングルユーザー、SQLite）では offset で十分。cursor は YAGNI |
| JWT 認証 | MVP はシングルユーザー・loopback バインドのため不要。BAKUFU_TRUST_PROXY=false で外部公開を安全デフォルト禁止（tech-stack.md §ネットワーク/TLS 方針） |
| global `Session` シングルトン | async 環境では request 外のコンテキストで誤用される危険。Depends(get_session) の yield パターンで scope を明確化 |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: lifespan 方式でのエンジン初期化

`@asynccontextmanager` デコレーターで `lifespan(app)` 関数を定義し、`AsyncEngine` 生成 → `async_sessionmaker` 生成 → `app.state` 格納 → `yield` → エンジン dispose の流れで初期化・終了処理を担う。`@app.on_event("startup")` は FastAPI 0.95+ で deprecated のため採用しない。

#### 確定 R1-B: request スコープ session

`get_session()` は `app.state.async_sessionmaker` から `AsyncSession` を yield する。1 HTTP リクエスト = 1 `AsyncSession`。リクエスト終了時に finally で session を close する。

#### 確定 R1-C: offset/limit ページネーション固定

`PaginatedResponse[T]` は `items / total / offset / limit` の 4 フィールド。cursor-based は MVP スケールで YAGNI。limit 上限は 100 とし DoS を防止する。

#### 確定 R1-D: bind 設定は環境変数

`BAKUFU_BIND_HOST`（デフォルト: `127.0.0.1`）/ `BAKUFU_BIND_PORT`（デフォルト: `8000`）を環境変数で制御する。既定は loopback バインド（外部公開は reverse proxy 前置きが必要）。

#### 確定 R1-E: エラーレスポンス形式

`{"error": {"code": "<error_code>", "message": "<human_readable>"}}` に統一。全エラーハンドラがこの形式を返す。

#### 確定 R1-F: CORS 設定

`BAKUFU_CORS_ORIGINS` 環境変数（カンマ区切り URL 列）で許可 Origin を制御。未設定デフォルトは `http://localhost:5173`（開発フロントエンドのみ許可）。

#### 確定 R1-G: 後続 Issue B〜G の DI 共有

後続 Issue B〜G の各 Aggregate HTTP API は `get_session()` を共有 DI で受け取る。各 service も同一 Depends 連鎖（`get_session` → `get_<name>_repository` → `get_<name>_service`）。

#### 確定 R1-H: application services の責務制限

application services の責務は Repository Port 経由の薄い CRUD のみ（M3 スコープ）。LLM Adapter 呼び出し・Notifier はスコープ外。service 内で `commit()` / `rollback()` は呼ばない。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO（ペルソナ A） | システムオーナー / 最終ユーザー | 非技術者または中級 | ローカル PC で bakufu を起動して AI チームを操作する | 設定なしで `python -m bakufu` が動き、API が叩ける状態にする |
| AI Agent（ペルソナ B） | 自律実行エージェント | N/A（コード生成） | HTTP API 経由で bakufu の状態を読み書きする | 安定した API インタフェースと一貫したエラーレスポンスを得る |
| 後続 Issue 実装担当（B〜G） | エンジニア / エージェント | 高（Python/FastAPI 経験あり） | Issue B〜G の各 Aggregate HTTP API を本基盤の上に実装する | 共通基盤が安定していて、`Depends(get_<name>_service)` を import するだけで実装を開始できる |

<!-- bakufu システム全体ペルソナは docs/architecture/context.md §4 を参照。本 feature で固有のペルソナがあればここに追加。 -->

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, uvicorn, uv（tech-stack.md）|
| 既存 CI | 7 ジョブ（branch-policy / pr-title-check / lint / typecheck / test-backend / test-frontend / audit）|
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 既定 loopback `127.0.0.1:8000`、外部公開は reverse proxy 前置き |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-HAF-001 | FastAPI アプリ初期化 | lifespan + CORS + router 登録 | 必須 |
| REQ-HAF-002 | DI コンテナ | `get_session()` / Repository / Service factory Depends | 必須 |
| REQ-HAF-003 | エラーハンドリング | 統一エラー形式変換ミドルウェア | 必須 |
| REQ-HAF-004 | 共通 Pydantic スキーマ | `PaginatedResponse[T]` / `ErrorResponse` | 必須 |
| REQ-HAF-005 | ヘルスチェック | `GET /health` → `{"status":"ok","version":"..."}` | 必須 |
| REQ-HAF-006 | uvicorn エントリポイント | `BAKUFU_BIND_HOST` / `BAKUFU_BIND_PORT` 環境変数 | 必須 |
| REQ-HAF-007 | application services 骨格 | 各 Aggregate の thin CRUD service インタフェース | 必須 |

<!-- ID 規則: REQ-<feature 略号 2 文字>-<3 桁連番>。例: REQ-EM-001（Empire）/ REQ-RM-001（Room）。-->

## Sub-issue 分割計画

該当なし — 理由: 本 Issue A が HTTP API 基盤全体を担う。REQ-HAF-001〜007 は密結合であり、単一 PR で実装・レビューすることで整合性を担保する。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| （本 Issue A のみ） | REQ-HAF-001〜007 | 基盤全体 | M2 Repository 実装完了が前提 |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | API 応答 p95 200ms 以下（context.md §8 準拠）|
| 可用性 | 127.0.0.1 loopback バインドのみ（ネットワーク断でも UI 操作可）|
| 保守性 | DI 一元化（`dependencies.py`）で後続 Issue B〜G が独立実装可能 |
| 可搬性 | Python 3.12+ / Windows・macOS・Linux 対応（tech-stack.md 凍結済み）|
| セキュリティ | loopback 既定。CORS 環境変数制御。認証は MVP 外（loopback + シングルユーザー設計）|

## 受入基準

<!-- E2E テストでブラックボックス検証可能な粒度。各受入基準は test-design.md の TC-E2E-XXX で 1 件以上検証される。 -->

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `GET /health` が `{"status":"ok"}` を含むレスポンスを返す | httpx TestClient |
| 2 | `/openapi.json` が HTTP 200 を返す | httpx TestClient |
| 3 | 不正な JSON ボディの POST が `{"error":{"code":"...","message":"..."}}` を返す | httpx TestClient |
| 4 | `BAKUFU_BIND_HOST` / `BAKUFU_BIND_PORT` で bind アドレスが変更できる | `main.py` 単体テスト |
| 5 | pyright 0 errors、CI 7 ジョブ全緑 | CI |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| API インフラ基盤 | FastAPI アプリケーション設定・ルーティング・DI 定義 | 低 |
| ヘルスチェックレスポンス | `{"status":"ok","version":"..."}` のみ（secret を含まない） | 低 |
| エラーレスポンス | コード + 人間可読メッセージのみ（スタックトレースは response body に含めない） | 低 |
