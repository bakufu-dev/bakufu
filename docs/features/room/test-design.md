# テスト設計書

<!-- feature: room -->
<!-- 配置先: docs/features/room/test-design.md -->
<!-- 対象範囲: REQ-RM-001〜006 / MSG-RM-001〜007 / 脅威 T1, T2 / 受入基準 1〜17 / 詳細設計 確定 A〜H / archive 冪等性 / leader 必須性 と Workflow 参照整合性 と Agent 存在検証 と name 一意の application 層責務境界 -->

本 feature は domain 層の Aggregate Root（Room）と内部 VO（PromptKit）と例外（RoomInvariantViolation）に閉じる。HTTP API / CLI / UI の公開エントリポイントは持たないため、E2E は本 feature 範囲外（後続 `feature/room-ui` / `feature/http-api` / `feature/admin-cli` で起票）。本 feature のテストは **ユニット主体 + 結合は Aggregate 内 module 連携（Room + PromptKit + AgentMembership + RoomInvariantViolation 往復シナリオ）+ 責務境界の物理確認**で構成する。

empire / workflow / agent の test-design.md と完全に同じ規約を踏襲（外部 I/O ゼロ・factory に `_meta.synthetic = True` の `WeakValueDictionary` レジストリ）。

## テストマトリクス

