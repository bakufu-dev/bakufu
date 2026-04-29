# 基本設計書

> feature: `empire`
> 関連: [basic-design.md §モジュール契約](basic-design.md) / [`docs/design/domain-model/aggregates.md`](../../../design/domain-model/aggregates.md) §Empire

## 記述ルール（必ず守ること）

基本設計に**疑似コード・サンプル実装（python/ts/sh/yaml 等の言語コードブロック）を書かない**。
ソースコードと二重管理になりメンテナンスコストしか生まない。
必要なのは構造契約（クラス・モジュール・データの関係）であり、実装の細部は [detailed-design.md](detailed-design.md) で凍結する。

## モジュール構成

| 機能 ID | モジュール | ディレクトリ | 責務 |
|--------|----------|------------|------|
| REQ-EM-001〜005 | `Empire` Aggregate Root | `backend/src/bakufu/domain/empire.py` | Empire の属性・不変条件・ふるまい |
| REQ-EM-002, 003 | `RoomRef` / `AgentRef` Value Object | `backend/src/bakufu/domain/value_objects.py`（既存ファイル更新） | Empire 内に保持される参照 VO |
| REQ-EM-005 | `EmpireInvariantViolation` 例外 | `backend/src/bakufu/domain/exceptions.py`（既存ファイル更新） | ドメイン例外 |
| 共通 | ID 型 `EmpireId` / `RoomId` / `AgentId` / 列挙型 `Role` | `backend/src/bakufu/domain/value_objects.py`（既存定義） | 既存定義を参照、本 feature で追加なし |

```
ディレクトリ構造（本 feature で追加・変更されるファイル）:

.
└── backend/
    ├── src/
    │   └── bakufu/
    │       └── domain/
    │           ├── empire.py            # 新規: Empire Aggregate Root
    │           ├── value_objects.py     # 既存更新: RoomRef / AgentRef 追加
    │           └── exceptions.py        # 既存更新: EmpireInvariantViolation 追加
    └── tests/
        └── domain/
            └── test_empire.py           # 新規: ユニットテスト
```

## モジュール契約（機能要件）

本 sub-feature が提供するモジュールの入出力契約を凍結する。各 REQ-EM-NNN は親 [`feature-spec.md §5`](../feature-spec.md) ユースケース UC-EM-NNN と 1:1 または N:1 で対応する（孤児要件を作らない）。

### REQ-EM-001: Empire 構築

| 項目 | 内容 |
|---|---|
| 入力 | `id: EmpireId`（UUIDv4）、`name: str`（1〜80 文字） |
| 処理 | 入力（id / name）を業務ルール R1-1（[`../feature-spec.md §7`](../feature-spec.md)）に照らして検査 → 通過時のみ Empire を新規構築（rooms / agents は空の状態で構築） |
| 出力 | `Empire` インスタンス（rooms / agents が空の状態） |
| エラー時 | 業務ルール R1-1 違反（name 範囲外）で `EmpireInvariantViolation` を raise（MSG-EM-001） |

### REQ-EM-002: Agent 採用

| 項目 | 内容 |
|---|---|
| 入力 | `agent_ref: AgentRef`（`agent_id`, `name`, `role` を含む VO） |
| 処理 | 既採用一覧と照らして `agent_id` の重複（業務ルール R1-2）および容量上限（業務ルール R1-6）を検査 → 通過時のみ採用。実装方針は [`detailed-design.md §確定 A`](detailed-design.md) |
| 出力 | `agent_ref.agent_id` + 更新された Empire |
| エラー時 | 業務ルール R1-2 違反（`agent_id` 重複）または R1-6 違反（容量超過）で `EmpireInvariantViolation`（MSG-EM-002 / MSG-EM-005）を raise。失敗時、元の Empire は変化しない（pre-validate 方式の保証） |

### REQ-EM-003: Room 設立

| 項目 | 内容 |
|---|---|
| 入力 | `room_ref: RoomRef`（`room_id`, `name`, `archived=False` で初期化済み） |
| 処理 | 既設立一覧と照らして `room_id` の重複（業務ルール R1-3）および容量上限（業務ルール R1-6）を検査 → 通過時のみ設立 |
| 出力 | `room_ref.room_id` + 更新された Empire |
| エラー時 | 業務ルール R1-3 違反または R1-6 違反で `EmpireInvariantViolation`（MSG-EM-003 / MSG-EM-005）を raise |

### REQ-EM-004: Room アーカイブ

| 項目 | 内容 |
|---|---|
| 入力 | `room_id: RoomId` |
| 処理 | 既設立一覧から該当する Room を検索 → 見つかれば archived フラグを立てた状態に置換した新 Empire を返す（業務ルール R1-4 により物理削除はしない、履歴保持） |
| 出力 | 更新された Empire |
| エラー時 | `room_id` が既設立一覧に存在しない場合 `EmpireInvariantViolation`（MSG-EM-004） |

### REQ-EM-005: 不変条件検査

