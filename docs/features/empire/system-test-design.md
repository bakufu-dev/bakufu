# E2E テスト設計書

> feature: `empire`（業務概念単位）
> 関連: [`feature-spec.md`](feature-spec.md) §9 受入基準 10, 11

## 本書の役割

本書は **Empire 業務概念全体の E2E 検証戦略** を凍結する。各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）の境界を跨いで観察される業務ふるまいを、ブラックボックスで検証する。

各 sub-feature の `test-design.md` は IT / UT のみを担当する。**E2E は本書だけが扱う**（sub-feature の test-design.md には E2E を書かない）。

## E2E スコープ

- domain sub-feature の組織構築 → repository sub-feature の永続化 → 再起動 → repository の復元 → domain の組織状態と構造的等価
- 将来 http-api / ui sub-feature が完成した時点で `curl` / Playwright 経由の E2E を本書に追記

## 観察主体

個人開発者 CEO（[`feature-spec.md §4 ペルソナ`](feature-spec.md)）。本 E2E では将来の `bakufu admin` CLI（[`feature/admin-cli`](../admin-cli)）または直接 application 層を呼び出す test harness を用いて、CEO 観点での業務シナリオを観察する。

## E2E テストケース

| テストID | シナリオ | 観察主体の操作 | 期待結果（観察可能事象） | 紐付く受入基準 |
|---------|---------|--------------|---------------------|------------|
| TC-E2E-EM-001 | 組織状態の再起動跨ぎ保持（業務ルール R1-7） | 1) Empire 構築（name="山田の幕府"） 2) Agent 採用 3 件 3) Room 設立 2 件 4) Room 1 件 archive 5) アプリ再起動相当（DB 接続再生成） 6) Empire を ID で取得 | 復元された Empire が元の Empire と構造的等価。Agent 3 件、Room 2 件（archived 1 件、active 1 件）が完全に復元される | 10 |
| TC-E2E-EM-002 | Empire シングルトン暫定検証（業務ルール R1-5） | 1) Empire #1 構築・永続化 2) `repository.count()` を呼ぶ | `count() == 1` を観察。<br>※ application 層 `EmpireService.create()` が将来 feature のため、本 E2E は repository.count() の観察までで暫定とし、`feature/empire-service` 着手時に「Empire #2 構築 → AlreadyExistsError」シナリオへ拡張 | 11 |

将来追加予定:

- TC-E2E-EM-003: HTTP API 経由での組織構築 → 永続化 → 取得（`empire/http-api/` 完成後）
- TC-E2E-EM-004: UI 経由での組織編成（`empire/ui/` 完成後、Playwright）

## 検証方法

| 観点 | 採用方法 |
|---|---|
| 永続化層 | 実 SQLite（テスト用 in-memory または tempfile） |
| domain 層 | 実 Empire / RoomRef / AgentRef Aggregate |
| application 層 | 直接呼び出し（test harness） |
| 外部 LLM / Discord / GitHub | 本 E2E では未使用（business 概念に外部 I/O 無し） |

## カバレッジ基準

- 受入基準 10, 11 が **E2E で最低 1 件** ずつ検証される
- 永続化跨ぎでの構造的等価を保証（`save → restart → find_by_id` ラウンドトリップ）
- E2E はテスト戦略ガイド §E2E対象の判断「ライブラリ単独は IT で代替」に従い、本 feature では sub-feature 跨ぎの統合シナリオに絞る

## テストディレクトリ構造

```
backend/tests/e2e/
└── test_empire_lifecycle.py    # TC-E2E-EM-001, 002
```

## 未決課題

- TC-E2E-EM-002 のシングルトン強制の最終形は `feature/empire-service` 完成時に確定。本書は repository.count() の観察までを暫定 E2E とする
- TC-E2E-EM-003, 004 は将来の sub-feature 追加時に本書を更新する別 PR で起票