| 要件ID | 実装アーティファクト | テストケースID | テストレベル | 種別 | 受入基準 |
|--------|-------------------|---------------|------------|------|---------|
| REQ-RM-001 | `Room.__init__` / `model_validator(mode='after')` | TC-UT-RM-001 | ユニット | 正常系 | 1 |
| REQ-RM-001（name 境界） | `Room.name` の長さバリデーション | TC-UT-RM-002 | ユニット | 境界値 | 2 |
| REQ-RM-001（description 境界） | `Room.description` の長さバリデーション | TC-UT-RM-003 | ユニット | 境界値 | 3 |
| REQ-RM-001（NFC 正規化） | `Room.name` / `Room.description` の NFC + strip（確定 B） | TC-UT-RM-018 | ユニット | 正常系 | （確定 B） |
| REQ-RM-001（PromptKit 構築） | `PromptKit(prefix_markdown)` の境界 | TC-UT-RM-019 | ユニット | 境界値 | （MSG-RM-007） |
| REQ-RM-002 | `Room.add_member` 正常系 | TC-UT-RM-004 | ユニット | 正常系 | 4 |
| REQ-RM-002（重複） | `add_member` で `(agent_id, role)` 重複 | TC-UT-RM-005 | ユニット | 異常系 | 5 |
| REQ-RM-002（同一 Agent 異 Role 許容） | `add_member` で同 `agent_id` の異 `role` を追加 | TC-UT-RM-006 | ユニット | 正常系 | 6 |
| REQ-RM-002（容量） | `len(members) <= 50` | TC-UT-RM-009 | ユニット | 境界値 | 9 |
| REQ-RM-003 | `Room.remove_member` 正常系 | TC-UT-RM-007 | ユニット | 正常系 | 7 |
| REQ-RM-003（未登録） | `remove_member` で `(agent_id, role)` 不在 | TC-UT-RM-008 | ユニット | 異常系 | 8 |
| REQ-RM-004 | `Room.update_prompt_kit` 正常系 | TC-UT-RM-010 | ユニット | 正常系 | 10 |
| REQ-RM-005 | `Room.archive()` 正常系 | TC-UT-RM-011 | ユニット | 正常系 | 11 |
| REQ-RM-005（冪等性、確定 D） | 既 `archived=True` の Room に `archive()` 再呼び出し | TC-UT-RM-012 | ユニット | 正常系 | 12 |
| REQ-RM-005（archived terminal） | `archived=True` の Room への `add_member` / `remove_member` / `update_prompt_kit` | TC-UT-RM-013 | ユニット | 異常系 | 13 |
| REQ-RM-006-① | name 1〜80 文字 | TC-UT-RM-002 | ユニット | 境界値 | 2 |
| REQ-RM-006-② | description 0〜500 文字 | TC-UT-RM-003 | ユニット | 境界値 | 3 |
| REQ-RM-006-③ | `(agent_id, role)` 重複なし | TC-UT-RM-005 | ユニット | 異常系 | 5 |
| REQ-RM-006-④ | members 件数 0〜50 | TC-UT-RM-009 | ユニット | 境界値 | 9 |
| REQ-RM-006-⑤ | archived terminal | TC-UT-RM-013 | ユニット | 異常系 | 13 |
| 確定 A（pre-validate） | `add_member` 失敗時の元 Room 不変 | TC-UT-RM-020 | ユニット | 異常系 | — |
| 確定 A（pre-validate） | `remove_member` 失敗時の元 Room 不変 | TC-UT-RM-021 | ユニット | 異常系 | — |
| 確定 A（pre-validate） | `update_prompt_kit` 失敗時の元 Room 不変 | TC-UT-RM-022 | ユニット | 異常系 | — |
| 確定 D（archive 冪等性） | 連続 archive() 呼び出し | TC-UT-RM-012, TC-UT-RM-023 | ユニット | 正常系 | 12 |
| 確定 E（archived terminal） | archive 自身は archived 状態でも通過 | TC-UT-RM-012 | ユニット | 正常系 | 12 |
| 確定 F（同 Agent 兼 複数 Role） | `(agent_id, role)` ペアで一意、agent_id 単独では非一意 | TC-UT-RM-006 | ユニット | 正常系 | 6 |
| 確定 G（PromptKit VO 維持） | PromptKit が単一属性 VO のまま frozen + 構造的等価 | TC-UT-RM-024 | ユニット | 正常系 | 15 |
| 確定 H（webhook auto-mask） | `RoomInvariantViolation` の auto-mask（T2 防御） | TC-UT-RM-014 | ユニット | 異常系 | 14 |
| frozen 不変性 | `Room` / `PromptKit` 属性代入拒否 | TC-UT-RM-025 | ユニット | 異常系 | 15 |
| frozen 構造的等価 | VO の `__eq__` / `__hash__` | TC-UT-RM-024 | ユニット | 正常系 | 15 |
| `extra='forbid'` | 未知フィールド拒否 | TC-UT-RM-026 | ユニット | 異常系 | （T1 防御） |
| T1（PromptKit 経由 secret 漏洩） | `prefix_markdown` 長さ制約のみ Aggregate で守る、マスキングは Repository 層責務 | TC-UT-RM-019 | ユニット | 境界値 | （T1 / MSG-RM-007） |
| T2（webhook URL 例外漏洩） | `RoomInvariantViolation` の message / detail に webhook URL が混入しても伏字化 | TC-UT-RM-014 | ユニット | 異常系 | 14 |
| application 層責務メタ | Room Aggregate は `name` の Empire 内一意を**強制しない** | TC-UT-RM-027 | ユニット | 正常系 | （確定 R1-A 系 / 責務境界） |
| application 層責務メタ | Room Aggregate は `workflow_id` 参照整合性を**検証しない** | TC-UT-RM-028 | ユニット | 正常系 | （責務境界） |
| application 層責務メタ | Room Aggregate は LEADER 必須性を**検証しない**（雑談部屋など要らない部屋を許容） | TC-UT-RM-029 | ユニット | 正常系 | （確定 R1-A） |
| application 層責務メタ | Room Aggregate は `members[*].agent_id` の Agent 存在を**検証しない** | TC-UT-RM-030 | ユニット | 正常系 | （責務境界） |
| MSG-RM-001 | `[FAIL] Room name must be 1-80 characters (got {length})` | TC-UT-RM-031 | ユニット | 異常系 | 2 |
| MSG-RM-002 | `[FAIL] Room description must be 0-500 characters (got {length})` | TC-UT-RM-032 | ユニット | 異常系 | 3 |
| MSG-RM-003 | `[FAIL] Duplicate member: agent_id={agent_id}, role={role}` | TC-UT-RM-033 | ユニット | 異常系 | 5 |
| MSG-RM-004 | `[FAIL] Room members capacity exceeded (got {count}, max 50)` | TC-UT-RM-034 | ユニット | 異常系 | 9 |
| MSG-RM-005 | `[FAIL] Member not found: agent_id={agent_id}, role={role}` | TC-UT-RM-035 | ユニット | 異常系 | 8 |
| MSG-RM-006 | `[FAIL] Cannot modify archived Room: room_id={room_id}` | TC-UT-RM-036 | ユニット | 異常系 | 13 |
| MSG-RM-007 | `[FAIL] PromptKit.prefix_markdown must be 0-10000 characters (got {length})` | TC-UT-RM-037 | ユニット | 異常系 | （文言照合） |
| AC-16（lint/typecheck） | `pyright --strict` / `ruff check` | （CI ジョブ） | — | — | 16 |
| AC-17（カバレッジ） | `pytest --cov=bakufu.domain.room` | （CI ジョブ） | — | — | 17 |
| 結合シナリオ 1 | `Room` + `PromptKit` + `AgentMembership` + `RoomInvariantViolation` 往復 | TC-IT-RM-001 | 結合 | 正常系/異常系 | 1, 4, 7, 10, 11 |
| 結合シナリオ 2 | `add_member` 失敗 → 成功の連続（pre-validate 連続安全性） | TC-IT-RM-002 | 結合 | 異常系/正常系 | 4, 5 |