| 項目 | 内容 |
|---|---|
| 入力 | Empire インスタンス（コンストラクタ末尾 / 状態変更ふるまい末尾で自動呼び出し） |
| 処理 | 以下を検査: ① name 範囲（業務ルール R1-1）② `agent_id` の重複なし（R1-2）③ `room_id` の重複なし（R1-3）④ 採用済み一覧 / 設立済み一覧の容量上限（R1-6） |
| 出力 | None（検査通過） |
| エラー時 | いずれか違反で `EmpireInvariantViolation` を raise（kind フィールドに違反種別） |

## ユーザー向けメッセージ一覧

| ID | 種別 | メッセージ（要旨） | 表示条件 |
|---|---|---|---|
| MSG-EM-001 | エラー（境界値） | Empire name は 1〜80 文字 | `name` が長さ違反 |
| MSG-EM-002 | エラー（重複） | Agent {name} はすでに採用済み | `hire_agent` で `agent_id` 重複 |
| MSG-EM-003 | エラー（重複） | Room {name} はすでに設立済み | `establish_room` で `room_id` 重複 |
| MSG-EM-004 | エラー（参照エラー） | Room {room_id} が Empire 内に存在しない | `archive_room` で未登録 ID |
| MSG-EM-005 | エラー（一般） | Empire 不変条件違反: {detail} | 上記以外の不変条件違反 |

各メッセージの確定文言は [`detailed-design.md §MSG 確定文言表`](detailed-design.md) で凍結する。

## 依存関係

| 区分 | 依存 | バージョン方針 | 備考 |
|---|---|---|---|
| ランタイム | Python 3.12+ | pyproject.toml | 既存 |
| Python 依存 | pydantic v2 / pyright (strict) / ruff / pytest / pytest-cov | pyproject.toml | 既存（[`tech-stack.md`](../../../design/tech-stack.md)） |
| Node 依存 | 該当なし | — | 本 feature はバックエンド単独 |
| 外部サービス | 該当なし | — | domain 層のため外部通信なし |

## クラス設計（概要）

```mermaid
classDiagram
    class Empire {
        +id: EmpireId
        +name: str
        +rooms: list~RoomRef~
        +agents: list~AgentRef~
        +hire_agent(agent_ref) Empire
        +establish_room(room_ref) Empire
        +archive_room(room_id) Empire
    }
    class RoomRef {
        +room_id: RoomId
        +name: str
        +archived: bool
    }
    class AgentRef {
        +agent_id: AgentId
        +name: str
        +role: Role
    }
    class EmpireInvariantViolation {
        +message: str
        +detail: dict
    }

    Empire "1" *-- "N" RoomRef : owns refs
    Empire "1" *-- "N" AgentRef : owns refs
    Empire ..> EmpireInvariantViolation : raises on violation
```

**凝集のポイント**:
- Empire は `rooms` / `agents` の参照リストの整合性に閉じる責務。Room / Agent の実体は別 Aggregate（参照のみ保持）
- `RoomRef` / `AgentRef` は frozen VO で構造的等価判定。Empire 自身も frozen（Pydantic v2 `model_config.frozen=True`）
- 状態変更ふるまい（`hire_agent` / `establish_room` / `archive_room`）は **新しい Empire を返す**（不変モデル）。呼び出し側は戻り値を受け取って参照を差し替える

## 処理フロー

### ユースケース 1: Empire 構築

1. application 層が `Empire(id=..., name=...)` を呼び出す
2. 入力バリデーション（型・必須・名前長範囲、業務ルール R1-1）を実施
3. 不変条件検査（業務ルール R1-1〜3, R1-6）を実施。初期は採用 / 設立リストが空のため重複・容量は自動成立
4. valid なら Empire インスタンスを返す。違反なら `EmpireInvariantViolation` を raise

### ユースケース 2: Agent 採用（hire_agent）

1. application 層が `empire.hire_agent(agent_ref)` を呼び出す
2. pre-validate 方式で「既採用一覧に追加された仮 Empire」を再構築（実装手順は [`detailed-design.md §確定 A`](detailed-design.md)）
3. 再構築の過程で不変条件検査が走り、`agent_id` の重複（業務ルール R1-2）と容量上限（R1-6）を検査
4. 通過時のみ仮 Empire を返す。違反なら `EmpireInvariantViolation` を raise（元 Empire は不変なので「ロールバック」不要）

### ユースケース 3: Room 設立（establish_room）

ユースケース 2 と同手順。`rooms` リストに対する pre-validate。

### ユースケース 4: Room アーカイブ（archive_room）

1. application 層が `empire.archive_room(room_id)` を呼び出す
2. 既設立一覧で `room_id` 一致する RoomRef を線形探索（[`detailed-design.md §確定 D`](detailed-design.md)）
3. 見つからない場合は `EmpireInvariantViolation` を raise（MSG-EM-004）
4. 見つかった場合は pre-validate 方式で対象 RoomRef の `archived=True` に置換した仮 Empire を再構築（[`detailed-design.md §確定 A`](detailed-design.md)）
5. 仮 Empire の不変条件検査を通過したら返す

## シーケンス図

