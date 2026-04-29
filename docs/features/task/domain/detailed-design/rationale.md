# 詳細設計補章 — task / domain 設計判断

> 親文書: [`../detailed-design.md`](../detailed-design.md)
> 目的: Norman 500 行ルールに従い、詳細設計の判断根拠を補章として分割する。

## なぜ state machine を decision table 化するか

6 status × 10 method = 60 経路のうち許可されるのは 13 遷移のみ。残り 47 経路を `if-elif` の暗黙拒否にすると、後続 PR で遷移追加が紛れ込みやすい。

state machine table を `Final` + `MappingProxyType` で凍結し、「table に存在しない遷移は禁止」と読める形にする。設計書、実装、テストの同期責務も明示できる。

## なぜ `advance` を 4 method に分解するか

旧案の単一 `advance` は、`IN_PROGRESS` 通常進行、終端完了、Gate APPROVED、Gate REJECTED の 4 経路を引数で切り替える設計だった。これは method 内部で current_status と引数を見て action を組み立てる暗黙 dispatch になる。

不採用理由:
- application 層が状態と判断結果を読んで引数を組み立てるため、Tell, Don't Ask に反する
- Task が `ReviewDecision` を import し、Aggregate 境界を壊す
- task-repository / external-review-gate 系 PR が action 対応を個別解釈しやすい

採用方針:
- `approve_review`
- `reject_review`
- `advance_to_next`
- `complete`

method 名が呼び出し側の意図を直接表す。Task は `ReviewDecision` を import せず、Gate decision → Task method 名の対応は application 層で静的に解決する。

## なぜ `assigned_agent_ids` を List で保持するか

empire の `agents: list[AgentRef]` と同じく順序保持を優先する。Set は serialize 順が非決定的で、Repository 永続化時の diff ノイズを生む。List + 重複チェック helper が明示的で読みやすい。

## なぜ `cancel(by_owner_id, reason)` の reason を属性にしないか

`reason` は audit 情報であり、MVP では CANCELLED Task の表示属性ではない。Aggregate に保持せず、application 層の audit_log 記録責務に閉じる。

## なぜ `created_at` / `updated_at` を引数で受け取るか

Aggregate 内で現在時刻を生成するとテスト制御が難しくなる。application 層でUTC時刻を生成して渡すことで、Aggregate は時刻I/Oを持たない pure data として保てる。

## なぜ `Deliverable` / `Attachment` を本PRで導入するか

Task が `deliverables: dict[StageId, Deliverable]` を保持するため、forward reference で先送りすると後続で `model_rebuild` が必要になる。本PRでVOを実体化し、構造を単純に保つ。

## なぜ自己遷移を state machine に明示列挙するか

`commit_deliverable` / `advance_to_next` は status を変えないが、IN_PROGRESS でのみ許可される。この制約を table に載せることで、PENDING / AWAITING / BLOCKED / DONE / CANCELLED からの呼び出しは lookup 失敗として Fail Fast になる。
