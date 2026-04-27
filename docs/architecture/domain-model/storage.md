# 添付ファイル保存方式とシークレットマスキング

> [`../domain-model.md`](../domain-model.md) の補章。`Deliverable` / `Attachment` の保存方式、ファイル配信時のセキュリティ要件、subprocess 出力に対するシークレットマスキング規則を凍結する。

## Deliverable（Value Object）

| 属性 | 型 | 制約 |
|----|----|----|
| `stage_id` | `StageId` | — |
| `body_markdown` | `str` | 0〜1,000,000 文字。永続化前に [§シークレットマスキング規則](#シークレットマスキング規則確定) を適用 |
| `attachments` | `List[Attachment]` | 添付ファイル参照（後述） |
| `committed_by` | `AgentId` | — |
| `committed_at` | `datetime` | UTC |

## Attachment（Value Object、保存方式の確定）

添付ファイルは **content-addressable filesystem** に保存し、DB には参照メタデータのみ保持する。SQLite BLOB に直接格納しない。

### 属性

| 属性 | 型 | 制約 |
|----|----|----|
| `sha256` | `str`（64 hex 小文字） | コンテンツハッシュ。物理ファイル名と一意対応 |
| `filename` | `str`（後述のサニタイズ規則に準拠） | 表示用ファイル名 |
| `mime_type` | `str` | MIME タイプ（後述ホワイトリスト） |
| `size_bytes` | `int`（≥ 0、≤ 10 MiB） | バイトサイズ |

### 物理配置（確定、絶対パス固定）

`<BAKUFU_DATA_DIR>/attachments/<sha256[0:2]>/<sha256>/<filename_safe>`

| 構成要素 | 既定値 / 決定方式 |
|----|----|
| `BAKUFU_DATA_DIR` | 環境変数 `BAKUFU_DATA_DIR` で明示。未設定時は OS ごとの既定: Linux/macOS は `${XDG_DATA_HOME:-$HOME/.local/share}/bakufu`、Windows は `%LOCALAPPDATA%\bakufu` |
| `<sha256[0:2]>` | sha256 先頭 2 文字（git の object 配置と同型）。1 ディレクトリ内のファイル数を平準化 |
| `<sha256>` | フルハッシュ（小文字 hex 64 文字） |
| `<filename_safe>` | サニタイズ後ファイル名（後述） |

**相対パス（`./bakufu-data/`）は使用禁止**。cwd 依存で実行ディレクトリが変わるとファイルを見失う。Backend 起動時に `BAKUFU_DATA_DIR` を解決し、絶対パスとして保持する。

### filename サニタイズ規則（確定）

ファイル名はディスクに書く前に以下の規則で正規化・検証する。違反時は `AttachmentValidationError` を Fail Fast。

| ルール | 内容 |
|----|----|
| 文字数 | 1〜255 文字（NFC 正規化後の Unicode コードポイント数で判定） |
| Unicode 正規化 | NFC で正規化（合成形に統一） |
| 拒否文字 | `/`, `\`, `\0`（NUL）, ASCII 制御文字（0x00〜0x1F、0x7F）を含むものは拒否 |
| 拒否シーケンス | `..`（連続）、先頭 / 末尾の `.`、先頭 / 末尾の空白、`:` を含むパス（Windows 互換） |
| Windows 予約名 | `CON`, `PRN`, `AUX`, `NUL`, `COM1`〜`COM9`, `LPT1`〜`LPT9`（拡張子有無問わず）を拒否 |
| 経路化禁止 | 結果文字列を `os.path.basename()` した値と一致しない場合は拒否（path traversal の二重防護） |

### MIME タイプ検証（ホワイトリスト方式）

ファイル受領時に `python-magic` 等で **実コンテンツから MIME を判定**し、宣言された `mime_type` と一致するか検証する。一致しない場合は `AttachmentValidationError`。

許可 MIME タイプ（MVP）:

| MIME | 用途 |
|----|----|
| `text/markdown` | Deliverable 本体に近い添付 |
| `text/plain` | テキスト添付 |
| `application/json` | 構造化データ |
| `application/pdf` | レビュー用 PDF |
| `image/png` / `image/jpeg` / `image/webp` | スクリーンショット |
| `application/octet-stream` | 上記以外のバイナリ。配信時は強制ダウンロードのみ |

`text/html` は **拒否**（ブラウザで XSS 確定するため）。`text/csv` も MVP では拒否（Excel formula injection リスク、Phase 2 で対応）。

### サイズ上限

| 種別 | 上限 |
|----|----|
| 単一ファイル | 10 MiB |
| Task あたり総添付 | 100 MiB |
| Empire あたり総ストレージ | 5 GiB（admin CLI で監視） |

上限超過時は `AttachmentValidationError` を Fail Fast。

### 配信時のセキュリティ要件（HTTP API）

添付ファイルを HTTP で配信する際は以下のレスポンスヘッダを **必ず付与**する。

| ヘッダ | 値 | 意図 |
|----|----|----|
| `Content-Disposition` | `attachment; filename*=UTF-8''<RFC5987 encoded>` | ブラウザ内表示を抑止し強制ダウンロード |
| `X-Content-Type-Options` | `nosniff` | ブラウザの MIME sniffing を抑止 |
| `Content-Security-Policy` | `default-src 'none'; sandbox` | 万が一表示されても active content を実行させない |
| `Cache-Control` | `private, max-age=0, must-revalidate` | 共有キャッシュへの混入を抑止 |
| `X-Frame-Options` | `DENY` | iframe 経由の clickjacking 抑止 |

`text/html` 等のリスク MIME は受領時に拒否されているため配信ロジックに到達しないが、**配信側でも改めて allow list 検証**する（多層防御）。

### snapshot 凍結方式（ExternalReviewGate 用、確定）

`ExternalReviewGate.deliverable_snapshot` は Gate 生成時に Deliverable を **VO として inline コピー**する。具体的には：

- `body_markdown`: 文字列として Gate row にコピー保持（snapshot として独立、マスキング適用済みの本文）
- `attachments`: `Attachment` VO のリストを Gate row に inline コピー（`sha256` / `filename` / `mime_type` / `size_bytes`）
- 物理ファイルは content-addressable のため**コピーしない**。sha256 が同一なら同じ物理ファイルを Deliverable と Gate snapshot の両方が参照
- Deliverable 側で添付が差し替えられても sha256 が異なる別ファイルとなり、Gate snapshot の sha256 は変わらない（snapshot の不変性が物理層で保証）

### 孤児ファイル GC（確定、誤削除防止策つき）

| トリガ | 対象 | 動作 |
|------|------|------|
| Backend 起動時 | `<BAKUFU_DATA_DIR>/attachments/` 配下の全 sha256 | DB（Deliverable + Gate snapshot）の sha256 集合と差分を取り、未参照を削除 |
| 日次バックグラウンドタスク | 同上 | 起動時 GC と同等処理を 24h ごとに実行 |
| Task 削除（CASCADE） | 関連 Deliverable / Gate snapshot の sha256 | 直接削除はせず、参照カウント 0 になった次回 GC で回収（Tx 境界を跨がせない） |

GC は SQLite トランザクション境界外で動く。「DB の参照集合をスナップショットとして読む → ファイル列挙 → 差分削除」の順で実行し、**スナップショット取得後に追加された sha256 ファイルは次回 GC まで残す**（同時実行下で生まれたばかりのファイルを誤削除しないため）。

GC 操作は `audit_log` に `actor='system'` で記録する。

## SQLite BLOB を採用しない理由

| 候補 | 不採用理由 |
|----|----|
| SQLite BLOB に直接格納 | WAL ファイルが肥大化し SQLite 推奨上限（< 1GB blob, < 10TB DB）に容易に到達。ストリーミング配信不能、バックアップ単位がモノリシック |
| filesystem に sha256 なしのファイル名直接保存 | 同名ファイル衝突、snapshot 凍結時に「上書き or 別名」の判断が発生し設計負荷大 |
| filesystem + content-addressable（採用） | 同内容の自然な重複排除、snapshot 凍結が「sha256 参照のコピー」だけで成立、孤児 GC が「DB 未参照の sha256 を削除」で機械的 |

## シークレットマスキング規則（確定）

LLM subprocess の stdout / stderr、Outbox の `payload_json` / `last_error`、Conversation の `body_markdown` 等、**Agent や外部プロセスの生出力を永続化する箇所すべて**で、保存前に以下のマスキングを適用する。

### 適用先（漏れなく）

| 永続化先 | 適用必須 |
|---------|----|
| `Conversation.messages[].body_markdown`（特に `speaker_kind=SYSTEM` の subprocess 出力） | ✓ |
| `Deliverable.body_markdown` | ✓ |
| `domain_event_outbox.payload_json` | ✓ |
| `domain_event_outbox.last_error` | ✓ |
| `audit_log.args_json` / `audit_log.error_text` | ✓ |
| `Task.last_error`（BLOCKED 時の保存欄） | ✓ |
| `Persona.prompt_body`（Agent VO の一部、Repository 永続化前に適用） | ✓ |
| `PromptKit.prefix_markdown`（Room VO の一部、Repository 永続化前に適用 — [`feature/room`](../../features/room/detailed-design.md) §確定 G） | ✓ |
| 構造化ログ（ファイル / stdout） | ✓ |

### マスキング対象パターン

| 種別 | 検出方式 | 置換後 |
|----|----|----|
| 既知環境変数の値 | 起動時に `os.environ` から `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GH_TOKEN` / `GITHUB_TOKEN` / `OAUTH_CLIENT_SECRET` / `BAKUFU_DB_KEY` 等の値（長さ 8 以上のもののみ）をパターン辞書に登録し、出力文字列内で完全一致を伏字化 | `<REDACTED:ENV:ANTHROPIC_API_KEY>` |
| Anthropic API key 形式 | 正規表現 `sk-ant-(api03-)?[A-Za-z0-9_\-]{40,}` | `<REDACTED:ANTHROPIC_KEY>` |
| OpenAI API key 形式 | 正規表現 `sk-[A-Za-z0-9]{20,}`（`sk-ant-` を除く） | `<REDACTED:OPENAI_KEY>` |
| GitHub PAT | 正規表現 `(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}` | `<REDACTED:GITHUB_PAT>` |
| GitHub fine-grained PAT | 正規表現 `github_pat_[A-Za-z0-9_]{82,}` | `<REDACTED:GITHUB_PAT>` |
| AWS Access Key | 正規表現 `AKIA[0-9A-Z]{16}` | `<REDACTED:AWS_ACCESS_KEY>` |
| AWS Secret | 正規表現 `aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}` | `<REDACTED:AWS_SECRET>` |
| Slack token | 正規表現 `xox[baprs]-[A-Za-z0-9-]{10,}` | `<REDACTED:SLACK_TOKEN>` |
| Discord bot token | 正規表現 `[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}` | `<REDACTED:DISCORD_TOKEN>` |
| Bearer / Authorization ヘッダ | 正規表現 `(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+` | `\1<REDACTED:BEARER>` |
| OS ユーザーホームパス | OS から検出した `$HOME` ディレクトリ絶対パス | `<HOME>` |

### 適用順序

1. 環境変数値の伏字化（最も具体的）
2. 正規表現パターンマッチ
3. ホームパス置換

マスキング処理は `infrastructure/security/masking.py` に集約し、**永続化前の単一ゲートウェイ**として呼び出す（責務散在防止）。

### 配線方式（強制ゲートウェイ化）

`feature/persistence-foundation` の §確定 R1-D（要求分析）/ §確定 B（詳細設計）で凍結したとおり、配線は **SQLAlchemy TypeDecorator (`MaskedJSONEncoded` / `MaskedText`) の `process_bind_param`** で行う。Core / ORM 両経路（`session.add()` 経由と `session.execute(insert(table).values(...))` 経由）で確実に発火し、**呼び忘れ経路ゼロ**の物理保証になる。

旧設計の `event.listens_for(target, 'before_insert')` 方式は PR #23 BUG-PF-001 で**反転却下**された（Core `insert(table).values({...})` の inline values は ORM mapper を経由せず listener が発火しないため、raw SQL 経路で生 secret が永続化される脱出経路が残る — TC-IT-PF-020 旧 xfail strict=True で確認、リーナス commit `4b882bf` で TypeDecorator 方式に切替えて TC-IT-PF-020 PASSED で物理保証）。詳細経緯は [`feature/persistence-foundation/requirements-analysis.md`](../../features/persistence-foundation/requirements-analysis.md) §確定 R1-D 参照。

「属性追加時の漏れ」リスク（TypeDecorator 採用の唯一のリスク）は **CI 三層防衛**で物理保証する: (1) CI grep guard（masking 対象カラム名の宣言行に `Masked*` 型必須）、(2) アーキテクチャテスト（SQLAlchemy metadata からカラム型を assert）、(3) 本 §逆引き表の運用ルール。

### 適用先 → 配線箇所の逆引き表（Norman 指摘 R6 対応）

後続実装者がカラム名から TypeDecorator 種別を素早く辿れるようにする逆引き表。**新規 Aggregate Repository PR は本表に行を追加する責務**（テンプレートとしての真実源）。

| カラム / フィールド | テーブル | 配線モジュール（後続 PR） | TypeDecorator 種別 | 担当 PR |
|---|---|---|---|---|
| `Conversation.messages[].body_markdown` | `conversation_messages` | `infrastructure/persistence/sqlite/tables/conversation_messages.py` | `MaskedText` | `feature/conversation-repository`（後続） |
| `Deliverable.body_markdown` | `deliverables` | `tables/deliverables.py` | `MaskedText` | `feature/task-repository`（後続） |
| `domain_event_outbox.payload_json` | `domain_event_outbox` | `tables/outbox.py` | `MaskedJSONEncoded` | **本 PR（`feature/persistence-foundation`）** |
| `domain_event_outbox.last_error` | `domain_event_outbox` | `tables/outbox.py` | `MaskedText` | **本 PR** |
| `audit_log.args_json` | `audit_log` | `tables/audit_log.py` | `MaskedJSONEncoded` | **本 PR** |
| `audit_log.error_text` | `audit_log` | `tables/audit_log.py` | `MaskedText` | **本 PR** |
| `Task.last_error` | `tasks` | `tables/tasks.py` | `MaskedText` | `feature/task-repository`（後続） |
| `Persona.prompt_body` | `agents` | `tables/agents.py` | `MaskedText` | `feature/agent-repository`（Issue #32、**Schneier 申し送り #3 実適用済み**、persistence-foundation #23 で hook 構造提供 → 本 PR で配線完了） |
| `PromptKit.prefix_markdown` | `rooms` | `tables/rooms.py` | `MaskedText` | `feature/room-repository`（後続） |
| `bakufu_pid_registry.cmd` | `bakufu_pid_registry` | `tables/pid_registry.py` | `MaskedText` | **本 PR** |
| 構造化ログ | （ファイル） | `infrastructure/logging/structured.py` | log filter（TypeDecorator 対象外、ログ層で `MaskingGateway.mask()` 呼び出し） | `feature/logging` |
| **Empire 関連カラム（`empires` / `empire_room_refs` / `empire_agent_refs`）** | 同左 3 テーブル | `infrastructure/persistence/sqlite/repositories/empire_repository.py` + `tables/empires.py` 等 | **masking 対象なし**（`String` / `UUIDStr` / `Boolean` のみ。後続 Repository PR が誤って `MaskedText` を追加しないテンプレート、CI 三層防衛 Layer 1+2 で物理保証） | `feature/empire-repository`（PR #25） |
| `workflow_stages.notify_channels_json` | `workflow_stages` | `infrastructure/persistence/sqlite/tables/workflow_stages.py` | **`MaskedJSONEncoded`** | `feature/workflow-repository`（Issue #31、Schneier 申し送り #6 + workflow §Confirmation G の Repository 経路実適用、Discord webhook token マスキング） |
| **Workflow 残カラム（`workflows` 全カラム / `workflow_transitions` 全カラム / `workflow_stages` の `notify_channels_json` 以外）** | 同左 | `tables/workflows.py` / `tables/workflow_transitions.py` / `tables/workflow_stages.py` | **masking 対象なし**（`UUIDStr` / `String` / `Text` / `JSONEncoded` のみ。`completion_policy_json` は VO の自由記述だが secret 6 種非該当のため `JSONEncoded`、CI Layer 2 で `MaskedJSONEncoded` でないことを arch test で保証） | `feature/workflow-repository`（Issue #31） |
| **Agent 残カラム（`agents` の `prompt_body` 以外 / `agent_providers` 全カラム / `agent_skills` 全カラム）** | 同左 | `tables/agents.py` / `tables/agent_providers.py` / `tables/agent_skills.py` | **masking 対象なし**（`UUIDStr` / `String` / `Boolean` のみ。`agents.prompt_body` 以外のカラムが secret 6 種に該当しないことを CI Layer 2 で arch test で保証、過剰マスキング防止） | `feature/agent-repository`（Issue #32） |

##### 逆引き表の運用ルール

1. **新規カラムの追加**: 該当 Aggregate Repository PR が本表に 1 行追加する責務（型は `MaskedJSONEncoded` / `MaskedText` のいずれか）
2. **削除**: 該当カラムを Aggregate から削除する PR が本表からも削除する責務
3. **TypeDecorator 種別の選択基準**:
   - `MaskedJSONEncoded`: dict / list を JSON エンコードして保存するカラム（`payload_json` / `args_json` 等）
   - `MaskedText`: 文字列を直接保存するカラム（`last_error` / `body_markdown` / `prompt_body` / `prefix_markdown` / `cmd` 等）
4. **未配線カラムの追加禁止**: マスキング対象として本表に載っているカラムが `MaskedJSONEncoded` / `MaskedText` 以外の型で永続化される PR は **CI grep guard で自動却下** + コードレビューでも却下

### 漏洩したらどうするか

万が一マスキングを抜けて secret が DB に保存された場合の手順は [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) §Secret 混入時の緊急対応 と同じだが、追加で以下を行う:

1. SQLite の WAL を含むデータベースファイル（`bakufu.db`, `bakufu.db-wal`, `bakufu.db-shm`）の差し替え
2. 影響を受けた Conversation / Deliverable / Outbox 行を特定し、当該 secret 列を `<REDACTED:LEAKED>` で UPDATE
3. `audit_log` に `actor='security_response'` で記録

## 監査ログ（`audit_log`）

[`value-objects.md`](value-objects.md) §Admin CLI 監査ログ で定義したスキーマに従い、Admin CLI / GC / セキュリティ対応のすべての操作を **追記のみ** で記録する。