**マトリクス充足の証拠**:
- REQ-RM-001〜006 すべてに最低 1 件のテストケース
- REQ-RM-006 不変条件 5 種すべてに独立した検証ケース（①〜⑤）
- **`(agent_id, role)` 重複検査**: 同ペア重複は raise（TC-UT-RM-005）+ 同 `agent_id` で異 `role` は許容（TC-UT-RM-006）の 2 経路で「ペアで一意、agent_id 単独では非一意」の確定 F を物理確認
- **`archive()` 冪等性**: 既 `archived=True` への呼び出し（TC-UT-RM-012）+ 連続呼び出し（TC-UT-RM-023）の 2 経路。確定 D に整合
- **archived terminal 違反**: `add_member` / `remove_member` / `update_prompt_kit` の 3 ふるまいすべてが archived=True で raise することを TC-UT-RM-013 で網羅。`archive()` 自身は通過することは TC-UT-RM-012 で確認（確定 E）
- **application 層責務 4 件**（name 一意 / workflow_id 参照整合性 / LEADER 必須性 / Agent 存在検証）すべてに「Aggregate 層で強制しない」ことを物理確認する test を起票（TC-UT-RM-027〜030）。これは agent §確定 R1-B（name 一意）/ §確定 I（provider_kind MVP gate）と同じパターンで、責務境界を test で凍結し将来の誤った Aggregate 内強制への退行を防ぐ
- **PromptKit auto-mask（T2 防御）**: webhook URL 含む長文を `prefix_markdown` / `name` / `description` に流して例外発生 → message と detail の両方が伏字化されていることを TC-UT-RM-014 で確認（確定 H）
- **PromptKit VO 規約**: 単一属性 `prefix_markdown` のみ、frozen + 構造的等価 + 0〜10000 文字 + NFC のみ（strip しない）を TC-UT-RM-019 / TC-UT-RM-024 で確認（確定 G）
- MSG-RM-001〜007 すべてに静的文字列照合（TC-UT-RM-031〜037）
- 受入基準 1〜15 すべてに unit/integration ケース（16/17 は CI ジョブ）
- T1（PromptKit 経由 secret 漏洩）/ T2（webhook URL 例外漏洩）すべてに有効性確認ケース
- 確定 A（pre-validate）/ B（NFC + strip パイプライン）/ C（容量 50）/ D（archive 冪等性 + 新インスタンス）/ E（archived terminal）/ F（同 Agent 兼 複数 Role）/ G（PromptKit VO 維持）/ H（webhook auto-mask）すべてに証拠ケース
- 孤児要件ゼロ

## 外部 I/O 依存マップ

| 外部 I/O | 用途 | raw fixture | factory | characterization 状態 |
|--------|-----|------------|---------|---------------------|
| **該当なし** | Room は domain 層単独で外部 I/O を持たない（HTTP / DB / ファイル / 時刻 / LLM / Discord いずれも未依存）。`PromptKit.prefix_markdown` は文字列バリデーションのみで、実際に LLM へ送信する経路は本 feature には存在しない（`feature/llm-adapter` 責務）。`workflow_id` / `members[*].agent_id` も型として VO を保持するのみで、参照先 Aggregate の存在検証は application 層責務（`RoomService.create()` / `RoomService.add_member()`） | — | — | **不要（外部 I/O ゼロ）** |
| `unicodedata.normalize('NFC', ...)` | name / description / prefix_markdown 正規化 | — | — | 不要（CPython 標準ライブラリ仕様で固定、empire / workflow / agent と同方針） |
| `datetime.now(UTC)` | `AgentMembership.joined_at`（呼び出し側で生成して渡す、Aggregate 内では受け取るのみ） | — | — | 不要（Aggregate 内で時刻を取得しない、application 層責務） |

**根拠**:
- [`basic-design.md`](basic-design.md) §外部連携 で「該当なし — domain 層のみのため外部システムへの通信は発生しない」と凍結
- [`requirements-analysis.md`](requirements-analysis.md) §前提条件・制約 で「ネットワーク: 該当なし」と凍結
- 本 feature では assumed mock 問題は構造上発生しない（モック対象なし）

**factory（合成データ）の扱い**:

| factory | 出力 | `_meta.synthetic` 付与 |
|--------|-----|------------------|
| `RoomFactory` | `Room`（valid デフォルト = members 0 件、archived=False、最小 PromptKit） | `True` |
| `ArchivedRoomFactory` | `Room`（valid デフォルト + `archived=True`） | `True` |
| `PopulatedRoomFactory` | `Room`（leader + reviewer の 2 members） | `True` |
| `PromptKitFactory` | `PromptKit`（valid デフォルト = 短文 markdown） | `True` |
| `LongPromptKitFactory` | `PromptKit`（prefix_markdown 10000 文字、上限境界） | `True` |
| `AgentMembershipFactory` | `AgentMembership`（既存 VO の再利用、`role=DEVELOPER` を default） | `True` |
| `LeaderMembershipFactory` | `AgentMembership`（`role=LEADER`） | `True` |

`_meta.synthetic = True` は empire / workflow / agent と同じく **`tests/factories/room.py` モジュールスコープ `WeakValueDictionary[int, BaseModel]` レジストリ + `id(instance)` をキーに `is_synthetic()` で判定** 方式を踏襲する。frozen + `extra='forbid'` を尊重してインスタンスに属性追加は試みない。本番コード（`backend/src/bakufu/`）からは `tests/factories/room.py` を import しない（CI で `tests/` から `src/` への向きのみ許可）。

## E2E テストケース

**該当なし** — 理由:

