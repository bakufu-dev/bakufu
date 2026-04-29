# 詳細設計書

> feature: `agent` / sub-feature: `http-api`
> 関連 Issue: [#59 feat(agent-http-api): Agent CRUD HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/59)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../../http-api-foundation/http-api/detailed-design.md`](../../http-api-foundation/http-api/detailed-design.md)

## 本書の役割

**実装者が本書だけを読んで迷わず実装できる粒度** で構造契約を凍結する。`basic-design.md §モジュール契約` の各 REQ-AG-HTTP-NNN を、Pydantic スキーマ定義・例外マッピング・確定文言として展開する。

**書くこと**:
- Pydantic スキーマ（フィールド名・型・バリデーション制約）
- 例外マッピングテーブル（domain / application 例外 → HTTP ステータス + ErrorCode + MSG ID）
- MSG 確定文言（エラーレスポンスの `message` フィールド文字列）
- `dependencies.py` 追記内容（`get_agent_service` 拡張）
- `error_handlers.py` 追記内容（agent 専用例外ハンドラ群）
- `AgentService` メソッド一覧と raises 定義
- `AgentRepository` Protocol 拡張（`find_all_by_empire`）

**書かないこと**:
- 疑似コード / サンプル実装 → 設計書とソースコードの二重管理になる
- テストケース → `test-design.md`

## 確定 A: Pydantic スキーマ定義（`interfaces/http/schemas/agent.py`）

`model_config = ConfigDict(extra="forbid")` を全スキーマに適用する（余分なフィールドを拒否）。

### リクエストスキーマ

#### `PersonaCreate`（ネスト用）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `display_name` | `str` | `min_length=1`, `max_length=40` | Persona 表示名（NFC + strip 後、domain バリデーションに委譲）|
| `archetype` | `str \| None` | `max_length=80`（任意）| キャラクター説明。None は `""` として扱う |
| `prompt_body` | `str \| None` | `max_length=10000`（任意）| LLM システムプロンプト。None は `""` として扱う。**raw 値を受け取り domain に渡す。masking は repository 層と HTTP レスポンス層で行う** |

#### `ProviderConfigCreate`（ネスト用）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `provider_kind` | `str` | 有効値: `"CLAUDE_CODE"` / `"CODEX"` / `"GEMINI"` 等 `ProviderKind` StrEnum 値 | domain の `ProviderKind` バリデーションに委譲 |
| `model` | `str` | `min_length=1`, `max_length=80` | モデル名（例: `"claude-sonnet-4-5"`）|
| `is_default` | `bool` | 必須 | providers リスト中で `True` が ちょうど 1 件であることは domain が検査（R1-3）|

#### `SkillRefCreate`（ネスト用）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `skill_id` | `UUID` | 必須 | Skill 識別子 |
| `name` | `str` | `min_length=1`, `max_length=80` | Skill 名 |
| `path` | `str` | `min_length=1`, `max_length=500` | スキル markdown ファイルパス。domain の H1〜H10 パストラバーサル防御に委譲 |

#### `AgentCreate`（POST /api/empires/{empire_id}/agents Body）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `name` | `str` | `min_length=1`, `max_length=40` | Agent 名（R1-1）|
| `persona` | `PersonaCreate` | 必須 | Persona VO 定義 |
| `role` | `str` | 有効値: `"DEVELOPER"` / `"ARCHITECT"` / `"QA"` / `"PM"` / `"RESEARCHER"` 等 `Role` StrEnum 値 | domain の `Role` バリデーションに委譲 |
| `providers` | `list[ProviderConfigCreate]` | `min_length=1`（R1-2、1 件以上必須）| LLM プロバイダ構成。domain 不変条件 R1-2〜3 を domain で検査 |
| `skills` | `list[SkillRefCreate]` | 任意、デフォルト `[]` | スキル参照リスト。domain 不変条件 R1-4 を domain で検査 |

#### `PersonaUpdate`（ネスト用）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `display_name` | `str \| None` | `min_length=1`, `max_length=40`（適用時のみ）| None は変更なし |
| `archetype` | `str \| None` | `max_length=80`（適用時のみ）| None は変更なし |
| `prompt_body` | `str \| None` | `max_length=10000`（適用時のみ）| None は変更なし |

**PersonaUpdate の部分更新ルール**: PersonaUpdate が非 None で渡された場合、各フィールドが非 None のもののみ既存 Persona の対応フィールドを差し替える。全フィールド None の PersonaUpdate は「変更なし」として無視する。

#### `AgentUpdate`（PATCH /api/agents/{id} Body）

| フィールド | 型 | 制約 | 備考 |
|---|---|---|---|
| `name` | `str \| None` | `min_length=1`, `max_length=40`（適用時のみ）| None は変更なし |
| `persona` | `PersonaUpdate \| None` | 任意 | None は変更なし |
| `role` | `str \| None` | 有効 `Role` StrEnum 値（適用時のみ）| None は変更なし |
| `providers` | `list[ProviderConfigCreate] \| None` | `min_length=1`（適用時のみ）| None は変更なし。**設定時は全 providers を置換**（部分更新禁止 — providers の is_default 一意性は全 list を再評価しなければ保証できないため）|
| `skills` | `list[SkillRefCreate] \| None` | 任意 | None は変更なし。**設定時は全 skills を置換** |

全フィールド None の AgentUpdate も有効（変更なしの no-op PATCH、既存 Agent をそのまま返す）。

### レスポンスサブスキーマ

#### `PersonaResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `display_name` | `str` | Persona.display_name |
| `archetype` | `str` | Persona.archetype |
| `prompt_body` | `str` | **§確定 A-masking（全パス凍結）**: `PersonaResponse.prompt_body` の `field_serializer` は GET / POST / PATCH 全レスポンスパスで発火する（R1-9 独立防御）。POST / PATCH 時は in-memory `Persona.prompt_body`（raw 値）を `ApplicationMasking.mask(value)` により伏字化する。GET 時は DB 復元済みの masked 値（`<REDACTED:*>`）に同じ `ApplicationMasking.mask()` を適用する。`ApplicationMasking.mask()` は冪等（`<REDACTED:*>` → `<REDACTED:*>`）のため見た目上は変化しないが、**GET パスでも必ず field_serializer が発火する**ことで DB への raw token 直接 INSERT バイパスが発生しても HTTP レスポンスには露出しない（A02 二重防御）。import パスは `from bakufu.application.security.masking import ApplicationMasking`（interfaces → application 依存、TC-UT-AGH-009 の `bakufu.infrastructure` 禁止制約を維持 — §確定I 参照）。なお `prompt_body` は pydantic regex 制約なしのフリーテキストのため、masked 値を保持した Agent に対して `AgentRepository.find_by_id` が `pydantic.ValidationError` を起こすことはない（workflow R1-16 の EXTERNAL_REVIEW Stage 問題とは構造的に異なる）|

#### `ProviderConfigResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `provider_kind` | `str` | ProviderKind StrEnum 値（例: `"CLAUDE_CODE"`）|
| `model` | `str` | モデル名 |
| `is_default` | `bool` | 既定プロバイダフラグ |

#### `SkillRefResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `skill_id` | `str` | UUID 文字列 |
| `name` | `str` | Skill 名 |
| `path` | `str` | スキル markdown ファイルパス |

### レスポンススキーマ

#### `AgentResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `id` | `str` | AgentId（UUID 文字列）|
| `empire_id` | `str` | EmpireId（UUID 文字列）|
| `name` | `str` | Agent.name |
| `persona` | `PersonaResponse` | Persona VO（prompt_body は masked）|
| `role` | `str` | Role StrEnum 値 |
| `providers` | `list[ProviderConfigResponse]` | ProviderConfig リスト |
| `skills` | `list[SkillRefResponse]` | SkillRef リスト |
| `archived` | `bool` | Agent.archived |

`model_config = ConfigDict(from_attributes=True)` を適用。domain `Agent` からの変換時は `str(agent.id)` / `str(agent.empire_id)` で UUID → 文字列変換。

#### `AgentListResponse`

| フィールド | 型 | 備考 |
|---|---|---|
| `items` | `list[AgentResponse]` | 0 件以上 |
| `total` | `int` | `len(items)` |

## 確定 B: 例外マッピングテーブル

agent http-api に関わるすべての例外と HTTP レスポンスの対応を凍結する。Router 内では `try/except` を書かない（http-api-foundation architecture 規律）。

| 例外クラス | 発生箇所 | HTTP ステータス | ErrorCode | MSG ID |
|---|---|---|---|---|
| `AgentNotFoundError` | `AgentService.find_by_id` / `archive` / `update`（None 時）| 404 | `not_found` | MSG-AG-HTTP-001 |
| `AgentNameAlreadyExistsError` | `AgentService.hire`（find_by_name ヒット）/ `update`（name 変更時 find_by_name ヒット）| 409 | `conflict` | MSG-AG-HTTP-002 |
| `AgentArchivedError` | `AgentService.update`（archived=True 時）| 409 | `conflict` | MSG-AG-HTTP-003 |
| `AgentInvariantViolation` | domain Agent 構築 / update（不変条件 R1-1〜4 違反）| 422 | `validation_error` | MSG-AG-HTTP-004（前処理済み本文）|
| `EmpireNotFoundError` | `AgentService.hire` / `find_by_empire`（Empire 不在）| 404 | `not_found` | MSG-EM-HTTP-002（empire 既存ハンドラが処理）|
| `RequestValidationError` | FastAPI Pydantic デシリアライズ失敗 | 422 | `validation_error` | http-api-foundation MSG-HAF-002（既存ハンドラが処理）|
| `HTTPException` | CSRF ミドルウェア（`Origin` 不一致）| 403 | `forbidden` | http-api-foundation MSG-HAF-004（既存ハンドラが処理）|
| `Exception`（その他）| どこでも | 500 | `internal_error` | http-api-foundation MSG-HAF-003（既存ハンドラが処理）|

## 確定 C: 例外ハンドラ実装（`error_handlers.py` 追記）

http-api-foundation の `error_handlers.py` に以下のハンドラ関数を追記し、`app.py` の `_register_exception_handlers` で登録する。

| ハンドラ関数名 | 処理例外 | 返却する ErrorResponse |
|---|---|---|
| `agent_not_found_handler` | `AgentNotFoundError` | `ErrorResponse(code="not_found", message=MSG-AG-HTTP-001)` + HTTP 404（既存の暫定ハンドラを正式版に変更 — import 元を `room_exceptions` → `agent_exceptions` に更新）|
| `agent_name_already_exists_handler` | `AgentNameAlreadyExistsError` | `ErrorResponse(code="conflict", message=MSG-AG-HTTP-002)` + HTTP 409 |
| `agent_archived_handler` | `AgentArchivedError` | `ErrorResponse(code="conflict", message=MSG-AG-HTTP-003)` + HTTP 409 |
| `agent_invariant_violation_handler` | `AgentInvariantViolation` | HTTP 422, `ErrorResponse(code="validation_error", message=<前処理済みメッセージ>)` |

登録順は workflow ハンドラ群の直後（既存の `HTTPException` / `RequestValidationError` / `Exception` ハンドラより**前**）に登録する。

**`agent_invariant_violation_handler` の前処理ルール（empire / room / workflow と同一パターン）**:
1. `[FAIL] ` プレフィックスを除去: `re.sub(r"^\[FAIL\]\s*", "", str(exc))`
2. `\nNext:` 以降を除去: `.split("\nNext:")[0].strip()`

これにより domain 内部の AI エージェント向けフォーマットが HTTP クライアントに露出しない。

## 確定 D: `AgentRepository` Protocol 拡張（前提条件 P-1 の実装仕様）

`application/ports/agent_repository.py` に以下メソッドを追記する。

| メソッド | 引数 | 戻り値 | 説明 |
|---|---|---|---|
| `find_all_by_empire` | `empire_id: EmpireId` | `list[Agent]` | Empire 内の全 Agent を返す。0 件の場合は空リスト。アーカイブ済みも含む。SQL: `SELECT ... FROM agents WHERE empire_id = :empire_id ORDER BY name` で取得し、各行に対して `find_by_id` と同一の子テーブル JOIN パターンで Agent 復元 |

`SqliteAgentRepository` にも同メソッドを実装する。実装は `agents` テーブルを `empire_id` でフィルタし、`agent_providers`（`ORDER BY provider_kind`）/ `agent_skills`（`ORDER BY skill_id`）を JOIN して Agent を復元する。

## 確定 E: エンドポイント定義（`routers/agents.py`）

| メソッド | パス | パスパラメータ | リクエスト Body | レスポンス | ステータスコード |
|---|---|---|---|---|---|
| POST | `/api/empires/{empire_id}/agents` | `empire_id: UUID` | `AgentCreate` | `AgentResponse` | 201 |
| GET | `/api/empires/{empire_id}/agents` | `empire_id: UUID` | なし | `AgentListResponse` | 200 |
| GET | `/api/agents/{id}` | `id: UUID` | なし | `AgentResponse` | 200 |
| PATCH | `/api/agents/{id}` | `id: UUID` | `AgentUpdate` | `AgentResponse` | 200 |
| DELETE | `/api/agents/{id}` | `id: UUID` | なし | なし（No Content）| 204 |

Router は 2 つの `APIRouter` で構成する:
- `empire_agents_router`: `prefix="/api/empires"`, `tags=["agent"]`（empire_id スコープのエンドポイント）
- `agents_router`: `prefix="/api/agents"`, `tags=["agent"]`（agent_id スコープのエンドポイント）

`http-api-foundation` の `app.py` に両 router を `app.include_router(...)` で追記する。

## 確定 F: application 例外定義（`application/exceptions/agent_exceptions.py`）

| 例外クラス名 | 基底クラス | `__init__` 引数 | 用途 |
|---|---|---|---|
| `AgentNotFoundError` | `Exception` | `agent_id: str` | find_by_id / archive / update で Agent 不在（room_exceptions.py の暫定定義を正式移転）|
| `AgentNameAlreadyExistsError` | `Exception` | `empire_id: str`, `name: str` | hire / update で同 Empire 内に同名 Agent が存在（R1-6 違反）|
| `AgentArchivedError` | `Exception` | `agent_id: str` | update で archived=True の Agent を操作しようとした（R1-5 違反）|

**`AgentNotFoundError` の正式移転（room_exceptions.py との整合）**:
room http-api（Issue #57）で `room_exceptions.py` に暫定定義された `AgentNotFoundError` は、本 PR で `agent_exceptions.py` に正式移転する。`room_exceptions.py` では `from bakufu.application.exceptions.agent_exceptions import AgentNotFoundError` に変更し暫定定義を削除する。`error_handlers.py` の既存 `agent_not_found_handler` 関数内の import 元も同様に更新する。

## 確定 G: `AgentService` メソッド一覧

http-api-foundation 確定F で骨格が確定済み（`AgentService.__init__(repo: AgentRepository)`）。本 PR で以下のシグネチャに変更し、メソッドを全て肉付けする。

コンストラクタ変更: `__init__(self, agent_repo, empire_repo, session)` に拡張（Empire 存在確認のため `EmpireRepository` と `AsyncSession` を追加）。

| メソッド名 | 引数 | 戻り値 | raises |
|---|---|---|---|
| `hire` | `empire_id: EmpireId, agent_create: AgentCreateDTO` | `Agent` | `EmpireNotFoundError` / `AgentNameAlreadyExistsError` / `AgentInvariantViolation` |
| `find_by_empire` | `empire_id: EmpireId` | `list[Agent]` | `EmpireNotFoundError` |
| `find_by_id` | `agent_id: AgentId` | `Agent` | `AgentNotFoundError` |
| `update` | `agent_id: AgentId, name: str \| None, persona: PersonaUpdateDTO \| None, role: str \| None, providers: list \| None, skills: list \| None` | `Agent` | `AgentNotFoundError` / `AgentArchivedError` / `AgentNameAlreadyExistsError` / `AgentInvariantViolation` |
| `archive` | `agent_id: AgentId` | `None` | `AgentNotFoundError` |

`hire` / `update` / `archive` は `async with session.begin()` を service 内で開く（UoW 責務は service 層が持つ）。

**`update` の部分更新ルール（凍結）**:
- `name` が非 None → 同 Empire 内の name 重複チェック後に差し替え
- `persona` が非 None → PersonaUpdate の各フィールドで非 None のもののみ既存 Persona を差し替え（3 フィールド独立更新可）
- `role` が非 None → 差し替え
- `providers` が非 None → 全置換（部分更新禁止。is_default 一意性は全 list 再評価が必要なため）
- `skills` が非 None → 全置換
- 上記差し替えを適用した dict で `Agent.model_validate(updated_dict)` を呼び不変条件を再検査

**`archive` の冪等性**: `agent.archived` がすでに True の場合も `agent.archive()` を呼び出し save する（冪等）。2 回目の DELETE も 204 を返す。

## 確定 H: `dependencies.py` 追記（DI ファクトリ拡張）

`get_agent_service` を以下に変更する。

| 関数名 | 型シグネチャ変更前 | 型シグネチャ変更後 |
|---|---|---|
| `get_agent_service` | `(session: SessionDep) → AgentService`（AgentRepo のみ）| `(session: SessionDep) → AgentService`（AgentRepo + EmpireRepo + session を渡す）|

`get_agent_service` の実装変更点:
- `SqliteEmpireRepository(session)` を生成し `EmpireRepository` として渡す
- `session` を `AgentService` コンストラクタに渡す（UoW のため）
- `get_empire_service()` への依存は持たない（循環依存を避けるため AgentService が EmpireRepository を直接受け取る — workflow http-api §確定H と同パターン）

`AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]` 型エイリアスを定義し、各エンドポイントで簡潔に使えるようにする。

## MSG 確定文言表

| MSG ID | `code` | `message`（確定文言）| HTTP ステータス |
|---|---|---|---|
| MSG-AG-HTTP-001 | `not_found` | `"Agent not found."` | 404 |
| MSG-AG-HTTP-002 | `conflict` | `"Agent with this name already exists in the Empire."` | 409 |
| MSG-AG-HTTP-003 | `conflict` | `"Agent is archived and cannot be modified."` | 409 |
| MSG-AG-HTTP-004 | `validation_error` | `AgentInvariantViolation.message` から `[FAIL]` プレフィックスと `\nNext:.*` を除去した本文のみ（例: `"providers must have exactly one default provider."`）| 422 |

MSG-AG-HTTP-004 は domain 層の `AgentInvariantViolation.message` を **前処理したうえで** HTTP レスポンスに使用する（前処理ルールは §確定C 末尾に凍結）。

## 確定 I: `application/security/masking.py`（masking ユーティリティ昇格）

`interfaces/http/schemas/agent.py` の `PersonaResponse.field_serializer` は `application` 層の masking ユーティリティを呼び出す。interfaces → infrastructure 直接依存を禁止する TC-UT-AGH-009 の静的解析制約を維持するための配置確定。

| 項目 | 内容 |
|---|---|
| 新規ファイル | `bakufu/application/security/masking.py` |
| 実装内容 | `ApplicationMasking` クラスが application 層の明示的なゲートウェイとして `MaskingGateway.mask()` を委譲呼び出しする。公開関数 alias は置かない。masking ロジックの実体は `infrastructure/security/masking.py` が唯一の真実源として保持する（DRY 原則）|
| import パス（schemas から） | `from bakufu.application.security.masking import ApplicationMasking` |
| 依存方向 | interfaces → application（許容）/ application → infrastructure（許容）/ interfaces → infrastructure の直接依存なし |
| 冪等性保証 | `ApplicationMasking.mask()` は冪等。`<REDACTED:*>` を入力しても同一の `<REDACTED:*>` を返す。GET パス field_serializer の二重 masking が副作用を持たないことを保証する |
| TC-UT-AGH-009 との整合 | `interfaces/http/schemas/` から `bakufu.infrastructure` への直接 import が存在しないことを静的解析で検証。`bakufu.application` への import は許容範囲 |

## 参照設計との整合確認

| http-api-foundation 確定事項 | agent http-api での適用 |
|---|---|
| 確定A: ErrorCode 定数（`not_found` / `validation_error` / `internal_error` / `forbidden`）| `conflict` を empire / room / workflow と共通で使用（`error_handlers.py` の `ErrorCode` 定数に追加済み）|
| 確定B: `app.state.session_factory` / `engine` | `get_session()` DI 経由で `AsyncSession` を取得（変更なし）|
| 確定D: CSRF Origin 検証（MVP: Origin なし通過 / 不一致 403）| POST / PATCH / DELETE は CSRF ミドルウェアが適用される（追加設定不要）|
| 確定E: `get_session()` DI | `get_agent_service(session=Depends(get_session))` で利用（変更なし）|
| 確定F: Service `__init__(repo)` 骨格 | `AgentService.__init__` の引数を agent_repo + empire_repo + session に拡張 |

## 開放論点

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | `GET /api/empires/{empire_id}/agents` でアーカイブ済みを除外するクエリパラメータ（`?archived=false` 等）は MVP では不要と判断しスコープ外とした。将来 Agent 数が増えた場合に別 Issue で対応 | 将来 Issue |
| ~~Q-OPEN-2~~ | ~~`PersonaResponse.prompt_body` の masking は infrastructure 層を直接呼び出す（interfaces → infrastructure の依存）。依存方向として許容範囲だが、将来的に masking 関数を `application` 層のユーティリティに昇格させる案がある~~ → **本 PR で §確定I として凍結済み**。`ApplicationMasking` 昇格・interfaces → application 経由呼び出し・TC-UT-AGH-009 禁止制約を維持することで確定。 | ~~将来 Issue~~ → 本 PR 解決 |
| Q-OPEN-3 | `AgentUpdate` で `providers` / `skills` を個別に追加 / 削除する API（`POST /api/agents/{id}/providers` / `DELETE /api/agents/{id}/skills/{skill_id}` 等）は MVP では複雑性増加を避けるためスコープ外とした。UI ワークフローエディタの要件次第で将来追加 | 将来 Issue（agent-ui）|
