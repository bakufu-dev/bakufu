# 結合テストケース詳細 — RoleProfile HTTP API

> TC-IT-RPH-001〜013（主要ケースのみ詳細記載。他は index.md マトリクスを参照）
> 関連: [`index.md`](index.md) / [`../basic-design.md §REQ-RP-HTTP`](../basic-design.md)

## TC-IT-RPH-001〜013 の共通前提条件

結合テスト全体で `_seed_empire(session_factory, empire_id)` ヘルパ（repository テストで実装済みのパターン）または HTTP 経由の Empire 作成で empire_id を準備する。

## TC-IT-RPH-006: PUT — 新規 Upsert → 200（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-RP-HTTP-003 / §確定 C |
| 種別 | 正常系 |
| 前提条件 | Empire 存在、当該 role の RoleProfile なし |
| 操作 | `PUT /api/empires/{empire_id}/role-profiles/DEVELOPER` に `{deliverable_template_refs: []}` を送信 |
| 期待結果 | HTTP 200。`id`（UUID）/ `empire_id` / `role == "DEVELOPER"` / `deliverable_template_refs == []` |

## TC-IT-RPH-007: PUT — 2 回 Upsert で同一 id を保持（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-RP-HTTP-003 / §確定 C |
| 種別 | 正常系 |
| 前提条件 | 1 回目 PUT で RoleProfile 作成済み |
| 操作 | 同一 `PUT /api/empires/{empire_id}/role-profiles/DEVELOPER` を再度送信 |
| 期待結果 | HTTP 200（エラーなし）。`response.id` が 1 回目と同一 UUID |

## TC-IT-RPH-010: PUT — refs 完全置換（§確定 C）

| 項目 | 内容 |
|---|---|
| 対応 REQ | REQ-RP-HTTP-003 / §確定 C |
| 種別 | 正常系 |
| 前提条件 | ref を 2 件持つ RoleProfile が存在 |
| 操作 | refs を空リストにして PUT |
| 期待結果 | HTTP 200。`deliverable_template_refs == []`（完全置換されている）|