- 本 feature は domain 層の純粋ライブラリで、CLI / HTTP API / UI のいずれの公開エントリポイントも持たない（[`requirements.md`](requirements.md) §画面・CLI 仕様 / §API 仕様 で「該当なし」と凍結）
- 戦略ガイド §E2E対象の判断「バッチ処理・内部API・ライブラリなどエンドユーザー操作がない場合は結合テストで代替可」に従い、E2E は本 feature 範囲外
- 後続 `feature/admin-cli`（`bakufu admin room create` 等）/ `feature/http-api`（Room CRUD）/ `feature/room-ui`（Web UI）が公開 I/F を実装した時点で E2E を起票
- 受入基準 1〜15 はすべて unit/integration テストで検証可能（16/17 は CI ジョブ）

| テストID | ペルソナ | シナリオ | 操作手順 | 期待結果 |
|---------|---------|---------|---------|---------|
| （N/A） | — | 該当なし — domain 層のため公開 I/F なし | — | — |

## 結合テストケース

domain 層単独の本 feature では「結合」を **Aggregate 内 module 連携（Room + PromptKit + AgentMembership + RoomInvariantViolation の往復シナリオ）+ pre-validate 連続シナリオ**と定義する。外部 LLM / Discord / GitHub / DB は本 feature では使わないためモック不要。

| テストID | 対象モジュール連携 | 使用 fixture | 前提条件 | 操作 | 期待結果 |
|---------|------------------|--------------|---------|------|---------|
| TC-IT-RM-001 | `Room` + `PromptKit` + `AgentMembership` + `RoomInvariantViolation` 往復 | factory（`RoomFactory` / `PromptKitFactory` / `AgentMembershipFactory` / `LeaderMembershipFactory`） | members 0 件の最小 Room | 1) `add_member(leader)` で leader を追加 → 2) `add_member(developer)` で developer を追加 → 3) members 2 件、構造的等価判定 → 4) `update_prompt_kit(new)` で PromptKit を差し替え → 5) `remove_member(developer, DEVELOPER)` で削除 → 6) `archive()` で archived=True に → 7) 各段階で frozen 不変性により元 Room が変化しないことを確認 | 受入基準 1, 4, 7, 10, 11 を一連で確認、Pydantic frozen 不変性を経路全体で確認 |
| TC-IT-RM-002 | `Room.add_member`（失敗）+（成功）の連続 | factory | members 1 件（既存 leader）の Room | 1) 同 `(agent_id, role)` で `add_member` → MSG-RM-003 で raise → 2) 元 Room が unchanged であることを確認（pre-validate）→ 3) 続けて異なる `(agent_id, role)` で `add_member` → 成功 → 4) members 2 件、`(agent_id, role)` の集合が想定通り | 失敗の独立性（pre-validate 確定 A）が連続操作で破綻しないこと、受入基準 4, 5 |

**注**: 本 feature では結合テストも `tests/integration/test_room.py` ではなく `tests/domain/test_room.py` 内の「往復シナリオ」セクションとして実装してよい（empire / workflow / agent と同方針）。

## ユニットテストケース

`tests/factories/room.py` の factory 経由で入力を生成する。raw fixture は本 feature では外部 I/O ゼロのため存在しない。

### Room Aggregate Root（不変条件 5 種、受入基準 1〜13）

