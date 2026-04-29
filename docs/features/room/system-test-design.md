# E2E テスト設計書

> feature: `room`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 16, 17, 18, 19〜31
> 更新 Issue: [#57 feat(room-http-api): Room + Agent assignment HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/57)

## 本書の役割

本書は **Room 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / [`http-api/`](http-api/) / 将来の ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の Room 設立 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Room 状態と構造的等価
- http-api sub-feature 完成後: `httpx.AsyncClient` 経由の HTTP リクエストによる Room 操作 → DB 永続化 → 取得の一気通貫検証

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では `bakufu admin` CLI（`feature/admin-cli`）または直接 application 層を呼び出す test harness（ドメイン / リポジトリ層 E2E）、あるいは `httpx.AsyncClient` 経由の HTTP リクエスト（http-api E2E）を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-RM-001 | Room の再起動跨ぎ保持（業務ルール R1-7） | 1) Room 設立（name="V モデル開発室"、workflow_id=既存、members=[]、prompt_kit 空） 2) `RoomRepository.save(room, empire_id)` 3) アプリ再起動相当（DB 接続再生成） 4) `RoomRepository.find_by_id(room_id)` | 復元された Room が元の Room と構造的等価（id / name / description / workflow_id / members / prompt_kit / archived が一致） | 16 |
| TC-E2E-RM-002 | Empire 内 Room 名一意（業務ルール R1-8） | 1) Room #1 設立・永続化（name="V モデル開発室"、empire_id=empire_a） 2) 同 Empire で name="V モデル開発室" で Room #2 設立試行 → `RoomRepository.find_by_name(empire_a, "V モデル開発室")` で存在確認 | `find_by_name` が Room #1 を返す。application 層がこれを受けて `RoomNameAlreadyExistsError` を raise（application 層責務、暫定は Repository 側の観察まで）| 17 |
| TC-E2E-RM-003 | PromptKit.prefix_markdown の永続化前マスキング（業務ルール R1-9） | 1) `prefix_markdown` に `"Discord webhook https://discord.com/api/webhooks/XXXXX/YYYYY"` を含む PromptKit を持つ Room を設立・永続化 2) SQLite から `rooms.prompt_kit_prefix_markdown` カラムを直読み | DB に保存された `prompt_kit_prefix_markdown` は `<REDACTED:DISCORD_WEBHOOK>` 形式にマスクされており、raw webhook URL が残っていない（**room §確定 G 実適用確認**）| 18 |
| TC-E2E-RM-004 | HTTP API 経由 Room ライフサイクル一気通貫（受入基準 19〜31 業務統合）| 1) `POST /api/empires/{empire_id}/rooms` → 201 + RoomResponse（name="V モデル開発室"、workflow_id=既存）2) `GET /api/empires/{empire_id}/rooms` → 200 + items に 1 件 3) `POST /api/rooms/{room_id}/agents` (role="LEADER") → 201 + members に 1 件 4) `GET /api/rooms/{room_id}` → 200 + members に LEADER 1 件 5) `DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/LEADER` → 204 6) `PATCH /api/rooms/{room_id}` (name="アジャイル開発室") → 200 + name 更新済み 7) `DELETE /api/rooms/{room_id}` → 204（アーカイブ）8) `GET /api/rooms/{room_id}` → 200 + archived=True | 各ステップで期待 HTTP ステータス + レスポンス Body を確認。DB の `rooms.archived` カラムが True に変化。ライフサイクル全体で状態遷移が一貫する | 19, 22, 23, 25, 27, 28, 30 |
| TC-E2E-RM-005 | HTTP API 経由の UUID バリデーション（業務ルール R1-10）| 1) `GET /api/rooms/not-a-uuid` → 422 2) `POST /api/empires/not-a-uuid/rooms` → 422 3) `DELETE /api/rooms/{room_id}/agents/not-a-uuid/roles/LEADER` → 422 | 不正 UUID パスパラメータはすべて 422 を返し、500 は発生しない | 31 |

将来追加予定:

- TC-E2E-RM-006: UI 経由での Room 編成（`room/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層（TC-E2E-RM-001〜003） | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Room / PromptKit / AgentMembership Aggregate |
| application 層（TC-E2E-RM-001〜003） | 直接呼び出し（test harness） |
| HTTP 層（TC-E2E-RM-004〜005） | `httpx.AsyncClient` + FastAPI `app` を直接 ASGI テスト（本番 uvicorn 不要）|
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（business 概念に外部 I/O なし） |

## カバレッジ基準

- 受入基準 16, 17, 18 が **E2E で最低 1 件** ずつ検証される
- 受入基準 19〜31 の業務統合シナリオが TC-E2E-RM-004 で一気通貫検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- TC-E2E-RM-003 の masking 検証は SQLite ファイルへの直読みで `<REDACTED:*>` を物理確認
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## テストディレクトリ構造

```
backend/tests/e2e/
├── test_room_lifecycle.py    # TC-E2E-RM-001, 002, 003（domain + repository 層）
└── test_room_http_api.py     # TC-E2E-RM-004, 005（HTTP API 一気通貫）
```

## 未決課題

- TC-E2E-RM-002 の application 層 `RoomNameAlreadyExistsError` は `feature/empire-application` 完成時に確定。本書は repository.find_by_name() の観察までを暫定 E2E とする
- TC-E2E-RM-004 は Workflow factory / Agent factory の実装が前提（TC-E2E-RM-004 は http-api/test-design.md §要起票と同じ前提条件）
- TC-E2E-RM-006 は将来の sub-feature 追加時に本書を更新する別 PR で起票
