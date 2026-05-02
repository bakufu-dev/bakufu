# 業務仕様書（feature-spec）— websocket-broadcast

> feature: `websocket-broadcast`（業務概念単位）
> sub-features: [`domain/`](domain/) / [`http-api/`](http-api/)（Issue #159 で実装）
> 関連 Issue: [#157 M4: WebSocket broadcast — Domain Eventのリアルタイム配信基盤](https://github.com/bakufu-dev/bakufu/issues/157)
> 凍結済み設計: [`docs/design/architecture.md`](../../design/architecture.md) §EventBus / [`docs/design/tech-stack.md`](../../design/tech-stack.md) §WebSocket / [`docs/design/threat-model.md`](../../design/threat-model.md) §A3

## 本書の役割

本書は **websocket-broadcast という業務概念全体の業務仕様** を凍結する。プロジェクト全体の要求分析（[`docs/analysis/`](../../analysis/)）を Domain Event リアルタイム配信という観点で具体化し、ペルソナから見て **観察可能な業務ふるまい** を実装レイヤーに依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない。

**書くこと**:
- ペルソナが websocket-broadcast で達成できるようになる行為（ユースケース UC-WSB-NNN）
- 業務ルール（メッセージ形式・EventBus 契約・接続管理・WebSocket セキュリティ等、全 sub-feature を貫く凍結）
- 観察可能な事象としての受入基準（システムテストの真実源）

**書かないこと**（後段の設計書・別ディレクトリへ追い出す）:
- EventBus の具体的な実装クラス設計 → `domain/basic-design.md`
- WebSocket endpoint の配線詳細 → `http-api/basic-design.md`（Issue #159 で作成）
- クラス属性・型定義 → `domain/detailed-design.md`
- pyright strict / カバレッジ閾値 → §10 開発者品質基準

## 1. この feature の位置付け

websocket-broadcast は **bakufu MVP M4 の通信基盤** として定義する。M3 HTTP API により CRUD 操作の REST 経路は確立済みだが、非同期の状態変化（Task 状態遷移 / Gate 承認要求等）を UI にプッシュする手段がない。本 feature はその欠落を埋め、M6（ExternalReviewGate UI）と M7（Vモデル E2E）の前提となる。

業務的なライフサイクルは2つの実装レイヤーにまたがる:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain + application + infrastructure | [`domain/`](domain/) | Domain Event 基盤（DomainEvent / EventBus Port / InMemoryEventBus）— **Issue #158** |
| interfaces/http | [`http-api/`](http-api/) | WebSocket endpoint + ConnectionManager — **Issue #159** |

**設計上の制約**: `domain` sub-feature（Issue #158）の完了が `http-api` sub-feature（Issue #159）の着手前提である。

## 2. 人間の要求

> Issue #157:
>
> `backend/interfaces/http/` に WebSocket エンドポイントを実装し、Domain Event をクライアント UI にリアルタイム配信する基盤を構築する。MVP 目標「UI から bakufu へ指示 → 結果確認」の通信レイヤー。

## 3. 背景・痛点

### 現状の痛点

1. M3 HTTP API が完了しているが、**Task の状態遷移・Agent のステータス変化・Gate の承認要求はポーリングなしに UI に届かない**。UI が全状態を知るには定期的に全エンドポイントを叩く必要があり、遅延と無駄なリクエストが発生する
2. Domain Event が domain 層に存在しない。Aggregate が状態変化しても「何が起きたか」を他レイヤーに通知する仕組みがなく、ApplicationService が状態変化を呼び出し元に返すことしかできない（工程1調査で判明）
3. ExternalReviewGate の「承認を求める」Discord 通知は実装済みだが、**bakufu UI 上でのリアルタイム表示経路がない**

### 解決されれば変わること

- CEO が bakufu UI を開いたまま放置していると、Task が自動進行する様子がリアルタイムで見える
- ExternalReviewGate の承認要求がブラウザに即時プッシュされ、Discord を見なくても承認操作ができる
- Agent の実行状態（idle / running / blocked）が UI に反映される

### ビジネス価値

- **「UI から bakufu に指示 → 結果確認」MVP ゴールの通信レイヤーを確立する**。本 feature なしに M6 UI は画面更新のためのポーリングを自前実装しなければならず、クライアントコードが複雑化する
- EventBus パターンの導入により、将来の Discord 通知 / メール通知 / 外部 Webhook など通知チャネルを EventBus を購読するだけで追加できる（拡張性の確保）

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|---|---|---|---|
| CEO | bakufu のオーナー・運用者 | 直接 | bakufu UI でタスクの進行状況・Gate 承認要求をリアルタイムで確認したい |
| UI 開発者（AI エージェント） | M6 UI の実装者 | 直接 | `useWebSocket` hook 経由で Domain Event を購読し、画面を自動更新したい |

プロジェクト全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|---|---|---|---|---|
| UC-WSB-001 | CEO | Task の状態が変化したとき（PENDING → IN_PROGRESS 等）、UI で即座に確認したい | 必須 | domain / http-api |
| UC-WSB-002 | CEO | ExternalReviewGate が PENDING（承認待ち）になったとき、UI に通知を受け取りたい | 必須 | domain / http-api |
| UC-WSB-003 | CEO | Agent のステータス（idle / running / blocked）が変化したとき、UI で確認したい | 必須 | domain / http-api |
| UC-WSB-004 | CEO | Directive が完了（DONE / FAILED）したとき、UI で確認したい | 必須 | domain / http-api |
| UC-WSB-005 | UI 開発者 | `ws://localhost:8000/ws` に WebSocket 接続し、全 Domain Event を JSON で受け取りたい | 必須 | http-api |

## 6. スコープ

### In Scope

- `DomainEvent` 抽象基底クラスの定義（domain 層）
- MVP 対象の Domain Event クラス定義（Task / ExternalReviewGate / Agent / Directive）
- `EventBusPort` インターフェース（application/ports）
- `InMemoryEventBus` 実装（infrastructure）
- 各 ApplicationService への `event_bus.publish()` 統合
- `GET /ws` WebSocket エンドポイント（interfaces/http）
- `ConnectionManager`（接続管理・ブロードキャスト）
- `EventBus → WebSocket bridge`
- `app.py` lifespan への ConnectionManager / EventBus 統合

### Out of Scope（参照）

- Redis / Kafka 等の分散 EventBus 実装 → Phase 2（`InMemoryEventBus` で MVP は十分）
- WebSocket 認証（JWT / Cookie）→ Phase 2（loopback バインド前提のため MVP では不要。R1-6 参照）
- フロントエンド React hook（`useWebSocket`）→ M6 UI Issue（Issue #159 完了後）
- Room チャット・Conversation ログのリアルタイム表示 → Phase 2
- Server-Sent Events（SSE）代替実装 → 不採用（WebSocket で双方向通信の拡張余地を残す）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: WebSocket エンドポイントは `GET /ws` の単一エンドポイントとする。MVP では全 Domain Event を1チャネルで配信する

**理由**: トピック別マルチチャネル（`/ws/tasks`, `/ws/gates` 等）は接続管理が複雑になる。MVP の接続数は1人の CEO が1ブラウザタブで使う想定であり、単一チャネルで十分。Phase 2 でフィルタリングが必要になった場合はサブスクリプション方式に拡張する。

### 確定 R1-2: WebSocket メッセージ形式は以下の JSON 構造を固定フォーマットとする

フォーマット: `{"event_type": "<aggregate>.<action>", "aggregate_id": "<UUID>", "aggregate_type": "<str>", "occurred_at": "<ISO8601 UTC>", "payload": {...}}`

**理由**: クライアントが `event_type` でハンドラを切り替えられるよう構造化する。`occurred_at` は必須（UI 側でイベントの順序・鮮度を判断するため）。`payload` は event_type によって異なる追加データを格納する。

### 確定 R1-3: EventBus は ApplicationService が `publish()` を呼ぶ単方向通知パターンとする。Domain 層は EventBus を直接参照しない

**理由**: DDD のクリーン設計。Domain Aggregate が EventBus（application/infrastructure 層の概念）に依存すると依存方向が逆転し、`domain → application` の禁止違反となる。ApplicationService が Aggregate の操作後に Domain Event を生成して `publish()` する責務を持つ。

### 確定 R1-4: InMemoryEventBus はプロセス内の購読者リストに対してブロードキャストする。MVP では永続化しない

**理由**: 外部 MQ（Redis / Kafka）はローカルファースト MVP には過剰。インプロセス実装でレイテンシも最小化。EventBus のイベント損失は許容（再接続時に UI が最新状態を REST API で取得する設計）。

### 確定 R1-5: WebSocket 接続は1クライアントの切断が他クライアントのブロードキャストを妨げない。ConnectionManager は切断時に該当接続を削除し、残存接続へのブロードキャストを継続する

**理由**: bakufu は将来マルチタブ操作が想定される。1接続のネットワーク障害で他タブのリアルタイム表示が止まるのは許容できない。FastAPI の WebSocket は切断時に `WebSocketDisconnect` を発火するので `try/except` で安全に削除できる。

### 確定 R1-6: WebSocket 接続に認証は要求しない（MVP）

**理由**: bakufu は `127.0.0.1` バインド（loopback 専用）で稼働する。外部からの接続は物理的に不可能（threat-model.md §A3 の境界設計による）。MVP でシングルユーザー（CEO）前提のため、接続元確認は不要。Phase 2 でマルチユーザー化する場合はトークン認証を追加する（Q-OPEN-1 参照）。

## 8. 制約・前提

| 区分 | 内容 |
|---|---|
| 既存運用規約 | GitFlow / Conventional Commits / CODEOWNERS 保護 |
| ライセンス | MIT |
| 対象 OS | Linux / macOS（開発）|
| 依存 feature | `http-api-foundation`（FastAPI app + lifespan + DI ファクトリ）|
| WebSocket ライブラリ | `uvicorn[standard]` に同梱の `websockets`。追加の依存パッケージ不要（pyproject.toml 変更なし）|
| Python バージョン | 3.12+ |
| EventBus 永続化 | なし（MVP）。イベント損失は許容設計 |
| 同時接続数 | MVP: 1〜数接続（シングルユーザー想定）|

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|---|---|---|
| 1 | `ws://localhost:8000/ws` に WebSocket 接続できる | UC-WSB-005 | TC-ST-WSB-001 |
| 2 | Task の状態遷移（REST API 経由）後、接続中クライアントに `{"event_type": "task.state_changed", ...}` JSON が届く | UC-WSB-001 | TC-ST-WSB-002 |
| 3 | ExternalReviewGate が PENDING になったとき、接続中クライアントに `{"event_type": "external_review_gate.state_changed", ...}` JSON が届く | UC-WSB-002 | TC-ST-WSB-003 |
| 4 | Agent のステータス変化後、接続中クライアントに `{"event_type": "agent.status_changed", ...}` JSON が届く | UC-WSB-003 | TC-ST-WSB-004 |
| 5 | クライアント切断後、残存接続へのブロードキャストが継続する（切断が他クライアントをブロックしない） | R1-5 | TC-ST-WSB-005 |
| 6 | Domain Event 発行から WebSocket クライアント受信まで p95 2 秒以内（ローカル実行環境） | （非機能）| TC-ST-WSB-006 |

## 10. 開発者品質基準（CI 担保、業務要求ではない）

| 基準 ID | 名称 | 内容 |
|---|---|---|
| Q-1 | 型検査 / lint エラーゼロ | `pyright --strict` + `ruff check` が CI でエラーゼロであること |
| Q-2 | カバレッジ | domain / application/ports / infrastructure 実装ファイル群 90% 以上（CI `pytest --cov` で担保）|
| Q-3 | 依存方向の物理保証 | domain 層から application / infrastructure への import ゼロ。`EventBusPort` は `application/ports/` にのみ配置（CI の import 検査で物理確認）|

## 11. 開放論点 (Open Questions)

| # | 論点 | 起票先 |
|---|---|---|
| Q-OPEN-1 | Phase 2 でマルチユーザー対応時、WebSocket 接続の認証方式（Bearer token in query param / `Sec-WebSocket-Protocol` ヘッダ）はどれを採用するか | Phase 2 Issue |
| Q-OPEN-2 | イベント順序保証が必要になった場合（`event_id` によるクライアント側順序制御）の設計 | Phase 2 Issue |
| Q-OPEN-3 | Room スコープのイベントフィルタリング（特定 Room の Task 変化のみ受信）の設計 | Phase 2 Issue |

## 12. Sub-issue 分割計画

| Sub-issue 名 | 紐付く UC | スコープ | 依存関係 |
|---|---|---|---|
| **A**: domain（Issue #158） | UC-WSB-001〜004 | DomainEvent / EventBusPort / InMemoryEventBus / ApplicationService 統合 | `http-api-foundation` に依存 |
| **B**: http-api（Issue #159） | UC-WSB-005 | ConnectionManager / `GET /ws` / EventBus→WebSocket bridge / lifespan 統合 | Issue #158 完了後に着手 |

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|---|---|---|
| Domain Event payload | Aggregate 状態変化の内容（status 文字列 / Aggregate ID 等）| 中（内容による）|
| WebSocket メッセージ | JSON 形式の Domain Event（シークレット非含有。masking gateway 通過後の状態データのみ）| 低 |
| 接続情報 | クライアントの WebSocket 接続オブジェクト（インメモリ、プロセス終了で消滅）| 低 |

## 14. 非機能要求

| 区分 | 要求 |
|---|---|
| パフォーマンス | Domain Event 発行から WebSocket クライアント受信まで p95 2 秒以内（ローカル実行環境）|
| 可用性 | 単一クライアント切断で他クライアントへの配信が中断しないこと（R1-5）|
| 可搬性 | Python 3.12 / Linux / macOS。追加の外部サービス不要（インプロセス EventBus）|
| セキュリティ | WebSocket は loopback バインド前提（127.0.0.1）。Origin 検証は `ws://localhost:8000` のみ許可（R1-6、[`docs/design/threat-model.md`](../../design/threat-model.md) §A3）|