| テストID | 対象 | 種別 | 入力（factory） | 期待結果 |
|---------|-----|------|---------------|---------|
| TC-UT-RM-001 | `Room(id, name, description, workflow_id, members=[], prompt_kit, archived=False)` | 正常系 | factory デフォルト | 構築成功、`archived=False`、`members` 0 件、`prompt_kit.prefix_markdown` 任意 |
| TC-UT-RM-002 | `Room.name` 境界値 | 境界値 | name 0 / 1 / 80 / 81 文字、空白のみ、NFC 分解形混入 | 0/81/空白のみは `RoomInvariantViolation(kind='name_range')` + MSG-RM-001、1/80 は成功 |
| TC-UT-RM-003 | `Room.description` 境界値 | 境界値 | description 0 / 500 / 501 文字、NFC 分解形混入 | 0/500 は成功（空文字列許容）、501 は `RoomInvariantViolation(kind='description_too_long')` + MSG-RM-002 |
| TC-UT-RM-004 | `Room.add_member(agent_id, role, joined_at)` 正常系 | 正常系 | 空 members + 新 `AgentMembership` 1 件 | 新 Room の `members` 1 件、元 Room は空のまま（frozen） |
| TC-UT-RM-005 | `add_member` 重複 | 異常系 | 既存 `(agent_id, role)` ペアと同一の追加 | `RoomInvariantViolation(kind='member_duplicate')` + MSG-RM-003 |
| TC-UT-RM-006 | 同 `agent_id` の異 `role` 追加（確定 F） | 正常系 | `agent_id=X` で `LEADER` 既存 → 同 `agent_id=X` で `REVIEWER` 追加 | 構築成功、members 2 件、両方とも保持される（leader 兼 reviewer 表現） |
| TC-UT-RM-007 | `Room.remove_member(agent_id, role)` 正常系 | 正常系 | members 2 件 + 1 件削除 | 新 Room の `members` 1 件、元 Room は 2 件のまま |
| TC-UT-RM-008 | `remove_member` 不在 | 異常系 | 存在しない `(agent_id, role)` を指定 | `RoomInvariantViolation(kind='member_not_found')` + MSG-RM-005 |
| TC-UT-RM-009 | members 容量上限（確定 C） | 境界値 | 50 件成功、51 件目で raise | 50 まで成功、51 で `RoomInvariantViolation(kind='capacity_exceeded')` + MSG-RM-004 |
| TC-UT-RM-010 | `Room.update_prompt_kit(new)` 正常系 | 正常系 | 既存 Room + 新 PromptKit | 新 Room の `prompt_kit` が new に置換、元 Room は旧 PromptKit のまま |
| TC-UT-RM-011 | `Room.archive()` 正常系 | 正常系 | archived=False の Room | 新 Room の `archived=True`、元 Room は False のまま |
| TC-UT-RM-012 | `archive()` 冪等性（確定 D / E） | 正常系 | 既 `archived=True` の Room に `archive()` 再呼び出し | 例外を raise**せず**、`archived=True` の新 Room を返す。返り値は `model_validate` 経由のため**新インスタンス**（オブジェクト同一性ではない、構造的等価で同状態）。確定 D と E（archive 自身は archived 状態でも通過）の両方を一つの test で同時に検証 |
| TC-UT-RM-013 | archived terminal 違反（確定 E） | 異常系 | archived=True の Room に `add_member` / `remove_member` / `update_prompt_kit` を**それぞれ**呼ぶ | 全 3 ふるまいで `RoomInvariantViolation(kind='room_archived')` + MSG-RM-006、`archive()` 自身は通過することは TC-UT-RM-012 で確認済 |

### pre-validate 方式（確定 A）の元 Room 不変性

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RM-020 | `add_member` 失敗時の元 Room 不変 | 異常系 | 重複 `(agent_id, role)` で失敗 | 失敗後、元 Room の `members` 件数・内容が完全に変化なし |
| TC-UT-RM-021 | `remove_member` 失敗時の元 Room 不変 | 異常系 | 不在 `(agent_id, role)` で失敗 | 元 Room の `members` 件数・内容完全一致 |
| TC-UT-RM-022 | `update_prompt_kit` 失敗時の元 Room 不変 | 異常系 | archived=True の Room で update を試行（room_archived で raise） | 元 Room の `prompt_kit` 完全一致 |
| TC-UT-RM-023 | `archive()` 連続呼び出し（冪等性の連続安全性） | 正常系 | archived=False の Room → `archive()` → `archive()` → `archive()` を 3 連続 | 全呼び出しで `archived=True` の Room を返す、エラーなし、最終状態が `archived=True` |

### PromptKit Value Object（確定 G、受入基準 15）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RM-019 | `PromptKit(prefix_markdown)` 境界値（T1 関連 / 確定 B / G） | 境界値 | prefix_markdown 0 / 10000 / 10001 文字、前後改行を含む文字列 | 0/10000 は成功、10001 で `pydantic.ValidationError`（または `RoomInvariantViolation(kind='prompt_kit_too_long')` + MSG-RM-007）。**前後改行は strip されないことを assert**（NFC のみ適用、agent §確定 E と同方針） |
| TC-UT-RM-024 | PromptKit / Room 構造的等価 / hash | 正常系 | 全属性同値の `PromptKit` を 2 インスタンス + 全属性同値の `Room` を 2 インスタンス | `==` True、`hash()` 一致（受入基準 15）。frozen + `model_config.frozen=True` 起因 |
| TC-UT-RM-018 | name / description の NFC + strip 正規化（確定 B） | 正常系 | 合成形「Vモデル開発室」/分解形「Vモデル開発室」/前後空白あり `name='  Vモデル開発室  '` | `Room.name` および `Room.description` が NFC + strip 後の文字列で保持される。**`PromptKit.prefix_markdown` は NFC のみ、strip しないことを併せて確認**（前後改行を保持する Markdown 規約） |

### frozen / extra='forbid' / VO 構造的等価（受入基準 15）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RM-025 | frozen 不変性 | 異常系 | `room.name = 'X'` / `room.archived = True` / `prompt_kit.prefix_markdown = ...` 直接代入 | `pydantic.ValidationError`（frozen instance への代入拒否）、Room / PromptKit 両方で確認 |
| TC-UT-RM-026 | `extra='forbid'` 未知フィールド拒否 | 異常系 | `Room.model_validate({...,'unknown': 'x'})` / `PromptKit.model_validate({'prefix_markdown': '', 'unknown': 1})` | 両方で `pydantic.ValidationError`（T1 関連の入力境界防御） |

