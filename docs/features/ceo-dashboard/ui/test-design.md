# テスト設計書 — ceo-dashboard / ui

> feature: `ceo-dashboard` / sub-feature: `ui`
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`detailed-design.md`](detailed-design.md) / [`../feature-spec.md`](../feature-spec.md)
> 担当 Issue: [#167 feat(M6-B): React フロントエンドUI実装](https://github.com/bakufu-dev/bakufu/issues/167)

## 本書の役割

本書は **ceo-dashboard / ui sub-feature の IT（結合テスト）と UT（単体テスト）** を凍結する。システムテスト（TC-E2E-CD-001〜011）は [`../system-test-design.md`](../system-test-design.md) が担当する。本書が担う IT/UT は `basic-design.md §モジュール契約`（REQ-CD-UI-001〜006）・`detailed-design.md §確定 A〜G`・MSG-CD-UI-001〜006・脅威 T1（XSS）・T2（CORS）を網羅し、Playwright E2E では検証しにくいレイヤー（Hook の状態機械・クライアントバリデーション・Markdown サニタイズロジック）を補完する。

**書くこと**:
- REQ-CD-UI-NNN / §確定 X / MSG-CD-UI-NNN / 受入基準 # / 脅威 T を実テストケース（TC-IT / TC-UT）に紐付けるマトリクス
- 外部 I/O 依存マップ（Mock 戦略 / MSW ハンドラ / WebSocket モック）
- 結合テストケース（IT）: カスタム Hook × Mock バックエンド
- ユニットテストケース（UT）: コンポーネント / 純粋関数の正常系・異常系・エッジケース
- カバレッジ基準

**書かないこと**:
- システムテスト（Playwright E2E）→ 親 [`../system-test-design.md`](../system-test-design.md)
- 受入テスト → [`docs/acceptance-tests/scenarios/`](../../../acceptance-tests/scenarios/)

## テスト方針

| レベル | 対象 | 手段 |
|-------|------|------|
| IT（結合）| カスタム Hooks（`useWebSocketBus` / `useGateAction` / `useDirectiveSubmit` / `useTasks` 等）+ `apiClient` + React Router | vitest + `@testing-library/react` `renderHook` + MSW ハンドラ（HTTP mock）+ WebSocket テストダブル |
| UT（単体）| 個別コンポーネント（`StatusBadge` / `GateActionForm` / `DeliverableViewer` / `DirectiveForm` / `ConnectionIndicator`）+ 純粋関数 | vitest + `@testing-library/react` `render` + `vi.stubEnv` |

**MSW（Mock Service Worker）を使う理由**: `apiClient` は `fetch` を直接呼ぶため、`vi.fn()` で `fetch` を差し替えると URL マッチングや状態コードのシミュレーションが複雑になる。MSW の `http.get` / `http.post` ハンドラはネットワーク境界でインターセプトし、実際の `fetch` を通過させるため、`apiClient` の `response.ok` 判定・`ApiError` 生成ロジックを完全に検証できる。

**WebSocket テストダブルを使う理由**: `useWebSocketBus` は `global.WebSocket` に依存する。テストでは `vi.stubGlobal('WebSocket', MockWebSocket)` で差し替え、`MockWebSocket` がイベント（`onopen` / `onclose` / `onmessage`）をテストから制御できるように実装する。これにより切断・再接続バックオフ・キャッシュ invalidation の状態遷移を決定的に検証できる。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|---|---|---|---|---|---|
| REQ-CD-UI-001 | `TaskListPage` / `useTasks` | TC-IT-CD-001, TC-IT-CD-002 | IT | 正常系 / 異常系 | feature-spec.md §8 #1 |
| REQ-CD-UI-002 | `TaskDetailPage` / `useTask` | TC-IT-CD-003 | IT | 正常系 | feature-spec.md §8 #2, #3, #4 |
| REQ-CD-UI-003 | `ExternalReviewGatePage` / `useGate` | TC-IT-CD-004 | IT | 正常系 | feature-spec.md §8 #5, #6 |
| REQ-CD-UI-004 | `DirectiveNewPage` / `useRooms` | TC-IT-CD-012 | IT | 正常系 | feature-spec.md §8 #11 |
| REQ-CD-UI-005 | `useWebSocketBus` / `ConnectionIndicator` | TC-IT-CD-007, TC-IT-CD-008, TC-IT-CD-009, TC-IT-CD-010, TC-IT-CD-011 | IT | 正常系 / 異常系 | feature-spec.md §8 #12, #13 |
| REQ-CD-UI-006 | `StatusBadge` | TC-UT-CD-001〜006 | UT | 正常系 | feature-spec.md §8 #1 |
| §確定 B | `apiClient` | TC-IT-CD-005, TC-IT-CD-006 | IT | 正常系 / 異常系 | feature-spec.md R1-5 |
| §確定 C | `useWebSocketBus` 再接続バックオフ | TC-IT-CD-008, TC-IT-CD-009, TC-IT-CD-018 | IT | 異常系 / 境界値 | feature-spec.md R1-1 |
| §確定 C（Agent / Directive invalidate）| `useWebSocketBus` イベントルーティング | TC-IT-CD-010, TC-IT-CD-011, TC-IT-CD-019, TC-IT-CD-020 | IT | 正常系 | feature-spec.md §8 #12 |
| §確定 D | `GateActionForm` / `useGateAction` | TC-IT-CD-013, TC-IT-CD-014, TC-IT-CD-015, TC-UT-CD-010, TC-UT-CD-011, TC-UT-CD-012 | IT / UT | 正常系 / 異常系 | feature-spec.md §8 #7, #8, #9, #10 |
| §確定 E | `DirectiveForm` / `useDirectiveSubmit` | TC-IT-CD-016, TC-IT-CD-017, TC-UT-CD-013, TC-UT-CD-014, TC-UT-CD-015 | IT / UT | 正常系 / 異常系 | feature-spec.md §8 #11 |
| §確定 F | `DeliverableViewer` | TC-UT-CD-007, TC-UT-CD-008, TC-UT-CD-009 | UT | 正常系 / セキュリティ | — |
| MSG-CD-UI-001 | `DirectiveNewPage` エラーメッセージ | TC-UT-CD-018 | UT | 文言照合 | — |
| MSG-CD-UI-002 | `GateActionForm` reject 空入力警告 | TC-UT-CD-010, TC-UT-CD-019 | UT | 文言照合 | feature-spec.md §8 #9 |
| MSG-CD-UI-003 | `DirectiveForm` Room 未選択警告 | TC-UT-CD-013, TC-UT-CD-020 | UT | 文言照合 | — |
| MSG-CD-UI-004 | `DirectiveForm` テキスト空警告 | TC-UT-CD-014, TC-UT-CD-021 | UT | 文言照合 | — |
| MSG-CD-UI-005 | `ConnectionIndicator` 切断中テキスト | TC-UT-CD-016, TC-UT-CD-022 | UT | 文言照合 | feature-spec.md §8 #13 |
| MSG-CD-UI-006 | `InlineError` ネットワーク不達テキスト | TC-IT-CD-006, TC-UT-CD-023 | IT / UT | 文言照合 | feature-spec.md R1-5 |
| T1: XSS（LLM 出力）| `DeliverableViewer` + `rehype-sanitize` | TC-UT-CD-008 | UT | セキュリティ | basic-design.md §セキュリティ設計 |
| T2: CORS（API クライアント境界）| `apiClient` ベース URL 制限 | TC-IT-CD-005 | IT | セキュリティ | basic-design.md §セキュリティ設計 |
| R1-2: 二重送信防止 | `GateActionForm` ボタン disabled | TC-UT-CD-011 | UT | 異常系 | feature-spec.md §8 #10 |
| R1-3: reject feedback_text 必須 | `GateActionForm` クライアントバリデーション | TC-UT-CD-010 | UT | 異常系 | feature-spec.md §8 #9 |
| R1-4: `<REDACTED:...>` そのまま表示 | `DeliverableViewer` | TC-UT-CD-009 | UT | 正常系 | — |
| R1-7: Directive 投入 Room 選択必須 | `DirectiveForm` / `DirectiveNewPage` | TC-UT-CD-013, TC-UT-CD-015 | UT | 異常系 | — |

**マトリクス充足の証拠**:
- REQ-CD-UI-001 〜 REQ-CD-UI-006 全てに IT または UT テストケース（最低 1 件）
- §確定 B / C / D / E / F 全てに IT または UT テストケース（最低 1 件）
- §確定 C backoff 上限境界値（30000ms 固定 + 上限なし継続）が TC-IT-CD-018 で検証される
- §確定 C `Agent` / `Directive` イベントルーティングが TC-IT-CD-019 / TC-IT-CD-020 で検証される
- MSG-CD-UI-001 〜 006 全てに文言照合テスト
- T1（XSS）に有効性確認テスト（TC-UT-CD-008）
- T2（CORS）を apiClient ベース URL テスト（TC-IT-CD-005）で補完
- 親受入基準 #1〜#14 のうち IT/UT で直接検証可能なもの（#1, #7, #8, #9, #10, #11）をカバー（#12, #13 は system-test-design.md が Playwright E2E で担当）

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory / mock | テスト戦略 |
|---|---|---|---|---|
| Backend REST API（`fetch`）| Task / Gate / Room / Directive の取得・操作 | — | MSW ハンドラ（`http.get` / `http.post`）をテストごとに定義 | `setupServer()` をグローバル setup に登録。テストごとに `server.use(...)` でハンドラをオーバーライド |
| WebSocket（`ws://`）| リアルタイムイベント受信 | — | `MockWebSocket` クラス（`vi.stubGlobal('WebSocket', MockWebSocket)`）| テストから `mockWs.dispatchEvent('open')` / `'close'` / `'message'` を制御。バックオフタイマーは `vi.useFakeTimers()` で制御 |
| React Router（`navigate`）| ページ遷移（Directive 投入後 / Gate 操作後）| — | `createMemoryRouter` + `RouterProvider`（`@testing-library/react`）| ナビゲーション先 URL を `router.state.location.pathname` で検証 |
| `import.meta.env.VITE_EMPIRE_ID` / `VITE_API_BASE_URL` | API ベース URL / Empire ID 解決 | — | `vi.stubEnv('VITE_EMPIRE_ID', 'test-empire-id')` | テスト固有値を per-test で注入。teardown で `vi.unstubAllEnvs()` |

**外部 DB 依存なし**。本 sub-feature はフロントエンド SPA のみであり、新規テーブルを持たない（バックエンド永続化は既実装 API で担う）。Characterization fixture は不要。

**注意**: MSW の `setupServer()` は Node.js テスト環境（vitest）で動作する `@msw/node` を使用する。ブラウザ（Service Worker）モードではない。

## 結合テストケース（IT）

テストファイル: `frontend/src/__tests__/integration/`

### TC-IT-CD-001: `useTasks` — 全 Room の Task を並列取得して返す（REQ-CD-UI-001）

| 項目 | 内容 |
|---|---|
| 対象 | `useTasks` hook + `apiClient` + MSW |
| 前提 | MSW ハンドラ: `GET /api/rooms/:roomId/tasks` → `TaskListResponse`（各 room に 2 件）。`VITE_API_BASE_URL=http://localhost:8000` |
| 操作 | `renderHook(() => useTasks(["room-a", "room-b"]))` でフックをマウント。待機後にデータ取得完了 |
| 期待結果 | 返された tasks リストに room-a / room-b 各 2 件（計 4 件）が含まれる。各 Task の `id` / `status` / `room_id` が MSW ハンドラのレスポンスと一致する |
| 受入基準 | feature-spec.md §8 #1 |

### TC-IT-CD-002: `useTasks` — 個別 Room エラーが他 Room に影響しない（REQ-CD-UI-001 エラー時）

| 項目 | 内容 |
|---|---|
| 対象 | `useTasks` hook + `apiClient` + MSW |
| 前提 | room-a → 200（2 件）、room-b → 500（Internal Server Error）のハンドラを設定 |
| 操作 | `renderHook(() => useTasks(["room-a", "room-b"]))` |
| 期待結果 | room-a の 2 件は取得成功。room-b はエラー状態（`isError=true`）だが room-a の取得結果には影響しない（部分的成功）|
| 受入基準 | basic-design.md REQ-CD-UI-001 §エラー時 |

### TC-IT-CD-003: `useTask` — Task 詳細（Stage / deliverable / Gate リンク）を取得する（REQ-CD-UI-002）

| 項目 | 内容 |
|---|---|
| 対象 | `useTask` hook + `apiClient` + MSW |
| 前提 | MSW: `GET /api/tasks/:taskId` → `TaskResponse`（status=AWAITING_EXTERNAL_REVIEW / stages あり / PENDING Gate 1 件）|
| 操作 | `renderHook(() => useTask("task-uuid-1"))` |
| 期待結果 | `data.status === "AWAITING_EXTERNAL_REVIEW"` / `data.stages` に Stage リストが含まれる / `data.current_stage_id` が一致する |
| 受入基準 | feature-spec.md §8 #2, #3, #4 |

### TC-IT-CD-004: `useGate` — Gate 詳細を取得する（REQ-CD-UI-003）

| 項目 | 内容 |
|---|---|
| 対象 | `useGate` hook + `apiClient` + MSW |
| 前提 | MSW: `GET /api/gates/:gateId` → `GateDetailResponse`（decision=PENDING / deliverable_snapshot あり / audit_trail 1 件）|
| 操作 | `renderHook(() => useGate("gate-uuid-1"))` |
| 期待結果 | `data.decision === "PENDING"` / `data.deliverable_snapshot.body_markdown` に値がある / `data.audit_trail` に 1 件含まれる |
| 受入基準 | feature-spec.md §8 #5, #6 |

### TC-IT-CD-005: `apiClient` — 正常系: JSON レスポンスを返す（§確定 B）

| 項目 | 内容 |
|---|---|
| 対象 | `frontend/src/api/client.ts` の `apiClient` |
| 前提 | MSW: `GET /api/tasks/test-id` → 200 `{"id": "test-id", "status": "PENDING"}` |
| 操作 | `apiClient.get("/api/tasks/test-id")` |
| 期待結果 | JSON オブジェクト `{id: "test-id", status: "PENDING"}` が返る。`Content-Type: application/json` ヘッダが送信されていることを MSW の `request.headers` で確認 |
| セキュリティ | ベース URL が `VITE_API_BASE_URL` 固定であること（任意 URL への直接 fetch 不可）を確認する — T2 対策 |

### TC-IT-CD-006: `apiClient` — 非 2xx → `ApiError` throw（§確定 B / R1-5 / MSG-CD-UI-006）

| 項目 | 内容 |
|---|---|
| 対象 | `frontend/src/api/client.ts` の `apiClient` |
| 前提 | MSW: `GET /api/gates/nonexistent` → 404 `{"error": {"code": "GATE_NOT_FOUND", "message": "Gate not found"}}` |
| 操作 | `apiClient.get("/api/gates/nonexistent")` を await（try/catch） |
| 期待結果 | `ApiError` がスローされる。`error.status === 404` / `error.code === "GATE_NOT_FOUND"` / `error.message === "Gate not found"` |

### TC-IT-CD-007: `useWebSocketBus` — `onopen` → `state=connected`（REQ-CD-UI-005 / §確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` hook + `MockWebSocket` |
| 前提 | `vi.stubGlobal('WebSocket', MockWebSocket)` / `VITE_API_BASE_URL=http://localhost:8000` |
| 操作 | `renderHook(() => useWebSocketBus())` → `MockWebSocket` の `onopen` を即時 dispatch |
| 期待結果 | hook の `state` が `"connected"` になる |
| 受入基準 | feature-spec.md §8 #12 |

### TC-IT-CD-008: `useWebSocketBus` — `onclose` → `state=reconnecting` + backoff タイマー起動（§確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `vi.useFakeTimers()` |
| 前提 | 接続済み状態から `onclose` を dispatch |
| 操作 | `onclose` dispatch → `vi.advanceTimersByTime(1000)` |
| 期待結果 | `onclose` 直後に `state === "reconnecting"`。1000ms 経過後に新しい `WebSocket` コンストラクタが呼ばれる（1 回目の再接続試行）|
| 受入基準 | feature-spec.md §8 #13 / R1-1 |

### TC-IT-CD-009: `useWebSocketBus` — 再接続成功 → `state=connected` + `invalidateQueries()` 呼ばれる（§確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `QueryClient` spy |
| 前提 | `QueryClient.invalidateQueries` を `vi.spyOn` でスパイ。接続 → 切断 → 再接続の流れを演じる |
| 操作 | `onclose` dispatch → `vi.advanceTimersByTime(1000)` → 新 `MockWebSocket` の `onopen` を dispatch |
| 期待結果 | `state === "connected"` かつ `queryClient.invalidateQueries()` が呼ばれている（再接続後の全キャッシュ再検証）|
| 受入基準 | feature-spec.md R1-1 |

### TC-IT-CD-010: `useWebSocketBus` — `TaskStateChangedEvent` 受信 → `["task", id]` + `["tasks"]` invalidate（§確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `QueryClient` spy |
| 前提 | 接続済み状態 |
| 操作 | `MockWebSocket.onmessage` に `{"event_type":"TaskStateChangedEvent","aggregate_type":"Task","aggregate_id":"task-abc","payload":{}}` を dispatch |
| 期待結果 | `queryClient.invalidateQueries` が `["task", "task-abc"]` と `["tasks"]` の 2 回呼ばれる |
| 受入基準 | feature-spec.md §8 #12 |

### TC-IT-CD-011: `useWebSocketBus` — `ExternalReviewGateStateChangedEvent` 受信 → `["gate", id]` + `["task", taskId]` invalidate（§確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `QueryClient` spy |
| 前提 | 接続済み状態 |
| 操作 | `{"event_type":"ExternalReviewGateStateChangedEvent","aggregate_type":"ExternalReviewGate","aggregate_id":"gate-xyz","payload":{"task_id":"task-abc"}}` を dispatch |
| 期待結果 | `queryClient.invalidateQueries` が `["gate", "gate-xyz"]` と `["task", "task-abc"]` の 2 回呼ばれる |

### TC-IT-CD-012: `useRooms` — Empire に属する Room 一覧を取得する（REQ-CD-UI-004）

| 項目 | 内容 |
|---|---|
| 対象 | `useRooms` hook + `apiClient` + MSW |
| 前提 | MSW: `GET /api/empires/:empireId/rooms` → `RoomListResponse`（3 件）/ `VITE_EMPIRE_ID=empire-1` |
| 操作 | `renderHook(() => useRooms("empire-1"))` |
| 期待結果 | 3 件の Room が返る。各 Room の `id` / `name` が MSW レスポンスと一致する |
| 受入基準 | feature-spec.md §8 #11 |

### TC-IT-CD-013: `useGateAction.approve` — 成功 → cache invalidate + navigate(-1)（§確定 D）

| 項目 | 内容 |
|---|---|
| 対象 | `useGateAction` hook + `apiClient` + MSW + `createMemoryRouter` |
| 前提 | MSW: `POST /api/gates/gate-1/approve` → 200 `GateDetailResponse`（decision=APPROVED）|
| 操作 | `approve("gate-1", "LGTM")` を呼ぶ |
| 期待結果 | `queryClient.invalidateQueries(["gate", "gate-1"])` が呼ばれる。`router.state.location` が前のパスに戻る（`navigate(-1)`）|
| 受入基準 | feature-spec.md §8 #7 |

### TC-IT-CD-014: `useGateAction.reject` — feedback_text 付き成功 → navigate(-1)（§確定 D）

| 項目 | 内容 |
|---|---|
| 対象 | `useGateAction` hook + `apiClient` + MSW |
| 前提 | MSW: `POST /api/gates/gate-1/reject` → 200 `GateDetailResponse`（decision=REJECTED）|
| 操作 | `reject("gate-1", "要修正: XYZ")` を呼ぶ |
| 期待結果 | API に `{"feedback_text": "要修正: XYZ"}` が送信される。`queryClient.invalidateQueries(["gate", "gate-1"])` 呼ばれる。`navigate(-1)` が呼ばれる |
| 受入基準 | feature-spec.md §8 #8 |

### TC-IT-CD-015: `useGateAction.approve` — API エラー → `isSubmitting` リセット + `error` 設定（§確定 D）

| 項目 | 内容 |
|---|---|
| 対象 | `useGateAction` hook + MSW |
| 前提 | MSW: `POST /api/gates/gate-1/approve` → 409 `{"error": {"code": "GATE_ALREADY_DECIDED", "message": "already approved"}}`|
| 操作 | `approve("gate-1", "comment")` を呼ぶ |
| 期待結果 | mutation の `isError === true` / `error.code === "GATE_ALREADY_DECIDED"`。`navigate` は呼ばれない |

### TC-IT-CD-016: `useDirectiveSubmit` — POST 201 成功 → `["tasks"]` invalidate + navigate("/")（§確定 E）

| 項目 | 内容 |
|---|---|
| 対象 | `useDirectiveSubmit` hook + `apiClient` + MSW |
| 前提 | MSW: `POST /api/rooms/room-1/directives` → 201 `DirectiveWithTaskResponse` |
| 操作 | `submit("room-1", "task text")` を呼ぶ |
| 期待結果 | `queryClient.invalidateQueries(["tasks"])` が呼ばれる。`router.state.location.pathname === "/"` に遷移する |
| 受入基準 | feature-spec.md §8 #11 |

### TC-IT-CD-017: `useDirectiveSubmit` — API エラー → `InlineError` 表示、遷移なし（§確定 E）

| 項目 | 内容 |
|---|---|
| 対象 | `useDirectiveSubmit` hook + MSW |
| 前提 | MSW: `POST /api/rooms/room-1/directives` → 422 `{"error": {"code": "INVALID_INPUT", "message": "text is required"}}` |
| 操作 | `submit("room-1", "")` を呼ぶ |
| 期待結果 | mutation の `isError === true`。`router.state.location.pathname` は `/directives/new` から変化しない |

### TC-IT-CD-018: `useWebSocketBus` — backoff 上限境界値: 6 回目以降 30000ms 固定（§確定 C 境界値）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `vi.useFakeTimers()` |
| 前提 | backoff 配列 `[1000, 2000, 4000, 8000, 16000, 30000]`（`detailed-design.md §確定 C` 凍結値）|
| 操作 | `triggerOpen()` → `triggerClose()` → `vi.advanceTimersByTime(1000)` → 新インスタンスを即 `triggerClose()` → … の繰り返しで 5 回切断・再試行。6 回目以降は `vi.advanceTimersByTime(29999)` で WebSocket コンストラクタが呼ばれないこと、`vi.advanceTimersByTime(1)` で呼ばれることを確認 |
| 期待結果 | 5 回目再試行時の待機は 30000ms（配列末尾到達）。6 回目以降も同じく 30000ms で固定されリトライが継続する（上限なし）。合計 `vi.advanceTimersByTime(63000)` で 6 回の WebSocket コンストラクタ呼び出しが行われる（`MockWebSocket.instances.length === 7`）|
| 根拠 | `detailed-design §確定C`: 「30000ms に到達後は 30000ms 固定でリトライを継続（上限なし）」。終端処理（`attempt >= 5` → 固定化）の実装ミスを CI で検出する |
| 受入基準 | feature-spec.md R1-1 |

### TC-IT-CD-019: `useWebSocketBus` — `AgentStateChangedEvent`（aggregate_type=Agent）受信 → `["task"]` 全件 invalidate（§確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `QueryClient` spy |
| 前提 | 接続済み状態 |
| 操作 | `{"event_type":"AgentStateChangedEvent","aggregate_type":"Agent","aggregate_id":"agent-abc","payload":{}}` を dispatch |
| 期待結果 | `queryClient.invalidateQueries` が `["tasks"]`（prefix match — 全 Room の Task 一覧キャッシュを再検証）で呼ばれる。`["gate"]` 系は呼ばれない |
| 根拠 | `detailed-design §確定C`: 「`"Agent"` → `["task"]` 全件（Agent ステータス変化は Task 詳細に影響する可能性）」→ `useTasks` の queryKey は `["tasks", roomId]` であり、`["tasks"]` プレフィックスで全 Room の Task 一覧を一括再検証する|

### TC-IT-CD-020: `useWebSocketBus` — `DirectiveStateChangedEvent`（aggregate_type=Directive）受信 → `["tasks"]` invalidate（§確定 C）

| 項目 | 内容 |
|---|---|
| 対象 | `useWebSocketBus` + `MockWebSocket` + `QueryClient` spy |
| 前提 | 接続済み状態 |
| 操作 | `{"event_type":"DirectiveCompletedEvent","aggregate_type":"Directive","aggregate_id":"directive-xyz","payload":{}}` を dispatch |
| 期待結果 | `queryClient.invalidateQueries` が `["tasks"]` で呼ばれる（Task 一覧の再取得を促す）。`["task", <specific-id>]` では呼ばれない（Directive イベントは特定 Task ID を持たないため全件再取得）|
| 根拠 | `detailed-design §確定C`: 「`"Directive"` → `["tasks"]`（Directive 完了 → Task 状態変化）」|

## ユニットテストケース（UT）

テストファイル: `frontend/src/__tests__/unit/`

### StatusBadge — status → Tailwind color class マッピング（REQ-CD-UI-006）

| テストID | 種別 | 入力 status | 期待 Tailwind クラス（一部）|
|---|---|---|---|
| TC-UT-CD-001 | 正常系 | `"PENDING"` | gray 系クラス（例: `text-gray-500`）|
| TC-UT-CD-002 | 正常系 | `"IN_PROGRESS"` | blue 系クラス（例: `text-blue-500`）|
| TC-UT-CD-003 | 正常系 | `"AWAITING_EXTERNAL_REVIEW"` | yellow 系クラス（例: `text-yellow-500`）|
| TC-UT-CD-004 | 正常系 | `"DONE"` | green 系クラス（例: `text-green-500`）|
| TC-UT-CD-005 | 正常系 | `"BLOCKED"` | red 系クラス（例: `text-red-500`）|
| TC-UT-CD-006 | 正常系 | `"CANCELLED"` | gray 系（薄め）クラス（PENDING とは異なる muted 表現）|

各ケースの操作: `render(<StatusBadge status="..." />)` → `getByRole("status")` または `getByText(...)` でレンダリング確認。`aria-label` に status 文字列が含まれることも確認（色覚依存軽減）。

### DeliverableViewer — Markdown レンダリングと XSS 防止（REQ-CD-UI-002/003 / §確定 F / T1）

#### TC-UT-CD-007: 正常系 Markdown → HTML タグに変換される

| 項目 | 内容 |
|---|---|
| 種別 | 正常系 |
| 入力 | `bodyMarkdown="# Title\n\nParagraph text"` |
| 操作 | `render(<DeliverableViewer bodyMarkdown="# Title\n\nParagraph text" />)` |
| 期待結果 | DOM に `<h1>Title</h1>` と `<p>Paragraph text</p>` が存在する |

#### TC-UT-CD-008: XSS — `<script>` タグが sanitize されて実行されない（T1 / §確定 F）

| 項目 | 内容 |
|---|---|
| 種別 | セキュリティ |
| 入力 | `bodyMarkdown="<script>alert('xss')</script>benign text"` |
| 操作 | `render(<DeliverableViewer bodyMarkdown="..." />)` |
| 期待結果 | `<script>` タグが DOM に存在しない（`document.querySelector('script')` が null）。`benign text` は表示される（sanitize が良性コンテンツを消さない）|
| 根拠 | `rehype-sanitize` の `defaultSchema` が `script` を許可リストに含まない（§確定 F）|

#### TC-UT-CD-009: `<REDACTED:DISCORD_WEBHOOK>` がそのまま文字列表示される（R1-4 / §確定 F）

| 項目 | 内容 |
|---|---|
| 種別 | 正常系（エッジケース）|
| 入力 | `bodyMarkdown="token: <REDACTED:DISCORD_WEBHOOK>"` |
| 操作 | `render(<DeliverableViewer bodyMarkdown="..." />)` |
| 期待結果 | `getByText(/REDACTED:DISCORD_WEBHOOK/)` が存在する（文字列として表示、置換・除去なし）|

### GateActionForm — 操作バリデーションと状態制御（§確定 D / R1-2 / R1-3）

#### TC-UT-CD-010: reject — `feedback_text` 空で submit → バリデーションエラー表示（R1-3 / §確定 D / MSG-CD-UI-002）

| 項目 | 内容 |
|---|---|
| 種別 | 異常系 |
| 前提 | `gate.decision="PENDING"` の `GateDetailResponse` を props に渡す |
| 操作 | `feedback_text` 未入力のまま reject ボタンをクリック |
| 期待結果 | `onReject` コールバックが呼ばれない。DOM に `"差し戻し理由を入力してください。"` が表示される（MSG-CD-UI-002）|
| 受入基準 | feature-spec.md §8 #9 |

#### TC-UT-CD-011: `isSubmitting=true` → approve / reject / cancel ボタンが全て disabled（R1-2 / §確定 D）

| 項目 | 内容 |
|---|---|
| 種別 | 異常系 |
| 前提 | `gate.decision="PENDING"` / `isSubmitting=true` を props に渡す |
| 操作 | render のみ（操作なし）|
| 期待結果 | approve ボタン / reject ボタン / cancel ボタン全てが `disabled` 属性を持つ |
| 受入基準 | feature-spec.md §8 #10 |

#### TC-UT-CD-012: `gate.decision` が `PENDING` 以外 → readonly 表示、操作ボタン非表示（§確定 D）

| 項目 | 内容 |
|---|---|
| 種別 | 正常系（エッジケース）|
| 前提 | `gate.decision="APPROVED"` を props に渡す |
| 操作 | render |
| 期待結果 | approve / reject / cancel ボタンが DOM に存在しない。`decision="APPROVED"` と `decided_at` が読み取り専用表示される |

### DirectiveForm — クライアントバリデーション（§確定 E / R1-7）

#### TC-UT-CD-013: Room 未選択で submit → MSG-CD-UI-003 表示（R1-7 / §確定 E）

| 項目 | 内容 |
|---|---|
| 種別 | 異常系 |
| 前提 | `rooms` に 2 件の Room を渡す（select は未選択状態）|
| 操作 | テキスト入力後、Room 未選択のまま送信ボタンをクリック |
| 期待結果 | `onSubmit` が呼ばれない。DOM に `"Room を選択してください。"` が表示される（MSG-CD-UI-003）|

#### TC-UT-CD-014: テキスト空で submit → MSG-CD-UI-004 表示（§確定 E）

| 項目 | 内容 |
|---|---|
| 種別 | 異常系 |
| 前提 | `rooms` に 2 件 / Room 選択済み / テキスト未入力 |
| 操作 | 送信ボタンをクリック |
| 期待結果 | `onSubmit` が呼ばれない。DOM に `"Directive テキストを入力してください。"` が表示される（MSG-CD-UI-004）|

#### TC-UT-CD-015: `VITE_EMPIRE_ID` 未設定 → MSG-CD-UI-001 表示、フォーム非表示（R1-7 / §確定 E）

| 項目 | 内容 |
|---|---|
| 種別 | 異常系 |
| 前提 | `vi.stubEnv('VITE_EMPIRE_ID', '')` または環境変数未設定 |
| 操作 | `render(<DirectiveNewPage />)` |
| 期待結果 | フォームが表示されない。DOM に `"VITE_EMPIRE_ID が設定されていません。"` が含まれる（MSG-CD-UI-001 の冒頭文字列）|

### ConnectionIndicator — 接続状態表示（REQ-CD-UI-005）

#### TC-UT-CD-016: `state=disconnected` → 赤 dot + MSG-CD-UI-005 テキスト

| 項目 | 内容 |
|---|---|
| 種別 | 正常系 |
| 操作 | `render(<ConnectionIndicator status="disconnected" />)` |
| 期待結果 | 赤系 CSS クラスの dot 要素が存在する。DOM に `"サーバーとの接続が切断されました。再接続中..."` が含まれる（MSG-CD-UI-005）|
| 受入基準 | feature-spec.md §8 #13 |

#### TC-UT-CD-017: `state=reconnecting` → 黄 dot

| 項目 | 内容 |
|---|---|
| 種別 | 正常系 |
| 操作 | `render(<ConnectionIndicator status="reconnecting" />)` |
| 期待結果 | 黄系 CSS クラスの dot 要素が存在する |

### 確定文言照合（静的テスト）

| テストID | 種別 | 対象 MSG-ID | 期待文言（完全一致）|
|---|---|---|---|
| TC-UT-CD-018 | 文言照合 | MSG-CD-UI-001 | `VITE_EMPIRE_ID が設定されていません。frontend/.env に VITE_EMPIRE_ID=<uuid> を追加してください。` |
| TC-UT-CD-019 | 文言照合 | MSG-CD-UI-002 | `差し戻し理由を入力してください。` |
| TC-UT-CD-020 | 文言照合 | MSG-CD-UI-003 | `Room を選択してください。` |
| TC-UT-CD-021 | 文言照合 | MSG-CD-UI-004 | `Directive テキストを入力してください。` |
| TC-UT-CD-022 | 文言照合 | MSG-CD-UI-005 | `サーバーとの接続が切断されました。再接続中...` |
| TC-UT-CD-023 | 文言照合 | MSG-CD-UI-006 | `サーバーに接続できません。バックエンドが起動しているか確認してください。` |

各文言テストは実装ファイル（コンポーネント / hook）から文言定数を直接 import して `expect(MSG_CD_UI_XXX).toBe("...")` で照合するか、レンダリング後の DOM に `getByText(...)` で存在を確認する。文言定数を実装から export していない場合はレンダリングベースの確認とする。

## カバレッジ基準

| 対象 | カバレッジ目標 |
|-----|------------|
| REQ-CD-UI-001 〜 REQ-CD-UI-006 の各要件 | IT または UT テストで最低 1 件検証 |
| §確定 B（apiClient）| IT テストで正常系・異常系（ApiError）を検証 |
| §確定 C（WebSocket 再接続）| IT テストで connected → reconnecting → connected の状態遷移・backoff タイマー・**30000ms 上限固定（TC-IT-CD-018）**・Agent/Directive イベントルーティング（TC-IT-CD-019/020）を検証 |
| §確定 D（Gate 操作フロー）| IT（Hook）+ UT（Form）の両レベルで approve / reject / cancel と二重送信防止を検証 |
| §確定 E（Directive 投入）| IT（Hook）+ UT（Form）の両レベルで送信成功・バリデーション・EMPIRE_ID 未設定を検証 |
| §確定 F（Markdown sanitize）| UT で `<script>` タグが除去されることを DOM で確認（TC-UT-CD-008）|
| MSG-CD-UI-001 〜 006 の全文言 | 静的文字列照合（TC-UT-CD-018〜023）または DOM 確認 |
| T1（XSS: LLM 出力）| TC-UT-CD-008 で `<script>` サニタイズ有効性を確認 |
| T2（CORS: apiClient ベース URL）| TC-IT-CD-005 で `VITE_API_BASE_URL` 固定を確認 |
| 行カバレッジ目標 | `vitest --coverage` で 80% 以上（`frontend/src/` 対象）|
| 型チェック | `tsc --noEmit` で 0 error（feature-spec.md §10）|

## WebSocket テスト戦略詳細（TC-IT-CD-007〜011 / TC-IT-CD-018〜020 共通設計）

WebSocket の状態機械は `vi.useFakeTimers()` と `MockWebSocket` の組み合わせで制御する。

**`MockWebSocket` 実装仕様**（`frontend/src/__tests__/helpers/MockWebSocket.ts`）:

| 要素 | 内容 |
|---|---|
| 管理 | `MockWebSocket` を `vi.stubGlobal('WebSocket', MockWebSocket)` でグローバルに差し替え |
| 制御 | テストから `mockWs.triggerOpen()` / `triggerClose(code?)` / `triggerMessage(data)` を呼べる |
| インスタンス追跡 | `MockWebSocket.instances` で生成された全インスタンスを追跡（再接続回数の確認に使用）|
| teardown | 各テスト後に `vi.useRealTimers()` + `vi.unstubAllGlobals()` でリセット |

**backoff タイマー検証例（TC-IT-CD-008）**:
1. `vi.useFakeTimers()` 有効化
2. `renderHook(() => useWebSocketBus())`
3. `MockWebSocket.instances[0].triggerOpen()` → state=connected
4. `MockWebSocket.instances[0].triggerClose()` → state=reconnecting
5. `vi.advanceTimersByTime(999)` → 新 WebSocket コンストラクタ未呼び出しを確認
6. `vi.advanceTimersByTime(1)` → `MockWebSocket.instances.length === 2` を確認（1 秒後に再試行）

## エラー表示 / ローディング状態の検証方針

| 状態 | 検証アプローチ |
|---|---|
| `isLoading=true`（React Query）| `renderHook` の初期状態（MSW がレスポンスを遅延）で `data` が `undefined` / `isLoading === true` を確認 |
| `isError=true`（React Query）| MSW で 4xx/5xx を返すハンドラを使い、hook の `isError === true` / `error.message` 一致を確認 |
| `InlineError` コンポーネント | UT で `error` props を渡し `getByRole("alert")` が存在することを確認 |
| ローディング中スケルトン | UT で `isLoading=true` を props 経由で注入し、スケルトン要素 (`aria-busy`) が DOM に存在することを確認 |
| 空状態（0 件）| IT でハンドラが空配列を返す設定で、「Task はありません」等の空状態メッセージが存在することを確認 |

## テストディレクトリ構造

```
frontend/src/
└── __tests__/
    ├── helpers/
    │   └── MockWebSocket.ts           # WebSocket テストダブル
    ├── integration/
    │   ├── useTasks.test.ts           # TC-IT-CD-001〜002
    │   ├── useTask.test.ts            # TC-IT-CD-003
    │   ├── useGate.test.ts            # TC-IT-CD-004
    │   ├── apiClient.test.ts          # TC-IT-CD-005〜006
    │   ├── useWebSocketBus.test.ts    # TC-IT-CD-007〜011, TC-IT-CD-018〜020
    │   ├── useRooms.test.ts           # TC-IT-CD-012
    │   ├── useGateAction.test.ts      # TC-IT-CD-013〜015
    │   └── useDirectiveSubmit.test.ts # TC-IT-CD-016〜017
    └── unit/
        ├── StatusBadge.test.tsx       # TC-UT-CD-001〜006
        ├── DeliverableViewer.test.tsx # TC-UT-CD-007〜009
        ├── GateActionForm.test.tsx    # TC-UT-CD-010〜012
        ├── DirectiveForm.test.tsx     # TC-UT-CD-013〜014
        ├── DirectiveNewPage.test.tsx  # TC-UT-CD-015
        ├── ConnectionIndicator.test.tsx # TC-UT-CD-016〜017
        └── messages.test.ts           # TC-UT-CD-018〜023（文言照合）
```

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で `vitest` / `tsc` / `biome` ジョブ全て緑であること
- ローカル: `cd frontend && pnpm test` → `vitest run` で全テスト green
- カバレッジ確認: `pnpm test:coverage` → `vitest run --coverage` で 80% 以上であること

## 未決課題

| # | タスク | 状況 |
|---|---|---|
| 1 | `MockWebSocket` のバックオフ配列 `[1000, 2000, 4000, 8000, 16000, 30000]` は `detailed-design.md §確定 C` の値を実装から読み込む形で参照すること（テスト側でハードコードしない）| 実装着手時に確認 |
| 2 | MSW ハンドラの共通 setup（`setupServer`）を `frontend/src/__tests__/msw/handlers.ts` として集中管理するか、テストごとに定義するかは CONTRIBUTING.md に従う | 実装着手時に確認 |

## 関連

- [`basic-design.md §モジュール契約`](basic-design.md) — 機能要件（REQ-CD-UI-001〜006）
- [`detailed-design.md §確定事項`](detailed-design.md) — §確定 A〜G / MSG-CD-UI-001〜006
- [`../feature-spec.md §7`](../feature-spec.md) — 業務ルール R1-1〜R1-7
- [`../feature-spec.md §8`](../feature-spec.md) — 受入基準 #1〜#14
- [`../system-test-design.md`](../system-test-design.md) — システムテスト TC-E2E-CD-001〜011（Playwright E2E）
