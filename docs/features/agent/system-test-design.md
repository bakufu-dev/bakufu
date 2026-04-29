# E2E テスト設計書

> feature: `agent`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 10, 11, 12, 13〜18

## 本書の役割

本書は **Agent 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / [`http-api/`](http-api/)（Issue #59）/ ui（将来））の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の Agent 採用 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Agent 状態と構造的等価
- http-api sub-feature の HTTP API 経由 Agent CRUD → 永続化 → 再起動 → GET による Persona.prompt_body masked 確認（Issue #59、受入基準 13〜18）
- 将来 ui sub-feature が完成した時点で Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では将来の `bakufu admin` CLI（`feature/admin-cli`）または直接 application 層を呼び出す test harness を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-AG-001 | Agent の再起動跨ぎ保持（業務ルール R1-7） | 1) Agent 採用（name="ダリオ"、Provider 1 件 is_default=True、Skills 0 件） 2) `AgentRepository.save(agent)` 3) アプリ再起動相当（DB 接続再生成） 4) `AgentRepository.find_by_id(agent_id)` | 復元された Agent が元の Agent と構造的等価（id / name / persona / role / providers / archived が一致） | 10 |
| TC-E2E-AG-002 | Empire 内 Agent 名一意（業務ルール R1-6） | 1) Agent #1 採用・永続化（name="ダリオ"） 2) 同 Empire で name="ダリオ" で Agent #2 採用試行 → `AgentRepository.find_by_name(empire_id, "ダリオ")` で存在確認 | `find_by_name` が Agent #1 を返す。application 層がこれを受けて `AgentNameAlreadyExistsError` を raise（application 層責務、暫定は Repository 側の観察まで）| 11 |
| TC-E2E-AG-003 | Persona.prompt_body の永続化前マスキング（業務ルール R1-8） | 1) `prompt_body` に `"ANTHROPIC_API_KEY=sk-ant-xxxx"` を含む Agent を採用・永続化 2) SQLite から `agents.prompt_body` カラムを直読み | DB に保存された `prompt_body` は `<REDACTED:ANTHROPIC_KEY>` 形式にマスクされており、raw token が残っていない（**Schneier #3 実適用確認**）| 12 |

| TC-E2E-AG-004 | HTTP API 経由 Agent CRUD + 再起動跨ぎ一貫性（業務ルール R1-7 + R1-9 複合） | 1) POST /api/empires/{empire_id}/agents — name="ダリオ"、prompt_body="Anthropic API key: sk-ant-xxxx" → 201 AgentResponse（prompt_body masked） 2) GET /api/empires/{empire_id}/agents → 一覧に "ダリオ" が含まれる 3) GET /api/agents/{id} → prompt_body = `<REDACTED:ANTHROPIC_KEY>` 4) PATCH /api/agents/{id} — name="ダリオ改" → 200（prompt_body masked） 5) アプリ再起動相当（DB 接続再生成） 6) GET /api/agents/{id} → name="ダリオ改"、prompt_body masked のまま 7) DELETE /api/agents/{id} → 204 8) DELETE /api/agents/{id}（再試行）→ 204（冪等） | POST 201 + レスポンス prompt_body masked / GET 一覧に含まれる / GET 個別 prompt_body masked / PATCH 200 prompt_body masked / 再起動後 GET 状態保持 / DELETE 204 / 再 DELETE 204（冪等） | 13, 14, 15, 16, 17, 18 |

将来追加予定:

- TC-E2E-AG-005: UI 経由での Agent 採用（`agent/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Agent / Persona / ProviderConfig / SkillRef Aggregate |
| application 層 | 直接呼び出し（test harness） または HTTP API 経由（TC-E2E-AG-004） |
| HTTP API 層（TC-E2E-AG-004） | FastAPI TestClient（`httpx.AsyncClient` + `ASGITransport`）— 実 DB 使用 |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（business 概念に外部 I/O なし） |

## カバレッジ基準

- 受入基準 10, 11, 12 が **E2E で最低 1 件** ずつ検証される
- 受入基準 13〜18 が TC-E2E-AG-004 として **E2E で最低 1 件** ずつ検証される（http-api sub-feature 完成後）
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` および `POST → restart → GET` ラウンドトリップ）
- TC-E2E-AG-003 の masking 検証は SQLite ファイルへの直読みで `<REDACTED:*>` を物理確認
- TC-E2E-AG-004 の HTTP response masking 検証は GET レスポンスの `prompt_body` フィールドが `<REDACTED:*>` であることを確認
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## テストディレクトリ構造

```
backend/tests/e2e/
├── test_agent_lifecycle.py    # TC-E2E-AG-001, 002, 003
└── test_agent_http_api.py     # TC-E2E-AG-004（http-api sub-feature 完成後）
```

## 未決課題

- TC-E2E-AG-002 の application 層 `AgentNameAlreadyExistsError` は `AgentService` 実装完成時に確定。本書は repository.find_by_name() の観察までを暫定 E2E とする
- TC-E2E-AG-004 は http-api sub-feature（Issue #59）の実装完了後に実行可能。本書は検証シナリオを凍結済み
- TC-E2E-AG-005（UI Playwright）は将来の `agent/ui/` sub-feature 追加時に本書を更新する別 PR で起票