### 脅威対策（T1 / T2、確定 H）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RM-014 | T2: `RoomInvariantViolation` の webhook auto-mask（確定 H） | 異常系 | webhook URL を含む長文（500 文字超）を `description` または `prefix_markdown` に貼り、長さ超過で例外発生 | 例外の `str(exc)` および `exc.detail` の両方で webhook URL が `<REDACTED:DISCORD_WEBHOOK>` に伏字化されていること。`mask_discord_webhook` + `mask_discord_webhook_in` が `super().__init__` 前に適用されている物理保証（受入基準 14、agent / workflow と同パターン） |

**T1 申し送り**: `PromptKit.prefix_markdown` の secret マスキング（OAuth トークン / API key 等）は本 feature では**長さ上限のみ**を検証する（TC-UT-RM-019 で 10001 文字拒否）。実際の永続化前マスキング（`<REDACTED:ANTHROPIC_KEY>` 等の置換）は `feature/persistence-foundation` の Repository 層で適用される責務として残す（[`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則 §適用先一覧に `Room.prompt_kit.prefix_markdown` を本 PR で追記済み）。本 feature では「domain VO は raw 保持、Repository 層で適用」という適用先指定を凍結する。

### application 層責務メタ（責務境界の物理確認、確定 R1-A 系）

| テストID | 対象 | 種別 | 入力 | 期待結果 |
|---------|-----|------|------|---------|
| TC-UT-RM-027 | Room Aggregate は `name` の Empire 内一意を**強制しない** | 正常系 | 同 `name='Vモデル開発室'` で異なる id の Room 2 件を独立して構築 | 両方とも構築成功、`RoomInvariantViolation` を raise**しない**ことを assert。これは「name 一意は application 層 `RoomService.create()` の `RoomRepository.find_by_name(empire_id, name)` 経由で判定する」という責務境界を test で凍結 |
| TC-UT-RM-028 | Room Aggregate は `workflow_id` 参照整合性を**検証しない** | 正常系 | 存在しない workflow_id（任意の UUIDv4 を生成）で Room を構築 | 構築成功（Aggregate は workflow_id を VO 型として保持するのみ）。`feature/workflow` のリポジトリ参照は `RoomService.create()` 責務 |
| TC-UT-RM-029 | Room Aggregate は LEADER 必須性を**検証しない**（確定 R1-A） | 正常系 | LEADER role の member が 0 件の Room を構築（雑談部屋を想定） | 構築成功（Aggregate は Workflow が leader を要求するか知らない）。LEADER 必須性は `RoomService.add_member()` / `RoomService.remove_member()` / `RoomService.create()` が Workflow の `required_role` 集合と突合する責務（agent §確定 I の `provider_kind` MVP gate と同パターン） |
| TC-UT-RM-030 | Room Aggregate は `members[*].agent_id` の Agent 存在を**検証しない** | 正常系 | 存在しない agent_id（任意の UUIDv4 を生成）の `AgentMembership` を含む Room を構築 | 構築成功（Aggregate は agent_id を VO 型として保持するのみ）。Agent 存在検証は `RoomService.add_member()` の `AgentRepository.find_by_id` 経由 |

これら 4 件は「将来の誤った Aggregate 内強制への退行を test で物理的に防ぐ」境界凍結ケース。

### MSG 文言照合（受入基準 14、文言の静的照合）

| テストID | MSG ID | 入力 | 期待結果 |
|---------|--------|------|---------|
| TC-UT-RM-031 | MSG-RM-001 | name='a'*81 | `[FAIL] Room name must be 1-80 characters (got 81)` 完全一致 |
| TC-UT-RM-032 | MSG-RM-002 | description='a'*501 | `[FAIL] Room description must be 0-500 characters (got 501)` 完全一致 |
| TC-UT-RM-033 | MSG-RM-003 | 重複 `(agent_id, role)` | `[FAIL] Duplicate member: agent_id=<id>, role=LEADER` 形式 |
| TC-UT-RM-034 | MSG-RM-004 | members 51 件 | `[FAIL] Room members capacity exceeded (got 51, max 50)` 完全一致 |
| TC-UT-RM-035 | MSG-RM-005 | `remove_member(unknown_id, role)` | `[FAIL] Member not found: agent_id=<id>, role=DEVELOPER` 形式 |
| TC-UT-RM-036 | MSG-RM-006 | archived=True の Room に `add_member` | `[FAIL] Cannot modify archived Room: room_id=<id>` 形式 |
| TC-UT-RM-037 | MSG-RM-007 | prefix_markdown='a'*10001 | `[FAIL] PromptKit.prefix_markdown must be 0-10000 characters (got 10001)` 完全一致 |

## カバレッジ基準

- REQ-RM-001 〜 006 の各要件が**最低 1 件**のテストケースで検証されている（マトリクス参照）
- 不変条件 5 種それぞれが独立した unit ケースで検証されている（REQ-RM-006 ①〜⑤）
- **`(agent_id, role)` 重複検査**: 同ペア重複は raise（TC-UT-RM-005）+ 同 `agent_id` で異 `role` は許容（TC-UT-RM-006）の 2 経路で「ペアで一意、agent_id 単独では非一意」（確定 F）を物理確認
- **`archive()` 冪等性 + archived terminal**: 確定 D（既 archived へ archive 再呼び出し / 連続呼び出し）+ 確定 E（add/remove/update は raise、archive 自身は通過）を TC-UT-RM-012 / 013 / 023 で網羅
- **application 層責務 4 件**（name 一意 / workflow_id 参照整合性 / LEADER 必須性 / Agent 存在検証）すべてに「Aggregate 層で強制しない」ことを物理確認する unit ケース（TC-UT-RM-027〜030）。責務境界を test で凍結し将来の誤った Aggregate 内強制への退行を防ぐ
- **PromptKit auto-mask（T2 防御、確定 H）**: webhook URL 含む入力で例外発生時に message と detail の両方が伏字化されていることを TC-UT-RM-014 で確認
- MSG-RM-001 〜 007 の各文言が**静的文字列で照合**されている（TC-UT-RM-031 〜 037）
- 受入基準 1 〜 15 の各々が**最低 1 件のユニット/結合ケース**で検証されている（E2E 不在のため戦略ガイドの「結合代替可」に従う）
- 受入基準 16（pyright/ruff）/ 17（カバレッジ 95%）は CI ジョブで担保
- T1（PromptKit 経由 secret 漏洩）/ T2（webhook URL 例外漏洩）の各脅威に対する対策が**最低 1 件のテストケース**で有効性を確認されている
- 確定 A〜H すべてに証拠ケース
- C0 目標: `domain/room/` 配下で **95% 以上**（domain 層基準、要件分析書 §非機能要求準拠）

## 人間が動作確認できるタイミング

本 feature は domain 層単独のため、人間が UI / CLI で触れるタイミングは無い。レビュワー / オーナーは以下で動作確認する。

- CI 統合後: `gh pr checks` で 7 ジョブ緑（lint / typecheck / test-backend / audit / fmt / commit-msg / no-ai-footer）
- ローカル: `bash scripts/setup.sh` → `cd backend && uv run pytest tests/domain/room/test_room.py -v` → 全テスト緑
- カバレッジ確認: `cd backend && uv run pytest --cov=bakufu.domain.room --cov-report=term-missing tests/domain/room/test_room.py` → `domain/room/` 95% 以上
- 不変条件違反の実観測: 不正入力で MSG-RM-001〜007 が出ることを目視（実装担当が PR 説明欄に貼り付け）
- archive 冪等性の実観測: `uv run python -c "from tests.factories.room import RoomFactory; r = RoomFactory(); a1 = r.archive(); a2 = a1.archive(); print(a1.archived, a2.archived, a1 == a2)"` で `True True True` が出ることを目視
- 同 Agent 兼 複数 Role の実観測: `add_member(agent_x, LEADER)` → `add_member(agent_x, REVIEWER)` が成功することを目視
- webhook auto-mask の実観測: `description=' ... ' + 'a'*500` の形で webhook URL を含む長文を貼り付け → 例外 message に `<REDACTED:DISCORD_WEBHOOK>` が出ることを目視

後段で `feature/admin-cli`（`bakufu admin room create`）/ `feature/http-api`（Room CRUD）が完成したら、本 feature の Room を経由して `curl` 経由の手動シナリオで E2E 観測可能になる。

## テストディレクトリ構造

```
backend/
  tests/
    factories/
      __init__.py
      room.py                  # RoomFactory / ArchivedRoomFactory / PopulatedRoomFactory /
                               # PromptKitFactory / LongPromptKitFactory /
                               # AgentMembershipFactory / LeaderMembershipFactory
                               # （empire / workflow / agent 流の WeakValueDictionary レジストリ + is_synthetic()）
    domain/
      room/
        __init__.py
        test_room.py           # TC-UT-RM-001〜037 + TC-IT-RM-001〜002（往復シナリオ section）
```

**配置の根拠**:
- empire / workflow / agent と同方針: domain 層単独・外部 I/O ゼロのため `tests/integration/` ディレクトリは作らない
- characterization / raw / schema は本 feature では生成しない（外部 I/O ゼロ）
- factory のみは生成する（unit テストの入力バリエーション網羅のため）
- 本 feature では agent と同じく helper module-level 独立化（agent §確定 D 系）相当の検査関数群を `aggregate_validators.py` に持つ。test 側は `Room` を構築 / メソッド呼び出しすることで間接的に helper を経路網羅する（empire / workflow / agent と同方針）

## 未決課題・要起票 characterization task

| # | タスク | 起票先 | 備考 |
|---|-------|--------|------|
| （N/A） | 該当なし — 外部 I/O ゼロのため characterization 不要 | — | 後続 `feature/persistence-foundation` の Repository 実装（DB 永続化、`rooms.UNIQUE(empire_id, name)` 制約 + `room_members.UNIQUE(room_id, agent_id, role)` 制約）/ `feature/room-ui`（Web UI）が起票時に Room 起点の characterization が発生する見込み |

**Schneier から前回申し送りされた件への対応状況**（empire / workflow / agent レビューより継承）:

- **DB UNIQUE 二重防御**: 本 PR では対象外（domain 層）。`detailed-design.md §データ構造（永続化キー）` に「`rooms.UNIQUE(empire_id, name)` + `room_members.UNIQUE(room_id, agent_id, role)`」が明記されており、`feature/persistence-foundation` の Aggregate 別 Repository 実装時にこの DB 制約が basic-design.md / detailed-design.md と整合していることを必ず確認する申し送り
- **Unicode 不可視文字 / 同形異字符**: 本 PR では対象外（`feature/http-api` の入力境界責務）。Empire / Workflow / Agent / Room 共通で `name` の機密レベルは低のため認可バイパス経路ではないが、後段で抜けないこと
- **`PromptKit.prefix_markdown` の secret マスキング**: 本 feature では文字列保持のみ。永続化前マスキング規則（[`storage.md`](../../architecture/domain-model/storage.md) §シークレットマスキング規則）の適用は `feature/persistence-foundation` 責務として明示申し送り済み（本 PR で `storage.md` の適用先一覧に `Room.prompt_kit.prefix_markdown` を追記）。本 feature では「domain VO は raw 保持、Repository 層で適用」という適用先指定を凍結
- **本 feature 固有の申し送り**:
  - LEADER 必須性検査が `RoomService.add_member()` / `RoomService.remove_member()` / `RoomService.create()` に押し出されていること（TC-UT-RM-029 で物理確認）。`feature/room-service` 実装時に Workflow の `required_role` 集合と突合する仕様（確定 R1-D）を漏れなく実装する申し送り
  - prompt injection 対策（敵対的プロンプト検出 / ユーザー入力境界 escape）は `feature/llm-adapter` および `feature/http-api` の入力境界責務として残す。本 feature は長さ制約（10000 文字）のみを Pydantic field validator で Fail Fast
  - `archive()` の冪等性が「結果状態の同値性」（オブジェクト同一性ではない）で担保されていること（TC-UT-RM-012 で `id() != id()` および `__eq__ == True` を同時に assert する）

## レビュー観点（テスト設計レビュー時）

- [ ] REQ-RM-001〜006 すべてに 1 件以上のテストケースがあり、不変条件 5 種が独立 unit で検証されている
- [ ] **`(agent_id, role)` 重複検査**が「同ペア重複 raise（TC-UT-RM-005）+ 同 `agent_id` で異 `role` 許容（TC-UT-RM-006）」の 2 経路で確定 F を物理確認している
- [ ] **`archive()` 冪等性**が既 `archived=True` への呼び出し（TC-UT-RM-012）+ 連続呼び出し（TC-UT-RM-023）の 2 経路で検証され、返り値が `model_validate` 経由の**新インスタンス**であることが明示されている（確定 D）
- [ ] **archived terminal 違反**が `add_member` / `remove_member` / `update_prompt_kit` の 3 ふるまい全てで raise することが TC-UT-RM-013 で網羅されている（確定 E）
- [ ] **application 層責務 4 件**（name 一意 / workflow_id 参照整合性 / LEADER 必須性 / Agent 存在検証）すべてが「Aggregate 内で強制しない」ことを TC-UT-RM-027〜030 で物理確認している
- [ ] **PromptKit auto-mask（確定 H）**が webhook URL 含む長文での例外発生時に message + detail の両方で伏字化されることを TC-UT-RM-014 で確認している
- [ ] **PromptKit VO 規約**が「単一属性 frozen + 構造的等価 + 0〜10000 文字 + NFC のみ（strip しない）」を TC-UT-RM-018 / 019 / 024 で確認している（確定 G + B）
- [ ] MSG-RM-001〜007 の文言が静的文字列で照合される設計になっている（TC-UT-RM-031〜037）
- [ ] 確定 A〜H（pre-validate / NFC + strip / 容量 50 / archive 冪等性 / archived terminal / 同 Agent 兼複数 Role / PromptKit VO 維持 / webhook auto-mask）すべてに証拠ケースが含まれる
- [ ] 脅威 T1（PromptKit 経由 secret 漏洩）/ T2（webhook URL 例外漏洩）への有効性確認ケースが含まれ、サニタイズ・マスキングは別 feature 責務として明示申し送りされている
- [ ] 外部 I/O ゼロの主張が basic-design.md / requirements-analysis.md と整合している（実 ファイルシステム I/O は発生させない、`workflow_id` / `agent_id` は VO 型として保持のみ）
- [ ] frozen 不変性（TC-UT-RM-025）+ 構造的等価（TC-UT-RM-024）+ extra='forbid'（TC-UT-RM-026）が独立して検証されている
- [ ] empire / workflow / agent の WeakValueDictionary レジストリ方式と整合した factory 設計になっている
- [ ] Schneier 申し送り（DB UNIQUE 二重防御 / `feature/persistence-foundation` でのマスキング規則適用 / LEADER 必須性の `RoomService` 押し出し / prompt injection の `feature/llm-adapter` 責務）が次レビュー時に確認可能な形で test-design および設計書に記録されている