```mermaid
sequenceDiagram
    participant App as Application Service
    participant Empire as Empire Aggregate
    participant Validator as model_validator

    App->>Empire: hire_agent(agent_ref)
    Empire->>Empire: pre-validate 方式で仮 Empire を再構築
    Empire->>Validator: 業務ルール R1-2（重複） / R1-6（容量）を検査
    alt 不変条件 OK
        Validator-->>Empire: pass
        Empire-->>App: new Empire instance
    else 業務ルール違反
        Validator-->>Empire: raise EmpireInvariantViolation
        Empire-->>App: exception (original empire unchanged)
    end
```

## アーキテクチャへの影響

- `docs/design/domain-model.md` への変更: なし（凍結済み設計に従う実装のみ）
- `docs/design/tech-stack.md` への変更: なし
- 既存 feature への波及: `dev-workflow` 以外まだ存在しないため波及なし。ただし後続 `feature/agent` / `feature/workflow` / `feature/room` は Empire を参照しないため影響なし（Empire 側が他 Aggregate の参照型を持つ非対称構造）

## 外部連携

該当なし — 理由: domain 層のみのため外部システムへの通信は発生しない。

| 連携先 | 目的 | プロトコル | 認証 | タイムアウト / リトライ |
|-------|------|----------|-----|--------------------|
| 該当なし | — | — | — | — |

## UX 設計

該当なし — 理由: domain 層のため UI は持たない。Empire の UI は `feature/empire-ui`（Phase 2 以降）で扱う。

| シナリオ | 期待される挙動 |
|---------|------------|
| 該当なし | — |

**アクセシビリティ方針**: 該当なし（UI なし）。

## セキュリティ設計

### 脅威モデル

本 feature は domain 層のため、ほぼすべての攻撃面は HTTP API レイヤ / 添付配信レイヤで対処される（[`docs/design/threat-model.md`](../../../design/threat-model.md) 参照）。本 feature 範囲では以下の 2 件に絞る。

| 想定攻撃者 | 攻撃経路 | 保護資産 | 対策 |
|-----------|---------|---------|------|
| **T1: 不正な値での Aggregate 構築（バグ含む）** | application 層からの不正な引数（例: 81 文字の name） | Empire の整合性 | Pydantic v2 のフィールドバリデーション + `model_validator` で Fail Fast。pre-validate 方式で不正状態を一瞬たりとも持たない |
| **T2: 重複参照による DoS / メモリ肥大** | 同一 `agent_id` を繰り返し `hire_agent` する application バグ | Empire のメモリ・整合性 | 不変条件で重複を即拒否（O(N) 線形検査、N ≤ 100 想定で 1ms 未満） |

### OWASP Top 10 対応

| # | カテゴリ | 対応状況 |
|---|---------|---------|
| A01 | Broken Access Control | 該当なし（domain 層に認可境界なし、上位層責務） |
| A02 | Cryptographic Failures | 該当なし（暗号化責務なし） |
| A03 | Injection | 該当なし（domain 層は外部入力を直接扱わない、Pydantic 型強制で間接防御） |
| A04 | Insecure Design | **適用**: pre-validate 方式 + frozen model + `EmpireInvariantViolation` で不正状態の窓を物理的に閉じる |
| A05 | Security Misconfiguration | 該当なし（設定ファイルなし） |
| A06 | Vulnerable Components | Pydantic v2 / pyright を使用、依存監査は CI の `pip-audit` で実施 |
| A07 | Auth Failures | 該当なし（認証は別 feature） |
| A08 | Data Integrity Failures | **適用**: frozen model で不変性を強制、状態変更は新インスタンス生成 |
| A09 | Logging Failures | **適用**: application 層（EmpireService）が Empire 作成・hire_agent・establish_room・archive_room の各操作完了時に audit_log に記録する責務を持つ。domain 層は audit_log を直接出力しない（責務分離、application 層の申し送り事項）|
| A10 | SSRF | 該当なし（外部 URL fetch なし） |

## ER 図

該当なし — 理由: 本 feature は domain 層のみで永続化スキーマは含まない。Empire の永続化は `feature/persistence` で扱う。永続化スキーマの方針は [`docs/design/domain-model.md`](../../../design/domain-model.md) §残課題 を参照。

```mermaid
erDiagram
    EMPIRE {
        string id PK
        string name
    }
```

（参考: 永続化される際の概形のみ。詳細は別 feature で凍結。）

## エラーハンドリング方針

| 例外種別 | 処理方針 | ユーザーへの通知 |
|---------|---------|----------------|
| `EmpireInvariantViolation` | application 層で catch、HTTP API 層で 400 / 409 にマッピング（別 feature） | MSG-EM-001 〜 MSG-EM-005 |
| `pydantic.ValidationError` | Empire 構築時に発生（型不正・必須欠落）。application 層で catch | MSG-EM-001（汎用バリデーションエラー文言） |
| その他の例外 | 握り潰さない、application 層へ伝播。Backend ルートで 500 として記録 | 汎用エラーメッセージ |
