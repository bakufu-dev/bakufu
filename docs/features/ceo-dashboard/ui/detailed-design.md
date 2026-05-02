# 詳細設計書 — ceo-dashboard / ui

> feature: `ceo-dashboard` / sub-feature: `ui`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md)
> 基本設計: [`basic-design.md`](basic-design.md)
> 関連 Issue: [#167 feat(M6-B): React フロントエンドUI実装](https://github.com/bakufu-dev/bakufu/issues/167)

## 本書の役割

本書は **階層 3: ceo-dashboard / ui の詳細設計**（Detailed Design）を凍結する。基本設計（`basic-design.md`）で確立した構造契約を受け、**実装者が迷わずコーディングできるレベル**の確定事項を凍結する。

実装者への約束: 本書に書いた §確定 A〜G は実装が従うべき契約であり、実装者が勝手に改変できない。変更は本書の更新 PR のみで許可。

**書くこと**:
- §確定 A〜G: 実装判断の凍結（ルーティング / API クライアント / WebSocket / Gate 操作 / Directive 投入 / Markdown セキュリティ / 追加依存）
- API レスポンス型マッピング
- 状態管理の詳細

**書かないこと**:
- 疑似コード・実装サンプル（コードブロック）
- テスト設計（→ `test-design.md`）

## 記述ルール（必ず守ること）

本書に **疑似コード・サンプル実装（TypeScript / JSX 等の言語コードブロック）を書かない**。ソースコードと二重管理になりメンテナンスコストしか生まない。

---

## §確定 A: ルーティング構成（React Router 7 data router）

React Router 7 の `createBrowserRouter` を `frontend/src/router.ts` に定義し、`main.tsx` の `RouterProvider` に渡す。全ルートは 1 ファイルで集中管理する。

**ルート定義（凍結）**:

| パス | コンポーネント | loader 概要 |
|---|---|---|
| `/` | `Layout` > `TaskListPage` | `VITE_EMPIRE_ID` から rooms を取得し、各 room の tasks を取得 |
| `/tasks/:taskId` | `Layout` > `TaskDetailPage` | `GET /api/tasks/:taskId` + `GET /api/tasks/:taskId/gates` |
| `/gates/:gateId` | `Layout` > `ExternalReviewGatePage` | `GET /api/gates/:gateId` |
| `/directives/new` | `Layout` > `DirectiveNewPage` | `GET /api/empires/:empireId/rooms`（`VITE_EMPIRE_ID` 使用）|
| `*`（not found）| `Layout` > `NotFoundPage`（簡易 404）| なし |

**loader の使い方**:
- React Router 7 の `loader` 関数を各ルートに定義し、ページコンポーネントは `useLoaderData()` で初期データを受け取る
- 初期ロード後の再取得（WebSocket イベント受信時）は React Query の `queryClient.invalidateQueries()` で行う（loader と React Query の二重管理をしない — loader は SSR 的な初期データ注入、React Query は以降の状態管理）
- loader 内のエラー（404 等）は `ErrorBoundary` が catch し `InlineError` を表示する

## §確定 B: API クライアント設計

`frontend/src/api/client.ts` に fetch ラッパ `apiClient` を定義する。全コンポーネント・Hooks は `apiClient` 経由でのみバックエンドを呼び出す。直接 `fetch()` を書くことは禁止。

**設計凍結点**:

| 項目 | 内容 |
|---|---|
| ベース URL | `import.meta.env.VITE_API_BASE_URL`（例: `http://localhost:8000`）|
| リクエストヘッダ | `Content-Type: application/json` を全リクエストに付与 |
| エラー型 | `ApiError { code: string; message: string; status: number }` — バックエンドの `{"error": {"code": ..., "message": ...}}` をパースして構築 |
| fetch でのエラー検出 | `response.ok === false` を検知 → `ApiError` を throw |
| ネットワークエラー | `fetch` 自体が throw した場合（ネットワーク到達不能等）→ 上位に再 throw（`InlineError` が「サーバーに接続できません」を表示）|

**バックエンド API エンドポイントマッピング（凍結）**:

| 用途 | HTTP メソッド | パス | レスポンス型 |
|---|---|---|---|
| Task 単件取得 | GET | `/api/tasks/{task_id}` | `TaskResponse` |
| Room の Task 一覧 | GET | `/api/rooms/{room_id}/tasks` | `TaskListResponse` |
| Task の Gate 履歴 | GET | `/api/tasks/{task_id}/gates` | `GateListResponse` |
| Gate 単件取得 | GET | `/api/gates/{gate_id}` | `GateDetailResponse` |
| Gate 承認 | POST | `/api/gates/{gate_id}/approve` | `GateDetailResponse` |
| Gate 差し戻し | POST | `/api/gates/{gate_id}/reject` | `GateDetailResponse` |
| Gate キャンセル | POST | `/api/gates/{gate_id}/cancel` | `GateDetailResponse` |
| Empire の Room 一覧 | GET | `/api/empires/{empire_id}/rooms` | `RoomListResponse` |
| Directive 投入 | POST | `/api/rooms/{room_id}/directives` | `DirectiveWithTaskResponse` |

**フロントエンド型定義の管理**:

- `frontend/src/api/types.ts` に、上記 API のレスポンス型を TypeScript interface として定義する
- バックエンドの Pydantic スキーマと 1:1 対応させる（OpenAPI スキーマ自動生成は MVP スコープ外 — 手動定義で充足）
- 型名のプレフィックス: フロントエンド型には `Api` プレフィックスを付与しない（バックエンドと同名で混乱リスクより一致性を優先）

## §確定 C: WebSocket 再接続戦略（凍結）

`frontend/src/hooks/useWebSocketBus.ts` が Singleton WebSocket 接続を管理する。React Context（`WebSocketProvider`）経由でアプリ全体に接続状態とイベント購読手段を提供する。

**接続ライフサイクル**:

| ステップ | 内容 |
|---|---|
| 接続先 | `VITE_API_BASE_URL` の `http://` を `ws://`（または `https://` → `wss://`）に変換し、`/ws` を付加 |
| 初回接続 | `WebSocketProvider` の mount 時に `new WebSocket(url)` を生成 |
| 切断検知 | `ws.onclose` / `ws.onerror` で切断を検知 → `state = "reconnecting"` |
| reconnect バックオフ（凍結）| `[1000, 2000, 4000, 8000, 16000, 30000]` ms の配列を順に使用。30000 ms に到達後は 30000 ms 固定でリトライを継続（上限なし）|
| 再接続成功後 | `state = "connected"` + `queryClient.invalidateQueries()` 全クエリを再検証 |

**イベントルーティング（凍結）**:

バックエンドから受信する WebSocket メッセージは JSON 形式。フィールド構造:

| フィールド | 型 | 内容 |
|---|---|---|
| `event_type` | string | `"TaskStateChangedEvent"` / `"ExternalReviewGateStateChangedEvent"` 等 |
| `aggregate_type` | string | `"Task"` / `"ExternalReviewGate"` / `"Agent"` / `"Directive"` |
| `aggregate_id` | string（UUID）| 変化した Aggregate の ID |
| `payload` | object | イベント固有の追加フィールド（`old_status` / `new_status` 等）|

**invalidate ルール（凍結）**:

`useTasks` の queryKey は `["tasks", roomId]`（Room スコープ）。WebSocket invalidate での `["tasks"]` はその **プレフィックス**。React Query は `queryClient.invalidateQueries({ queryKey: ["tasks"] })` の呼び出しで、queryKey が `["tasks", *]` に前方一致する全クエリ（全 Room の Task 一覧）を再検証する。これにより全 Room をループして個別 invalidate する必要がない。

| `aggregate_type` | invalidate する queryKey | 備考 |
|---|---|---|
| `"Task"` | `["task", aggregate_id]` + `["tasks"]`（プレフィックス一致: `["tasks", roomId]` の全 Room 分を再検証）| Task 単件 + 一覧の両方を最新化 |
| `"ExternalReviewGate"` | `["gate", aggregate_id]` + `["task", payload.task_id]`（Task 詳細も再取得）| Gate 変化は Task status 変化を伴う |
| `"Agent"` | `["tasks"]`（プレフィックス一致: 全 Room の Task 一覧を再検証）| Agent ステータス変化が Task 詳細に波及する可能性 |
| `"Directive"` | `["tasks"]`（プレフィックス一致: 全 Room の Task 一覧を再検証）| Directive 完了 → Task status 変化 |

## §確定 D: Gate 操作フロー詳細

`GateActionForm` コンポーネントと `useGateAction` hook の契約を凍結する。

**状態管理**:

| state | 型 | 初期値 | 遷移 |
|---|---|---|---|
| `isSubmitting` | boolean | false | API call 開始時 true → 完了（成功 / 失敗）時 false |
| `error` | `ApiError \| null` | null | エラー発生時に設定 / 再送信時にクリア |

**approve フロー（凍結）**:

1. `approve` ボタン押下 → `isSubmitting = true`（ボタン disabled）
2. `POST /api/gates/{id}/approve { "comment": comment }` を `apiClient` 経由で呼ぶ
3. 成功（200）: `queryClient.invalidateQueries(["gate", gateId])` → `navigate(-1)`（前の Task 詳細へ）
4. 失敗: `isSubmitting = false` + `error` にセット → `InlineError` 表示

**reject フロー（凍結）**:

1. `feedback_text` が空の場合: submit 前にクライアントバリデーションで `InlineError`（「差し戻し理由を入力してください」）→ submit しない
2. `feedback_text` が 1 文字以上: `isSubmitting = true` → `POST /api/gates/{id}/reject { "feedback_text": feedbackText }`
3. 成功（200）: `queryClient.invalidateQueries(["gate", gateId])` → `navigate(-1)`
4. 失敗: `isSubmitting = false` + `error` 表示

**cancel フロー（凍結）**:

1. `reason` は任意（空文字も許容）
2. `POST /api/gates/{id}/cancel { "reason": reason }`
3. 成功（200）: `queryClient.invalidateQueries(["gate", gateId])` → `navigate(-1)`

**Gate が PENDING でない場合（凍結）**:

- `GateDetailResponse.decision` が `"PENDING"` でない場合、`GateActionForm` を readonly モードで表示（`decision` 結果と `decided_at` を表示、操作ボタンは非表示）

## §確定 E: Directive 投入フロー詳細

`DirectiveForm` コンポーネントと `useDirectiveSubmit` hook の契約を凍結する。

**`VITE_EMPIRE_ID` 未設定の扱い（凍結）**:

- `DirectiveNewPage` の mount 時に `import.meta.env.VITE_EMPIRE_ID` の存在を確認
- 未設定の場合: フォームを表示せず「VITE_EMPIRE_ID が設定されていません。`frontend/.env` を確認してください。」をエラー表示して終了
- 設定済みの場合: `GET /api/empires/{empireId}/rooms` で Room 一覧を取得し `<select>` に表示

**送信フロー（凍結）**:

1. Room 未選択のまま submit → クライアントバリデーション警告（「Room を選択してください」）
2. テキスト空のまま submit → クライアントバリデーション警告（「Directive テキストを入力してください」）
3. 両方入力済み: `isSubmitting = true` → `POST /api/rooms/{roomId}/directives { "text": text }`
4. 成功（201）: `queryClient.invalidateQueries({ queryKey: ["tasks"] })`（プレフィックス一致で全 Room の Task 一覧を再検証）+ `navigate("/")`（Task 一覧へ遷移）
5. 失敗: `isSubmitting = false` + `InlineError` 表示

## §確定 F: Markdown セキュリティ（XSS 防止）

`DeliverableViewer` は `react-markdown` を使用する。AI 生成の `body_markdown` / `deliverable_snapshot.body_markdown` には任意の HTML タグが混入し得るため、XSS 対策を必ず適用する。

**凍結ルール**:

| 項目 | 内容 |
|---|---|
| sanitize プラグイン | `rehype-sanitize` を `rehypePlugins` に必ず設定する（DOMPurify 相当）|
| `allowedElements` | `rehype-sanitize` の `defaultSchema` を使用（`script` / `iframe` / `style` タグは除外済み）|
| `dangerouslySetInnerHTML` 禁止 | `react-markdown` の外で `dangerouslySetInnerHTML` を使うことは禁止 |
| `<REDACTED:...>` の扱い | 文字列そのまま表示（置換しない）。sanitize 後にテキストとして残る |

**根拠**: LLM 成果物（`body_markdown`）は外部入力と同等の信頼度であり、XSS 攻撃の経路になり得る（`docs/design/threat-model.md §A3` 参照）。`rehype-sanitize` がデフォルト許可リスト（`p` / `h1〜h6` / `ul` / `ol` / `li` / `code` / `pre` / `blockquote` / `a` 等）のみを通過させる。

## §確定 G: 追加依存ライブラリの凍結

`package.json` に追加する依存ライブラリを確定する。**実装者はここに記載されていないライブラリを勝手に追加してはならない**。追加が必要な場合は設計書更新 PR を先行させる。

| パッケージ | バージョン方針 | 区分 | 用途 |
|---|---|---|---|
| `@tanstack/react-query` | `^5.0.0` | dependencies | サーバ状態管理（React Query v5）|
| `zustand` | `^4.0.0` | dependencies | WebSocket 接続状態のクライアント状態管理 |
| `tailwindcss` | `^4.0.0` | devDependencies | ユーティリティ CSS |
| `@tailwindcss/vite` | `^4.0.0` | devDependencies | Vite 向け Tailwind プラグイン |
| `react-markdown` | `^9.0.0` | dependencies | Markdown レンダリング |
| `rehype-sanitize` | `^6.0.0` | dependencies | Markdown XSS サニタイズ（§確定 F）|

**インストール対象から除外するもの（YAGNI）**:

| パッケージ | 除外理由 |
|---|---|
| axios | `fetch` API で充足。追加ライブラリ不要 |
| react-query-devtools | MVP では不要。Phase 2 以降でデバッグ用に追加可 |
| PixiJS | Phase 2（ピクセルアート視覚化）。MVP 外 |

## API レスポンス型定義（フロントエンド用）

`frontend/src/api/types.ts` で定義するフロントエンド型の凍結。バックエンド Pydantic スキーマと 1:1 対応する。

### TaskResponse

| フィールド | 型 | 内容 |
|---|---|---|
| `id` | string（UUID）| Task ID |
| `status` | `"PENDING" \| "IN_PROGRESS" \| "AWAITING_EXTERNAL_REVIEW" \| "DONE" \| "BLOCKED" \| "CANCELLED"` | Task 状態 |
| `room_id` | string（UUID）| 所属 Room |
| `directive_id` | string（UUID）| 起票 Directive |
| `current_stage_id` | string（UUID）| 現在の Stage ID |
| `directive_text` | string | CEO の指示テキスト（表示用）|
| `last_error` | `string \| null` | BLOCKED 時のエラー情報（masking 済み）|
| `created_at` | string（ISO 8601）| 起票日時 |
| `updated_at` | string（ISO 8601）| 最終更新日時 |

### GateDetailResponse

| フィールド | 型 | 内容 |
|---|---|---|
| `id` | string（UUID）| Gate ID |
| `task_id` | string（UUID）| 関連 Task |
| `stage_id` | string（UUID）| 対象 Stage |
| `decision` | `"PENDING" \| "APPROVED" \| "REJECTED" \| "CANCELLED"` | Gate 状態 |
| `deliverable_snapshot` | `DeliverableSnapshotResponse` | Deliverable スナップショット |
| `audit_trail` | `AuditEntryResponse[]` | 操作履歴 |
| `required_gate_roles` | `string[]` | 必要な GateRole 一覧（InternalReview 用）|
| `created_at` | string（ISO 8601）| 生成日時 |

### AuditEntryResponse

| フィールド | 型 | 内容 |
|---|---|---|
| `action` | string | `"VIEW"` / `"APPROVE"` / `"REJECT"` / `"CANCEL"` |
| `reviewer_id` | string（UUID）| 操作者 ID |
| `comment` | `string \| null` | approve コメント |
| `feedback_text` | `string \| null` | reject 理由 |
| `decided_at` | string（ISO 8601）| 操作日時 |

## §確定 H: キーボード操作・フォーカス仕様（Rams指摘 ①対応）

アクセシビリティは後付けで構造を変えるほど負債になる。MVP であっても主要操作（Gate 承認/差し戻し・Directive 投入）のキーボード操作を設計時に凍結し、実装担当が迷わない状態にする。

**フォーカス順序（凍結）**:

| 画面 | Tab 移動順序 |
|---|---|
| Gate 詳細（`/gates/:gateId`）| ① comment / feedback_text 入力欄 → ② approve ボタン → ③ reject ボタン → ④ cancel ボタン |
| Directive 投入（`/directives/new`）| ① Room `<select>` → ② テキストエリア → ③ 送信ボタン |
| Task 一覧（`/`）| ① Task カード（Tab で順次フォーカス移動）→ ② 各カードは Enter で Task 詳細へ遷移 |

**キー操作（凍結）**:

| 要素 | キー | 挙動 |
|---|---|---|
| approve / reject / cancel ボタン | `Enter` / `Space` | クリックと同等の操作を発火 |
| `isSubmitting=true` の disabled ボタン | `Enter` / `Space` | 無効（disabled 中は不動）|
| Room `<select>` | `↑` / `↓` | ブラウザネイティブ select 操作 |
| Task カード（`<a>` or `role=link` 要素）| `Enter` | Task 詳細ページへ遷移 |

**ARIA 要件（凍結）**:

| コンポーネント | ARIA 属性 |
|---|---|
| `StatusBadge` | `aria-label="{status名}"` を付与（色だけでなく文字列でも状態を通知）|
| `ConnectionIndicator` | `role="status"` + `aria-live="polite"` で接続状態変化をスクリーンリーダーに通知 |
| `InlineError` | `role="alert"` + `aria-live="assertive"` でエラーを即時通知 |
| 操作中 disable ボタン | `aria-disabled="true"` + `aria-busy="true"` |
| `GateActionForm` ボタン群 | `aria-describedby` で deliverable_snapshot のコンテナを参照（何を見て判断しているかの文脈を提供）|

**根拠**: Rams指摘「アクセシビリティは後から構造を追加するほど負債になる」。Tab/Enter/Space は HTML 標準要素（`<button>` / `<a>` / `<select>`）を使う限りブラウザが自動保証するため、追加実装コストはほぼゼロ。一方 ARIA 属性は実装担当に明示しないと省略される。本 §で凍結することで省略を設計レベルで防ぐ。

## ユーザー向けメッセージ確定文言（フロントエンド）

| ID | 表示条件 | 文言 |
|---|---|---|
| MSG-CD-UI-001 | `VITE_EMPIRE_ID` 未設定 | `VITE_EMPIRE_ID が設定されていません。frontend/.env に VITE_EMPIRE_ID=<uuid> を追加してください。` |
| MSG-CD-UI-002 | reject 時の feedback_text 空 | `差し戻し理由を入力してください。` |
| MSG-CD-UI-003 | Directive 投入 Room 未選択 | `Room を選択してください。` |
| MSG-CD-UI-004 | Directive テキスト空 | `Directive テキストを入力してください。` |
| MSG-CD-UI-005 | WebSocket 切断中 | `サーバーとの接続が切断されました。再接続中...` |
| MSG-CD-UI-006 | ネットワークエラー（fetch throw）| `サーバーに接続できません。バックエンドが起動しているか確認してください。` |

## 設計判断の補足

### なぜ React Query + Zustand の組み合わせか

サーバ状態（Task / Gate / Room の取得・更新）は React Query（TanStack Query v5）が担う。React Query はキャッシュ / 再検証 / エラー状態管理を一元化し、WebSocket イベント受信時の `invalidateQueries()` と相性が良い。

WebSocket 接続状態（connected / disconnected / reconnecting）はクライアント側の純粋な UI 状態であり、サーバから取得するデータではない。Zustand の小さなストアで管理することで、React Query のサーバ状態と明確に責務分離できる（「サーバ状態は React Query、クライアント UI 状態は Zustand」の二元管理）。Redux は MVP のスケールに対してオーバースペックであり YAGNI 違反のため不採用。

### なぜ loader + React Query の混在か

React Router 7 の `loader` はページ初期ロード時のデータ取得に使い、ページコンポーネントが `useLoaderData()` で初期データを受け取る（ウォーターフォール防止）。WebSocket イベント受信時の再取得は `queryClient.invalidateQueries()` で行う。

二重取得を避けるため、`loader` 内では `queryClient.ensureQueryData()` を使い、React Query のキャッシュがある場合はネットワークリクエストをスキップする。これにより「loader がキャッシュ戦略を壊す」問題を回避できる（[TanStack Query 公式ガイドのルーター統合パターン](https://tanstack.com/query/v5/docs/framework/react/plugins/persistQueryClient#usage-with-react-router)）。

### なぜ rehype-sanitize を必須化するか

`deliverable_snapshot.body_markdown` は LLM が生成したコンテンツであり、悪意ある Workflow 設定 / プロンプトインジェクション経由で `<script>` タグが混入する可能性を排除できない。`react-markdown` のデフォルト設定はスクリプト実行を防ぐが、`<style>` タグや event handler 属性（`onmouseover` 等）は通過させる実装が存在するため、`rehype-sanitize` の明示的な allowlist 適用が必要（`threat-model.md §A3` 対応）。
