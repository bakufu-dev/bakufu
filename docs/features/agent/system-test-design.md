# E2E テスト設計書

> feature: `agent`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 10, 11, 12

## 本書の役割

本書は **Agent 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の Agent 採用 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の Agent 状態と構造的等価
- 将来 http-api / ui sub-feature が完成した時点で `curl` / Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では将来の `bakufu admin` CLI（`feature/admin-cli`）または直接 application 層を呼び出す test harness を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-AG-001 | Agent の再起動跨ぎ保持（業務ルール R1-7） | 1) Agent 採用（name="ダリオ"、Provider 1 件 is_default=True、Skills 0 件） 2) `AgentRepository.save(agent)` 3) アプリ再起動相当（DB 接続再生成） 4) `AgentRepository.find_by_id(agent_id)` | 復元された Agent が元の Agent と構造的等価（id / name / persona / role / providers / archived が一致） | 10 |
| TC-E2E-AG-002 | Empire 内 Agent 名一意（業務ルール R1-6） | 1) Agent #1 採用・永続化（name="ダリオ"） 2) 同 Empire で name="ダリオ" で Agent #2 採用試行 → `AgentRepository.find_by_name(empire_id, "ダリオ")` で存在確認 | `find_by_name` が Agent #1 を返す。application 層がこれを受けて `AgentNameAlreadyExistsError` を raise（application 層責務、暫定は Repository 側の観察まで）| 11 |
| TC-E2E-AG-003 | Persona.prompt_body の永続化前マスキング（業務ルール R1-8） | 1) `prompt_body` に `"ANTHROPIC_API_KEY=sk-ant-xxxx"` を含む Agent を採用・永続化 2) SQLite から `agents.prompt_body` カラムを直読み | DB に保存された `prompt_body` は `<REDACTED:ANTHROPIC_KEY>` 形式にマスクされており、raw token が残っていない（**Schneier #3 実適用確認**）| 12 |

将来追加予定:

- TC-E2E-AG-004: HTTP API 経由での Agent 採用 → 永続化 → 取得（`agent/http-api/` 完成後）
- TC-E2E-AG-005: UI 経由での Agent 採用（`agent/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Agent / Persona / ProviderConfig / SkillRef Aggregate |
| application 層 | 直接呼び出し（test harness） |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（business 概念に外部 I/O なし） |

## カバレッジ基準

- 受入基準 10, 11, 12 が **E2E で最低 1 件** ずつ検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- TC-E2E-AG-003 の masking 検証は SQLite ファイルへの直読みで `<REDACTED:*>` を物理確認
- E2E はテスト戦略ガイド §E2E対象の判断「sub-feature 跨ぎの統合シナリオに絞る」に従う

## テストディレクトリ構造

```
backend/tests/e2e/
└── test_agent_lifecycle.py    # TC-E2E-AG-001, 002, 003
```

## 未決課題

- TC-E2E-AG-002 の application 層 `AgentNameAlreadyExistsError` は `feature/agent-service` 完成時に確定。本書は repository.find_by_name() の観察までを暫定 E2E とする
- TC-E2E-AG-004, 005 は将来の sub-feature 追加時に本書を更新する別 PR で起票
