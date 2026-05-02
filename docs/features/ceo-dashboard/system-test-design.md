# システムテスト設計書 — ceo-dashboard

> feature: `ceo-dashboard`
> 親業務仕様: [`feature-spec.md`](feature-spec.md)
> 関連 Issue: [#167 feat(M6-B): React フロントエンドUI実装](https://github.com/bakufu-dev/bakufu/issues/167)

## 本書の役割

本書は **ceo-dashboard の E2E（システム）テスト戦略** を凍結する。Vモデル右側の「要件定義 ↔ E2E テスト」対応として、[`feature-spec.md`](feature-spec.md) の受入基準 #1〜#14 を E2E で検証するテストシナリオを定義する。

sub-feature の IT / UT は [`ui/test-design.md`](ui/test-design.md) で扱う（テスト担当作成）。

## テスト方針

| 観点 | 採用方針 |
|---|---|
| E2E フレームワーク | Playwright（`@playwright/test`）— ブラウザ実行でリアルな DOM / WebSocket 操作が可能 |
| バックエンド | 実バックエンド起動（`docker compose up`）+ SQLite テスト用 DB |
| フロントエンド | `vite dev` または `vite preview` 起動状態でアクセス |
| 並列実行 | 各テストは独立 Empire + Room + Task をセットアップして互いに干渉しない |
| WebSocket テスト | Playwright の `page.waitForEvent` / `page.waitForSelector` でイベント反映を確認 |

## E2E テストシナリオ

### TC-E2E-CD-001: Task 一覧表示（受入基準 #1）

| 項目 | 内容 |
|---|---|
| 前提条件 | バックエンドが起動済み。Room に PENDING / IN_PROGRESS / DONE の各 status Task が 1 件ずつ存在する |
| 手順 | `http://localhost:5173/` にアクセスする |
| 期待結果 | 3 件の Task カードが表示され、それぞれ status に対応するバッジ色（gray / blue / green）が表示される |

### TC-E2E-CD-002: Task 詳細 — Stage 進行状況表示（受入基準 #2）

| 項目 | 内容 |
|---|---|
| 前提条件 | IN_PROGRESS の Task が存在し、2 Stage 以上の Workflow を持つ |
| 手順 | Task 詳細画面（`/tasks/:taskId`）にアクセスする |
| 期待結果 | Stage 名と status バッジ（完了 / 進行中 / 未着手）のリストが表示される |

### TC-E2E-CD-003: Task 詳細 — Deliverable 表示（受入基準 #3）

| 項目 | 内容 |
|---|---|
| 前提条件 | 直近 Stage に deliverable（body_markdown あり）が commit 済みの Task |
| 手順 | Task 詳細画面にアクセスする |
| 期待結果 | `body_markdown` が Markdown レンダリングされて表示される（`<h1>` / `<p>` 等の HTML タグで確認）|

### TC-E2E-CD-004: Task 詳細 — Gate リンク表示（受入基準 #4）

| 項目 | 内容 |
|---|---|
| 前提条件 | AWAITING_EXTERNAL_REVIEW の Task に PENDING Gate が存在する |
| 手順 | Task 詳細画面にアクセスする |
| 期待結果 | Gate 詳細への遷移リンクが表示される |

### TC-E2E-CD-005: Gate 承認（受入基準 #5 #7）

| 項目 | 内容 |
|---|---|
| 前提条件 | PENDING Gate が存在し、deliverable_snapshot.body_markdown に内容あり |
| 手順 | Gate 詳細画面にアクセス → Markdown 本文を確認 → approve ボタンをクリック |
| 期待結果 | Gate status が APPROVED に変化し、Task 詳細画面でも status が次 Stage または DONE に更新されている |

### TC-E2E-CD-006: Gate 差し戻し（受入基準 #8 #9）

| 項目 | 内容 |
|---|---|
| 前提条件 | PENDING Gate が存在する |
| 手順 | Gate 詳細画面で feedback_text 入力後に reject ボタンをクリック |
| 期待結果 | Gate status が REJECTED に変化し、Task が前段 Stage の IN_PROGRESS に戻る |
| 追加確認 | feedback_text が空のまま reject を試みた場合、UI 警告が表示されサブミットされない |

### TC-E2E-CD-007: 二重送信防止（受入基準 #10）

| 項目 | 内容 |
|---|---|
| 前提条件 | PENDING Gate が存在する |
| 手順 | approve ボタンをクリックした直後（API レスポンス前）に再度クリックを試みる |
| 期待結果 | ボタンが disabled 状態であり、2 度目のクリックは無効になる |

### TC-E2E-CD-008: Directive 投入（受入基準 #11）

| 項目 | 内容 |
|---|---|
| 前提条件 | `VITE_EMPIRE_ID` が設定済みで、Empire に Room が 1 件以上存在する |
| 手順 | `/directives/new` で Room 選択 → テキスト入力 → 送信 |
| 期待結果 | `POST /api/rooms/{room_id}/directives` 201 が返り、`/` の Task 一覧に新規 Task が追加される |

### TC-E2E-CD-009: WebSocket リアルタイム更新（受入基準 #12）

| 項目 | 内容 |
|---|---|
| 前提条件 | Task 一覧画面が表示済み |
| 手順 | バックエンド側で Task status を変更する（テスト用 API / seed）|
| 期待結果 | 画面をリロードせず、Task カードの status バッジが更新される |

### TC-E2E-CD-010: WebSocket 切断 / 再接続（受入基準 #13）

| 項目 | 内容 |
|---|---|
| 前提条件 | フロントエンドが起動済みで WebSocket 接続確立済み |
| 手順 | バックエンドを一時停止（`docker compose pause backend`）→ 数秒待機 → 再開（`docker compose unpause backend`）|
| 期待結果 | 切断中に「切断中」インジケータが表示され、再接続後に「接続済み」に戻る |

### TC-E2E-CD-011: API エラー表示（受入基準 #14）

| 項目 | 内容 |
|---|---|
| 前提条件 | なし |
| 手順 | 存在しない Gate ID で Gate 詳細画面（`/gates/00000000-0000-0000-0000-000000000000`）にアクセスする |
| 期待結果 | 404 エラーメッセージがインライン表示される |

## テスト優先順位

| 優先度 | シナリオ | 理由 |
|---|---|---|
| P0（必須）| TC-E2E-CD-005 / -006 / -008 | MVP の核心機能（Gate 操作 + Directive 投入）|
| P0（必須）| TC-E2E-CD-009 | 受入基準 #9 WebSocket リアルタイム更新 |
| P1（高）| TC-E2E-CD-001 / -002 / -003 / -007 | 基本表示 + 安全性 |
| P2（中）| TC-E2E-CD-010 / -011 | エラーハンドリング・再接続 |
