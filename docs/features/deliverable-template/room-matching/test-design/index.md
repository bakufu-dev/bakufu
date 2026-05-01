# テスト設計書（インデックス）— deliverable-template / room-matching

> feature: `deliverable-template` / sub-feature: `room-matching`
> 関連 Issue: [#120 feat(room-matching): Room matching (107-F)](https://github.com/bakufu-dev/bakufu/issues/120)
> 関連: [`../basic-design.md §モジュール契約`](../basic-design.md) / [`../detailed-design.md`](../detailed-design.md) / [`../../../room/feature-spec.md`](../../../room/feature-spec.md) / [`../../../room/http-api/basic-design.md`](../../../room/http-api/basic-design.md)
> 詳細: [`it.md`](it.md)（TC-IT-RMM-001〜012）/ [`ut.md`](ut.md)（TC-UT-RMS-001〜020）

## 本書の役割

本書は `basic-design.md §モジュール契約 REQ-RM-MATCH-001〜005` および `detailed-design.md §確定 A〜H` に対応するテストケースのインデックスを提供する。テストケース詳細は各 sub-file に分割して管理する。

**書くこと**:
- `validate_coverage` / `resolve_effective_refs` のユニットテスト（純粋関数 + 境界値）
- `upsert_override` / `delete_override` / `find_overrides` のユニットテスト
- HTTP API 経由（`assign_agent` + RoleOverride CRUD）の結合テスト
- 外部 I/O 依存マップ（factory 状況）

**書かないこと**:
- `validate_coverage` が純粋関数であるため E2E 重複検証は不要。結合テストで充足・不足・override フローの観察で代替
- DB スキーマ migration の直接 assert（alembic autogenerate テストで代替）

## テストケース ID 採番規則

| 番号帯 | 用途 | 対象サービス |
|---|---|---|
| TC-IT-RMM-001〜099 | 結合テスト: HTTP API 経由（assign_agent + RoleOverride CRUD）| — |
| TC-UT-RMS-001〜013 | ユニットテスト: `RoomMatchingService`（`validate_coverage` / `resolve_effective_refs`）| `RoomMatchingService` |
| TC-UT-RMS-014〜099 | ユニットテスト: `RoomRoleOverrideService`（`upsert_override` / `delete_override` / `find_overrides`）| `RoomRoleOverrideService` |

## テストマトリクス

### 結合テスト（IT）— 詳細は [`it.md`](it.md)

| 要件 ID | 確定事項 | テストケース ID | 種別 | 対象操作 |
|---|---|---|---|---|
| REQ-RM-MATCH-001 | §確定A, C, E | TC-IT-RMM-001 | 正常系 | assign_agent + カバレッジ充足 → 201 |
| REQ-RM-MATCH-001 | §確定A, E, F | TC-IT-RMM-002 | 異常系 | assign_agent + カバレッジ不足 → 422 |
| REQ-RM-MATCH-001 | §確定C, F | TC-IT-RMM-003 | 異常系 | 422 レスポンスの missing 構造確認（room_id / role / missing[].stage_id 等）|
| REQ-RM-MATCH-001/002 | §確定B（優先1）| TC-IT-RMM-004 | 正常系 | custom_refs で充足 → 201（RoleProfile より優先）|
| REQ-RM-MATCH-001/002 | §確定B（優先1）| TC-IT-RMM-005 | 異常系 | custom_refs 空タプル + required → 422（空は「提供なし」宣言）|
| REQ-RM-MATCH-001/002 | §確定B（優先2）| TC-IT-RMM-006 | 正常系 | RoomOverride 設定後の assign_agent → override refs で充足 → 201 |
| REQ-RM-MATCH-003 | §確定B（優先2）| TC-IT-RMM-007 | 正常系 | PUT role-overrides/{role} → 200（upsert）|
| REQ-RM-MATCH-003 | — | TC-IT-RMM-008 | 正常系 | PUT role-overrides/{role} 2 回目 → 200（上書き）|
| REQ-RM-MATCH-004 | — | TC-IT-RMM-009 | 正常系 | DELETE role-overrides/{role} → 204 |
| REQ-RM-MATCH-004 | no-op | TC-IT-RMM-010 | 境界値 | DELETE 不在 override → 204（エラーなし）|
| REQ-RM-MATCH-005 | — | TC-IT-RMM-011 | 正常系 | GET role-overrides → 200 一覧 |
| REQ-RM-MATCH-005 | 境界値 | TC-IT-RMM-012 | 境界値 | GET role-overrides → 200 空リスト |

### ユニットテスト（UT）— 詳細は [`ut.md`](ut.md)

#### validate_coverage（RoomMatchingService — 純粋関数）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-001 | §確定A, E | TC-UT-RMS-001 | 正常系 | 全 Stage 充足 → [] |
| REQ-RM-MATCH-001 | 境界値 | TC-UT-RMS-002 | 境界値 | workflow.stages 空 → [] |
| REQ-RM-MATCH-001 | §確定E | TC-UT-RMS-003 | 境界値 | optional=True のみ不足 → []（検証対象外）|
| REQ-RM-MATCH-001 | §確定A | TC-UT-RMS-004 | 異常系 | 1 Stage 1 件不足 → missing=[1件] |
| REQ-RM-MATCH-001 | §確定C | TC-UT-RMS-005 | 異常系 | 複数 Stage 複数件不足 → 全不足一括収集（missing=[N件]）|
| REQ-RM-MATCH-001 | §確定A, C | TC-UT-RMS-006 | 境界値 | effective_refs 空タプル + required_deliverable あり → 全件不足 |
| REQ-RM-MATCH-001 | §確定F | TC-UT-RMS-007 | 異常系 | missing 要素の stage_id / stage_name / template_id が正しく設定される |

#### resolve_effective_refs（RoomMatchingService — §確定B フォールバック）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-002 | §確定B（優先1）| TC-UT-RMS-008 | 正常系 | custom_refs が not None → リポジトリ呼び出しなしで即返却 |
| REQ-RM-MATCH-002 | §確定B（優先1）| TC-UT-RMS-009 | 境界値 | custom_refs が空タプル → 空タプルをそのまま返す（I/O なし）|
| REQ-RM-MATCH-002 | §確定B（優先2）| TC-UT-RMS-010 | 正常系 | custom_refs=None, RoomOverride あり → override.deliverable_template_refs を返す |
| REQ-RM-MATCH-002 | §確定B（優先3）| TC-UT-RMS-011 | 正常系 | custom_refs=None, RoomOverride なし, RoleProfile あり → role_profile.deliverable_template_refs を返す |
| REQ-RM-MATCH-002 | §確定B（優先4）| TC-UT-RMS-012 | 境界値 | custom_refs=None, 両方なし → 空タプルを返す |
| REQ-RM-MATCH-002 | §確定B 優先順位 | TC-UT-RMS-013 | 境界値 | RoomOverride が存在するとき RoleProfile は参照されない（短絡評価）|

#### upsert_override（RoomRoleOverrideService）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-003 | — | TC-UT-RMS-014 | 異常系 | Room 不在 → RoomNotFoundError |
| REQ-RM-MATCH-003 | — | TC-UT-RMS-015 | 異常系 | Room archived → RoomArchivedError |
| REQ-RM-MATCH-003 | — | TC-UT-RMS-016 | 正常系 | 正常 upsert → RoomRoleOverride を返す（room_id / role 一致）|

#### delete_override（RoomRoleOverrideService）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-004 | — | TC-UT-RMS-017 | 異常系 | Room 不在 → RoomNotFoundError |
| REQ-RM-MATCH-004 | no-op | TC-UT-RMS-018 | 境界値 | override 不在 → no-op（例外なし）|

#### find_overrides（RoomRoleOverrideService）

| 要件 ID | 確定事項 | テストケース ID | 種別 | 入力 / 期待 |
|---|---|---|---|---|
| REQ-RM-MATCH-005 | — | TC-UT-RMS-019 | 異常系 | Room 不在 → RoomNotFoundError |
| REQ-RM-MATCH-005 | 境界値 | TC-UT-RMS-020 | 境界値 | 空リスト → 正常（[] を返す）|

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | 状態 |
|---|---|---|---|---|
| SQLite（テスト用 DB）| IT 全ケース: 実 DB を使用 | `tmp_path` 配下 DB | `tests/factories/db.py`（実装済み）| ✅ 済 |
| `RoomRepository` | UT mock: Room 存在確認 / archived 確認 | — | `tests/factories/room.py` `make_room()` / `make_archived_room()`（実装済み）| ✅ 済 |
| `WorkflowRepository` | UT mock: Workflow.stages 取得 | — | `tests/factories/workflow.py` `make_workflow()` / `make_stage()`（実装済み）| ✅ 済 |
| `RoleProfileRepository` | UT mock: empire-level RoleProfile 取得 | — | `tests/factories/deliverable_template.py` `make_role_profile()`（実装済み）| ✅ 済 |
| `RoomRoleOverrideRepository` | UT mock: Room-level override 取得 / save / delete | — | `tests/factories/room.py` への `make_room_role_override()` 追加（**要作成**）| ⚠️ 要起票 |
| `Workflow` with `required_deliverables` | UT: validate_coverage のテスト用 Workflow 生成 | — | `tests/factories/workflow.py` への `make_stage_with_deliverables(required_deliverables=...)` 追加（**要作成**）| ⚠️ 要起票 |
| FastAPI ASGI | IT: HTTP リクエスト送信 | — | — | ✅ 既存パターン踏襲 |

### factory 要作成タスク（実装工程前に完了必須）

実装工程（ヴァンロッサム担当）着手前に以下の factory を追加する必要がある。**担当: ヴァンロッサム（実装着手時に同 PR で追加）**。設計工程では factory 生成ロジックの仕様のみ凍結し、実装は実装 PR に委ねる。

| factory | 追加先ファイル | 生成するもの | 必要ケース |
|---|---|---|---|
| `make_room_role_override(room_id, role, refs)` | `tests/factories/room.py` | `RoomRoleOverride` VO（frozen Pydantic）| TC-UT-RMS-010/013/016 |
| `make_stage_with_deliverables(optional=False, ...)` | `tests/factories/workflow.py` | `required_deliverables` を持つ `Stage`（`DeliverableRequirement` リスト付き）| TC-UT-RMS-001/003〜007 |

これらのオブジェクトは外部 API を呼ばないため characterization fixture は不要。factory 生成のみ。

## モック方針

| メソッド | テストレベル | モック対象 | モック手段 |
|---|---|---|---|
| `validate_coverage` | UT | なし（純粋関数）| モック不要。factories で Workflow / refs を直接構築 |
| `resolve_effective_refs` | UT | `_override_repo.find_by_room_and_role` / `_role_profile_repo.find_by_empire_and_role` | `AsyncMock` + factory 返却値 |
| `upsert_override` | UT | `_room_repo.find_by_id` / `_override_repo.save` | `AsyncMock` + factory 返却値 |
| `delete_override` | UT | `_room_repo.find_by_id` / `_override_repo.delete` | `AsyncMock` |
| `find_overrides` | UT | `_room_repo.find_by_id` / `_override_repo.find_all_by_room` | `AsyncMock` |
| 全メソッド | IT | なし（DB 実接続）| テスト用 SQLite `tmp_path` DB |

**重要**: UT では `AsyncMock.return_value` にインライン辞書リテラルを使わない。必ず factory（`make_room_role_override()` / `make_role_profile()` 等）経由で生成したオブジェクトを返却値とする（assumed mock 禁止）。

## カバレッジ基準

- REQ-RM-MATCH-001〜005 の全正常系を IT または UT で 1 件以上検証する
- §確定 B（3 段フォールバック）の全 4 分岐（custom_refs / override / role_profile / 空）を UT で確認する
- §確定 C（全不足一括収集）を UT で Stage × 複数不足 ケースで確認する
- §確定 E（optional=True 除外）を境界値 UT で確認する
- IT では HTTP ステータスコード・レスポンス構造（`error.code` / `error.detail.room_id` / `error.detail.missing`）を具体的に assert してよい（contract testing）
- DB を直接 assert しない。ラウンドトリップ（PUT → GET）で確認する

## 人間が動作確認できるタイミング

- CI 統合後: `gh pr checks` で全ジョブ緑であること
- ローカル確認:
  ```sh
  # UT
  uv run pytest backend/tests/unit/test_room_matching_service.py -v
  uv run pytest backend/tests/unit/test_room_role_override_service.py -v
  # IT
  uv run pytest backend/tests/integration/test_room_matching_http_api/ -v
  ```
