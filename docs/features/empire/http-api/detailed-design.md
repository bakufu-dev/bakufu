# 詳細設計書

> feature: `empire` / sub-feature: `http-api`
> 関連 Issue: [#56 feat(empire-http-api): Empire HTTP API (M3-B)](https://github.com/bakufu-dev/bakufu/issues/56)
> 関連: [`basic-design.md §モジュール契約`](basic-design.md) / [`../feature-spec.md`](../feature-spec.md) / [`../../http-api-foundation/http-api/detailed-design.md`](../../http-api-foundation/http-api/detailed-design.md)

## 本書の役割

**実装者が本書だけを読んで迷わず実装できる粒度** で構造契約を凍結する。`basic-design.md §モジュール契約` の各 REQ-EM-HTTP-NNN を、Pydantic スキーマ定義・例外マッピング・確定文言として展開する。

**書くこと**:
- Pydantic スキーマ（フィールド名・型・バリデーション制約）
- 例外マッピングテーブル（domain 例外 → HTTP ステータス + ErrorCode + MSG ID）
- MSG 確定文言（エラーレスポンスの `message` フィールド文字列）
- `dependencies.py` 追記内容（`get_empire_repository` / `get_empire_service`）
- `error_handlers.py` 追記内容（empire 専用例外ハンドラ）

**書かないこと**:
- 疑似コード / サンプル実装 → 設計書とソースコードの二重管理になる
- テストケース → `test-design.md`

## 確定 A: Pydantic スキーマ定義（`interfaces/http/schemas/empire.py`）

http-api-foundation 確定A の `ErrorResponse` / `ErrorDetail` と同一ファイル分割方針に従い、empire 専用スキーマを `schemas/empire.py` に配置する。

### リクエストスキーマ

| スキーマ名 | フィールド | 型 | 制約 | 用途 |
|---|---|---|---|---|
| `EmpireCreate` | `name` | `str` | `min_length=1`, `max_length=80`（業務ルール R1-1）| POST /api/empires リクエスト Body |
| `EmpireUpdate` | `name` | `str \| None` | `min_length=1`, `max_length=80`（適用時のみ）| PATCH /api/empires/{id} リクエスト Body |

`EmpireUpdate` は `name=None` の場合は変更なし（部分更新 PATCH パターン）。`model_config = ConfigDict(extra="forbid")` を全スキーマに適用する（余分なフィールドを拒否、Q-3 物理保証）。

### レスポンスサブスキーマ

| スキーマ名 | フィールド | 型 | 備考 |
|---|---|---|---|
| `AgentRefResponse` | `agent_id` | `str` | UUID 文字列 |
| | `name` | `str` | AgentRef.name |
| | `role` | `str` | AgentRef.role（Role enum の値）|
| `RoomRefResponse` | `room_id` | `str` | UUID 文字列 |
| | `name` | `str` | RoomRef.name |
| | `archived` | `bool` | RoomRef.archived |

### レスポンススキーマ

| スキーマ名 | フィールド | 型 | 備考 |
|---|---|---|---|
| `EmpireResponse` | `id` | `str` | Empire.id（UUID 文字列）|
| | `name` | `str` | Empire.name |
| | `archived` | `bool` | Empire.archived |
| | `rooms` | `list[RoomRefResponse]` | Empire.rooms のマップ |
| | `agents` | `list[AgentRefResponse]` | Empire.agents のマップ |
| `EmpireListResponse` | `items` | `list[EmpireResponse]` | 0 件または 1 件 |
| | `total` | `int` | `len(items)` |

`EmpireResponse` は `model_config = ConfigDict(from_attributes=True)` を適用し、domain `Empire` から直接変換できるようにする。ただし Pydantic `.model_validate(empire)` を使う場合は `id` が `EmpireId`（UUID wrapper）のため `str(empire.id)` で文字列変換する点に注意。

## 確定 B: 例外マッピングテーブル

empire http-api に関わるすべての例外と HTTP レスポンスの対応を凍結する。Router 内では `try/except` を書かない（http-api-foundation architecture 規律）。

| 例外クラス | 発生箇所 | HTTP ステータス | ErrorCode | MSG ID |
|---|---|---|---|---|
| `EmpireNotFoundError` | `EmpireService.find_by_id`（None 時）/ `EmpireService.archive`（None 時）| 404 | `not_found` | MSG-EM-HTTP-002 |
| `EmpireAlreadyExistsError` | `EmpireService.create`（count > 0 時）| 409 | `conflict` | MSG-EM-HTTP-001 |
| `EmpireArchivedError` | `EmpireService.update`（archived=True 時）| 409 | `conflict` | MSG-EM-HTTP-003 |
| `EmpireInvariantViolation` | `Empire.__init__` / `hire_agent` / `establish_room` / `archive_room`（domain 層）| 422 | `validation_error` | MSG-EM-HTTP-004（str(exc) を message に使用）|
| `RequestValidationError` | FastAPI Pydantic デシリアライズ失敗 | 422 | `validation_error` | http-api-foundation MSG-HAF-002（既存ハンドラが処理）|
| `HTTPException` | CSRF ミドルウェア（`Origin` 不一致）| 403 | `forbidden` | http-api-foundation MSG-HAF-004（既存ハンドラが処理）|
| `Exception`（その他）| どこでも | 500 | `internal_error` | http-api-foundation MSG-HAF-003（既存ハンドラが処理）|

`EmpireNotFoundError` の ErrorCode は `not_found`（http-api-foundation 確定A と共通コードを使用）。404 に対して `not_found` を返す既存 `http_exception_handler` は `HTTPException(status_code=404)` をトリガとするため、`EmpireNotFoundError` は直接 `HTTPException(status_code=404, ...)` に変換して既存ハンドラに委譲するか、専用ハンドラで処理する（実装者の判断で選択可、ただし ErrorCode は `not_found` に固定する）。

## 確定 C: 例外ハンドラ実装（`error_handlers.py` 追記）

http-api-foundation の `error_handlers.py` に以下のハンドラ関数を追記し、`app.py` の `_register_exception_handlers` で登録する。

| ハンドラ関数名 | 処理例外 | 返却する ErrorResponse |
|---|---|---|
| `empire_already_exists_handler` | `EmpireAlreadyExistsError` | `ErrorResponse(code="conflict", message=MSG-EM-HTTP-001)` + HTTP 409 |
| `empire_archived_handler` | `EmpireArchivedError` | `ErrorResponse(code="conflict", message=MSG-EM-HTTP-003)` + HTTP 409 |
| `empire_invariant_violation_handler` | `EmpireInvariantViolation` | `ErrorResponse(code="validation_error", message=str(exc))` + HTTP 422 |
| `empire_not_found_handler` | `EmpireNotFoundError` | `ErrorResponse(code="not_found", message=MSG-EM-HTTP-002)` + HTTP 404 |

登録順は既存の `HTTPException` / `RequestValidationError` / `Exception` ハンドラより **前**（より具体的な例外を先に登録する FastAPI の慣習に従う）。

## 確定 D: `dependencies.py` 追記（DI ファクトリ）

http-api-foundation の `dependencies.py` に以下を追記する。

| 関数名 | 型シグネチャ | 依存 |
|---|---|---|
| `get_empire_repository` | `(session: AsyncSession = Depends(get_session)) → EmpireRepository` | `get_session()`（http-api-foundation 確定E）|
| `get_empire_service` | `(repo: EmpireRepository = Depends(get_empire_repository)) → EmpireService` | `get_empire_repository()` |

`get_empire_service` は `Annotated[EmpireService, Depends(get_empire_service)]` 型エイリアスを定義し、各エンドポイントで簡潔に使えるようにする。

## 確定 E: エンドポイント定義（`routers/empire.py`）

| メソッド | パス | パスパラメータ | リクエスト Body | レスポンス | ステータスコード |
|---|---|---|---|---|---|
| POST | `/api/empires` | なし | `EmpireCreate` | `EmpireResponse` | 201 |
| GET | `/api/empires` | なし | なし | `EmpireListResponse` | 200 |
| GET | `/api/empires/{empire_id}` | `empire_id: str` | なし | `EmpireResponse` | 200 |
| PATCH | `/api/empires/{empire_id}` | `empire_id: str` | `EmpireUpdate` | `EmpireResponse` | 200 |
| DELETE | `/api/empires/{empire_id}` | `empire_id: str` | なし | なし（No Content）| 204 |

`empire_id` パスパラメータは `str` で受け取り、`EmpireId(UUID(empire_id))` に変換する（不正 UUID 形式は FastAPI の path validation で 422 を返す）。

Router の `prefix="/api/empires"`, `tags=["empire"]` で登録。http-api-foundation の `app.py` に `app.include_router(empire_router)` を追記する。

## 確定 F: application 例外定義（`application/exceptions/empire_exceptions.py`）

| 例外クラス名 | 基底クラス | `__init__` 引数 | 用途 |
|---|---|---|---|
| `EmpireNotFoundError` | `Exception` | `empire_id: str` | 取得・更新・削除で対象が見つからない場合 |
| `EmpireAlreadyExistsError` | `Exception` | なし | create 時 Empire が既に存在する場合（R1-5）|
| `EmpireArchivedError` | `Exception` | `empire_id: str` | アーカイブ済みへの更新操作（R1-8）|

これらは application 層の例外であり、domain 例外（`EmpireInvariantViolation`）とは独立する。interfaces 層の例外ハンドラが catch して HTTP レスポンスに変換する。

## 確定 G: `EmpireService` メソッド一覧

http-api-foundation 確定F で骨格が確定済み（`EmpireService.__init__(repo: EmpireRepository)`）。本 PR で以下のメソッドを肉付けする。

| メソッド名 | 引数 | 戻り値 | raises |
|---|---|---|---|
| `create` | `name: str` | `Empire` | `EmpireAlreadyExistsError` / `EmpireInvariantViolation` |
| `find_all` | なし | `list[Empire]` | なし |
| `find_by_id` | `empire_id: EmpireId` | `Empire` | `EmpireNotFoundError` |
| `update` | `empire_id: EmpireId, name: str \| None` | `Empire` | `EmpireNotFoundError` / `EmpireArchivedError` / `EmpireInvariantViolation` |
| `archive` | `empire_id: EmpireId` | `None` | `EmpireNotFoundError` |

`create` は `async with session.begin()` を service 内で開く（UoW 責務は service 層が持つ）。`update` / `archive` も同様。

## 確定 H: domain 拡張仕様

本 PR の実装スコープとして、以下の最小変更を `domain/empire.py` に加える。

| 変更種別 | 内容 |
|---|---|
| フィールド追加 | `archived: bool = False`（frozen モデルのため、コンストラクタ引数で渡す）|
| メソッド追加 | `archive() → Empire`：`Empire(**self.model_dump() | {"archived": True})` で新インスタンスを返す（不変モデルに準拠）|

`archived=True` の Empire への `hire_agent` / `establish_room` / `archive_room` は業務的に禁止とする（詳細は `detailed-design.md §確定 H` で将来定義）。本 PR では service 層が `EmpireArchivedError` を raise することで保護する。

## 確定 I: Alembic マイグレーション

3rd revision `0003_empire_archived.py` の変更内容:

| テーブル | カラム | 型 | DEFAULT | NOT NULL |
|---|---|---|---|---|
| `empires` | `archived` | `Boolean` | `false` | YES |

`upgrade()`: `ALTER TABLE empires ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE`
`downgrade()`: `ALTER TABLE empires DROP COLUMN archived`

## MSG 確定文言表

| MSG ID | `code` | `message`（確定文言）| HTTP ステータス |
|---|---|---|---|
| MSG-EM-HTTP-001 | `conflict` | `"Empire already exists."` | 409 |
| MSG-EM-HTTP-002 | `not_found` | `"Empire not found."` | 404 |
| MSG-EM-HTTP-003 | `conflict` | `"Empire is archived and cannot be modified."` | 409 |
| MSG-EM-HTTP-004 | `validation_error` | `str(exc)`（`EmpireInvariantViolation` の message を直接使用）| 422 |

MSG-EM-HTTP-004 は `EmpireInvariantViolation` の `message` 属性をそのまま使用する。これにより domain 層の MSG-EM-001〜005 の確定文言（domain/basic-design.md §ユーザー向けメッセージ一覧）が HTTP レスポンスに伝播する。

## 参照設計との整合確認

| http-api-foundation 確定事項 | empire http-api での適用 |
|---|---|
| 確定A: ErrorCode 定数（`not_found` / `validation_error` / `internal_error` / `forbidden`）| `conflict` を empire 専用 ErrorCode として追加（`error_handlers.py` の `ErrorCode` 定数に追記）|
| 確定B: `app.state.session_factory` / `engine`| `get_session()` DI 経由で `AsyncSession` を取得（変更なし）|
| 確定D: CSRF Origin 検証（MVP: Origin なし通過 / 不一致 403）| POST / PATCH / DELETE は CSRF ミドルウェアが適用される（追加設定不要）|
| 確定E: `get_session()` DI | `get_empire_repository(session=Depends(get_session))` で利用（変更なし）|
| 確定F: Service `__init__(repo)` 骨格 | `EmpireService.__init__(self, repo: EmpireRepository)` で確定済み（本 PR でメソッド肉付け）|
