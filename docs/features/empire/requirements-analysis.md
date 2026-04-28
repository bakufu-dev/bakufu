# 要求分析書

> feature: `empire`
> Issue: [#8 feat(empire): Empire Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/8)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Empire

## 人間の要求

> Issue #8:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の一環として **Empire Aggregate Root** を実装する。Empire は bakufu インスタンスの最上位ドメインオブジェクトで、Room / Agent の編成所在を保持するシングルトン Aggregate。

## 背景・目的

### 現状の痛点

1. `backend/src/bakufu/domain/` に Aggregate 実装が一切無い。Phase 0 で凍結したドメインモデルが文書のみで、実コードに落ちていない
2. M1 後段の `room` / `directive` / `task` は Empire への参照（採用済み Agent / 設立済み Room の所在）を前提とする。Empire が無いと並列着手後の合流地点が無い
3. CEO directive 受付の application 層は「どの Empire に紐づくか」を Aggregate 経由で問い合わせる設計のため、Empire Aggregate がなければ起点が無い

### 解決されれば変わること

- M1 後続の `room` / `directive` / `task` Issue が Empire 参照を前提に実装可能になる
- `domain/` 配下に「Aggregate Root + 参照 VO + 不変条件検査」のお手本が 1 件揃い、後続 Aggregate（workflow / agent / room / task / external-review-gate）の実装パターンが固定される
- ユニットテストを通じて Pydantic v2 frozen model + pyright strict + pre-validate の組み合わせが実用に耐えることを検証できる

### ビジネス価値

- bakufu MVP の Vモデル E2E（M7）に至る最短経路の出発点を確保する
- 設計書（`docs/{analysis,requirements,design}/`）と実コードの最初の接続点として、後続 PR がコピーできる「お手本」を提供する

## 議論結果

### 設計担当による採用前提

- Aggregate Root は **Pydantic v2 `BaseModel` + `model_config = ConfigDict(frozen=True)` + `model_validator(mode='after')`** で表現する。`@dataclass(frozen=True)` ではなく Pydantic を採用するのは、後段で OpenAPI スキーマ自動生成（FastAPI）と SQLAlchemy mapper 用 dict 変換を共通化するため
- 不変条件検査は **pre-validate 方式**を厳守する（[`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §`validate()` 呼びタイミングとロールバック方式）。状態変更ふるまいは「変更後の仮想状態を構築 → validate → 通過時のみ自身を置換」の手順
- 参照型 `RoomRef` / `AgentRef` は本 feature で frozen VO として確定する。実体 Aggregate（Room / Agent）は別 feature だが、Empire 内の参照表現は本 feature で凍結する
- シングルトン制約は **application 層責務**。Aggregate 内部では「Empire は 1 件しか作れない」を強制せず、Repository.save() の前に application 層が件数を検査する

### 却下候補と根拠

| 候補 | 却下理由 |
|-----|---------|
| `@dataclass(frozen=True)` で Empire を表現 | OpenAPI スキーマ生成 / FastAPI 統合 / SQLAlchemy 変換を後段で別途書く必要があり、責務が散る。Pydantic v2 の `frozen=True` で同等の不変性が得られる |
| Aggregate 内部でシングルトン制約を強制 | Aggregate Root は単一インスタンスの整合性に閉じる責務。「複数生成されたかどうか」は Repository 横断の集合知識で、application 層責務 |
| Empire を Singleton パターン（クラスレベルキャッシュ）で実装 | グローバル状態を持ち込みテストの並列化を破壊する。インスタンスを引数で渡す DI パターンと相容れない |
| `RoomRef` / `AgentRef` の代わりに `RoomId` / `AgentId` だけ持つ | 表示用の `name` を毎回 Repository から引く必要があり UI の N+1 問題を生む。参照型に「表示用キャッシュ」として name を含める |

### 重要な選定確定（レビュー指摘 R1 応答）

#### 確定 R1-A: pre-validate 方式の具体実装

`hire_agent` / `establish_room` / `archive_room` は以下の手順を厳守：

1. 引数バリデーション（型・必須・長さ）を Pydantic v2 で先に通す
2. 変更後の `agents` / `rooms` リストを **新しいリストとして仮構築**
3. `self.model_dump(mode='python')` で現状を dict 化し、該当キーを新リストに差し替え
4. `Empire.model_validate(updated_dict)` で仮 Empire を再構築
5. 再構築過程で `model_validator(mode='after')` が走り、不変条件を検査
6. OK なら新 Empire を返す（Pydantic 不変モデルなので呼び出し側が参照を差し替える）、NG なら raise
7. 失敗時は元の Empire は変更されていないため「ロールバック」が要らない

`model_copy(update=...)` は `validate=False` 既定（Pydantic v2 の仕様）で `model_validator(mode='after')` を再実行しないため**採用しない**。`model_validate(...)` 経由で再構築する。詳細な根拠は [`detailed-design.md`](detailed-design.md) §確定 A。

#### 確定 R1-B: シングルトン強制の application 層実装

application 層 `EmpireService.create()`（別 Issue で実装）の責務:

1. `EmpireRepository.count()` を呼ぶ
2. `count > 0` なら `EmpireAlreadyExistsError` を raise（Fail Fast）
3. 0 件なら新規 Empire を構築・保存

ドメイン層の Empire はこの呼び出し前提で「自身ではシングルトン強制しない」契約。

## ペルソナ

| ペルソナ名 | 役割 | 技術レベル | 利用文脈 | 達成したいゴール |
|-----------|------|-----------|---------|----------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | GitHub / Docker / CLI 日常使用 | UI から Empire を 1 つ建てて、Agent 採用・Room 設立を編成する | 数クリックで Empire を構築、Agent 採用 / Room 設立を直感的に操作 |

bakufu システム全体のペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。本 feature は domain 層のため Aggregate-C 系（AI Agent）には直接触れない。

## 前提条件・制約

| 区分 | 内容 |
|-----|------|
| 既存技術スタック | Python 3.12+ / Pydantic v2 / pyright strict / pytest（[`tech-stack.md`](../../design/tech-stack.md)）|
| 既存 CI | lint / typecheck / test-backend / audit（pip-audit）|
| 既存ブランチ戦略 | GitFlow（CONTRIBUTING.md §ブランチ戦略） |
| コミット規約 | Conventional Commits |
| ライセンス | MIT |
| ネットワーク | 該当なし — Empire は domain 層のため外部通信なし |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |

## 機能一覧

| 機能ID | 機能名 | 概要 | 優先度 |
|--------|-------|------|--------|
| REQ-EM-001 | Empire 構築 | コンストラクタで `id` / `name` を受け取り `rooms=[]` / `agents=[]` で初期化。pre-validate 通過後のみ返す | 必須 |
| REQ-EM-002 | Agent 採用 | `hire_agent(agent_ref)` で `agents` リストに `AgentRef` を追加。重複 `agent_id` は不変条件違反 | 必須 |
| REQ-EM-003 | Room 設立 | `establish_room(room_ref)` で `rooms` リストに `RoomRef` を追加。重複 `room_id` は不変条件違反 | 必須 |
| REQ-EM-004 | Room アーカイブ | `archive_room(room_id)` で対象 RoomRef の `archived=True` に遷移。物理削除はしない | 必須 |
| REQ-EM-005 | 不変条件検査 | コンストラクタ末尾と状態変更ふるまい末尾で実行。違反時は `EmpireInvariantViolation` を raise | 必須 |

## Sub-issue 分割計画

本 Issue は単一 Aggregate に閉じる粒度のため Sub-issue 分割は不要。1 PR で 4 設計書 + 実装 + ユニットテストを完結させる。

| Sub-issue 名 | 紐付く REQ | スコープ | 依存関係 |
|------------|-----------|---------|---------|
| 単一 PR | REQ-EM-001〜005 | Empire Aggregate Root + RoomRef / AgentRef VO + ユニットテスト | chore #7 マージ済み（前提充足） |

## 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 不変条件検査は O(N+M)（N=rooms 件数、M=agents 件数）。MVP の想定規模 N+M ≤ 100 で 1ms 未満を目標 |
| 可用性 | 該当なし — domain 層はインメモリのみ。永続化は `feature/persistence` で扱う |
| 保守性 | pyright strict pass / ruff 警告ゼロ / カバレッジ 80% 以上 |
| 可搬性 | 純 Python のみ。OS / ファイルシステム依存なし |
| セキュリティ | domain 層は外部入力を直接扱わない。境界バリデーション（HTTP API レベル）は別 feature。pre-validate で不正状態を Aggregate に持ち込ませない（Fail Fast） |

## 受入基準

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | `Empire(id, name)` で valid な Empire が構築される | TC-UT-EM-001（コンストラクタ正常系） |
| 2 | name が 0 文字 / 81 文字以上で `EmpireInvariantViolation` | TC-UT-EM-002（境界値） |
| 3 | `hire_agent(agent_ref)` で `agents` に追加される | TC-UT-EM-003（正常系） |
| 4 | 同一 `agent_id` の `hire_agent` は `EmpireInvariantViolation`、Empire 状態は変化しない | TC-UT-EM-004（pre-validate 検証） |
| 5 | `establish_room(room_ref)` で `rooms` に追加される | TC-UT-EM-005 |
| 6 | 同一 `room_id` の `establish_room` は `EmpireInvariantViolation`、Empire 状態は変化しない | TC-UT-EM-006 |
| 7 | `archive_room(room_id)` で対象 RoomRef の `archived=True`、`rooms` リストから削除されない | TC-UT-EM-007 |
| 8 | 存在しない `room_id` の `archive_room` は `EmpireInvariantViolation` | TC-UT-EM-008 |
| 9 | `pyright --strict` および `ruff check` がエラーゼロ | CI lint / typecheck ジョブ |
| 10 | カバレッジが `domain/empire.py` で 80% 以上 | pytest --cov |

## 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Empire.name | bakufu インスタンスの表示名（例: "山田の幕府"） | 低（CEO 任意の文字列、機密性なし） |
| RoomRef / AgentRef | Room / Agent の参照（id + 表示用 name） | 低 |
