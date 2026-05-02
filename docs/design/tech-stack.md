# bakufu 技術スタック

bakufu の技術選定を採用 / 不採用候補 / 根拠の 3 列で固定する。実装は本書に従う。

## 採用スタック

### Backend

| カテゴリ | 採用 | 用途 / 根拠 |
|----|----|----|
| 言語 | Python 3.12+ | 型ヒント完備、`pyright` strict、ai-team の `claude_code_client.py` 等の資産を再利用しやすい |
| Web フレームワーク | **FastAPI** | Pydantic 統合、OpenAPI 自動生成、WebSocket ネイティブ、async 対応 |
| ORM | **SQLAlchemy 2.x** | DDD と相性が良い（Domain と Mapper を分離可能）、async 対応、SQLite/Postgres 両対応 |
| バリデーション | **Pydantic v2** | FastAPI 統合、frozen model で Value Object 表現 |
| データベース | **SQLite 3.50.2+**（WAL モード） | ローカルファースト、ゼロコンフィグ、後段で Postgres への切替可能。BLOB は使わず、添付ファイルは content-addressable filesystem に分離（`domain-model.md` §Attachment 参照）。**CVE-2025-6965（メモリ破壊）** 対策で 3.50.2 未満を ops 要件から除外（本システムは SQLAlchemy ORM のみで SQL を発行するため攻撃前提が物理遮断されるが、ops 依存ライブラリのバージョン拘束として明示） |
| 添付ストレージ | **ローカル filesystem**（`./bakufu-data/attachments/<sha256[0:2]>/<sha256>/`） | content-addressable で重複排除と snapshot 凍結が物理層で成立。SQLite BLOB は WAL 肥大の懸念で不採用 |
| Outbox / Dispatcher | **SQLite テーブル + asyncio 常駐タスク** | Domain Event の at-least-once 配送を MVP で実現。外部 MQ（Redis/RabbitMQ）はローカルファースト要件で不採用（YAGNI）。詳細は `domain-model.md` §Domain Event 補償設計 |
| マイグレーション | **Alembic** | SQLAlchemy 公式、シンプル |
| パッケージ管理 | **uv** | Astral 製、極めて高速、`uv.lock` で再現性、`uv tool install` で開発ツール導入 |
| 非同期ランタイム | **uvicorn** | FastAPI 標準、reload 対応 |
| テスト | **pytest** + **pytest-asyncio** + **httpx** | FastAPI 公式推奨、async サポート、TestClient で E2E |
| 型チェック | **pyright** | mypy より高速、strict mode、IDE 統合（VS Code Pylance） |
| Lint + Format | **ruff** | Astral 製、桁違いに高速、flake8 + black + isort 互換 |
| 依存監査 | **pip-audit** | PyPA 公式、OSV/PyPI advisory データベース照合 |

### Frontend

| カテゴリ | 採用 | 用途 / 根拠 |
|----|----|----|
| 言語 | TypeScript 5+ | strict mode、型安全な UI 実装 |
| ビルドツール | **Vite 7** | 開発サーバ高速、HMR、ESM ネイティブ |
| UI フレームワーク | **React 19** | 業界標準、Suspense / Server Components 対応 |
| ルーティング | **React Router 7** | data router、loader / action パターン |
| スタイル | **Tailwind CSS 4** | ユーティリティファースト、Vite 統合 |
| 状態管理 | **Zustand** + React Query / TanStack Query | DDD のドメイン層と分離した薄い状態管理。サーバ状態は React Query |
| WebSocket | ネイティブ `WebSocket` API + 薄いラッパ | リアルタイムイベント受信 |
| ピクセルアート（Phase 2） | **PixiJS 8** | ClawEmpire 完全寄せ、オフィス可視化 |
| パッケージ管理 | **pnpm** 9+ | 高速、ハードリンクで省ディスク、corepack 経由で導入 |
| Lint + Format | **biome** | Rust 製、eslint + prettier 統合の高速実装 |
| 型チェック | **tsc --noEmit** | TypeScript 公式 |
| テスト | **vitest** | Vite 統合、Jest 互換 API |
| 依存監査 | **osv-scanner** | Google 製、OSV データベース横断、npm + Python 一括スキャン |

### LLM Adapter

| カテゴリ | 採用 | 用途 / 根拠 |
|----|----|----|
| Claude Code CLI | **`claude` CLI + stream-json** | ai-team の `claude_code_client.py` を切り出して再利用、`--session-id` で会話継続 |
| Codex CLI | **`codex` CLI + JSONL** | ai-team の `codex_cli_client.py`、`codex exec --json` で `thread_id` 継続 |
| Gemini API | **google-generativeai** SDK | 公式 Python SDK |
| Anthropic API | **anthropic** SDK（`>=0.40.0`）| Phase 2 以降オプション（現状未採用）。`AbstractLLMClient` の Anthropic 実装候補（Issue #144）|
| OpenAI API | **openai** SDK（`>=1.30.0`）| Phase 2 以降オプション（現状未採用）。`AbstractLLMClient` の OpenAI 実装候補（Issue #144）|
| LLM 設定管理 | **pydantic-settings**（`>=2.0.0`）| `LLMClientConfig` の環境変数読み込み・`SecretStr` API キー管理に使用 |
| OAuth 認証 | Claude Max plan OAuth + Codex device-auth | API key 不要（従量課金回避）。`LLMProviderPort`（subprocess CLI）専用。`AbstractLLMClient`（HTTP API）は API キー方式 |

各 Adapter は **用途に応じて 2 種類の Port に分かれる**。詳細は §確定 LC-A を参照。

#### §確定 LC-A: `AbstractLLMClient`（HTTP API）と `LLMProviderPort`（CLI subprocess）の役割区分（2026-05-01 確定）

bakufu には LLM 呼び出し基盤が 2 種類存在する。**どちらを使うかの基準は下表で一意に決まる**。混在禁止。

| | `AbstractLLMClient` | `LLMProviderPort` |
|---|---|---|
| **用途** | 現状未採用（Phase 2 以降検討: HTTP API 直接が明示的に要求されるケースのみ）| coding agent 実行（コード生成 / 実行、長時間タスク）|
| **呼び出し方式** | HTTP API 直接（`anthropic` SDK / `openai` SDK）| subprocess CLI（`claude` / `codex` コマンド）|
| **セッション管理** | なし（1 req = 1 resp）| あり（TTL 2h / 再接続 / 孤児 GC）|
| **配置先（Port）** | `application/ports/llm_client.py`（`typing.Protocol`）| `application/ports/llm_provider_port.py`（Phase 1 実装済み）|
| **配置先（Impl）** | 未実装（Phase 2 以降）| `infrastructure/llm/`（Phase 1 実装済み: ClaudeCodeLLMClient / CodexLLMClient）|
| **対応 feature** | 現状なし（Phase 2 以降検討）| `ai-validation` / coding agent サブシステム（CLIサブプロセス方式）|
| **実装 Issue** | #144（本 Issue）| #123（`ai-validation`）/ 将来 Issue（coding agent サブシステム設計時）|

**判断基準**: Phase 1 では **すべての LLM 呼び出し（ai-validation 含む）に `LLMProviderPort`（CLI subprocess）を使用**。`AbstractLLMClient` は Phase 2 以降、HTTP API 直接が明示的に要求されるケースのみ検討する。

`AbstractLLMClient` は `docs/features/llm-client/` に設計を凍結（Issue #144）（Phase 2 placeholder, 現在未採用）。

#### LLM Adapter 運用方針（Phase 0 確定）

ai-team の `claude_code_client.py` を移植するにあたり、subprocess ベースの Claude Code CLI を本番運用する上で MVP として必要な「クラッシュ回復・セッション TTL・孤児プロセス処理」の方針を凍結する。各 LLM Adapter は本節の方針に従って `LLMProviderPort` を実装する。

##### セッションライフサイクル

| 項目 | 方針 | 根拠 |
|----|----|----|
| セッション識別 | Claude Code CLI の `--session-id <uuid>` を活用。Stage ごとに一意の session_id を Task に紐づけて永続化 | CLI 標準機能、再接続で同一文脈継続が可能 |
| Idle TTL | 最終アクセスから **2 時間** 経過した session_id は破棄、次回プロンプト時に再生成 | ai-team `claude_code_client.py` 実績準拠。長時間アイドルで CLI 内部状態が劣化する経験的閾値 |
| プロセス寿命 | 1 プロンプトごとに subprocess を spawn → 応答完了で正常終了。プロセス常駐はしない | subprocess 残置を最小化し、孤児リスクを下げる |
| 起動時 GC | bakufu Backend が spawn した CLI プロセスのみを **pidfile + 親 pid 追跡で限定的に SIGKILL**（後述「孤児プロセス GC の判定基準」参照） | クラッシュ後の孤児プロセスがリソースを食い続ける問題を防止しつつ、**同一ユーザーの他プロジェクトの Claude CLI を巻き込まない** |

##### クラッシュ・エラー分類と回復戦略

CLI の `returncode != 0` または stderr / stdout から以下 4 分類を判定する。`stream-json` のエラーペイロードを優先解析し、判別不能な場合は stderr 文字列マッチでフォールバック。

| エラー種別 | 判定材料 | 回復戦略 |
|----|----|----|
| `SessionLost` | stderr に `"session not found"` / `"unknown session"` | 同一 Stage 内で **新規 session_id を生成して 1 回のみ再投入**。再投入も失敗したら `BLOCKED` 化 |
| `RateLimited` | stderr に `"rate limit"` / HTTP 429 相当 | exponential backoff（**1m → 5m → 15m**）で最大 3 回。3 回失敗で `BLOCKED` 化 |
| `AuthExpired` | stderr に `"OAuth"` / `"unauthorized"` / 401 相当 | リトライしない。即 `BLOCKED` 化 + Notifier で人間に通知 |
| `Timeout` | プロセス無応答が 10 分継続 | SIGTERM → 5 秒 grace → SIGKILL。その後 `SessionLost` 相当の処理に合流 |
| その他 (`Unknown`) | 上記いずれにも該当しない | `BLOCKED` 化 + stderr 全文を Conversation に system message として保存し、人間が判断 |

##### `BLOCKED` 状態の運用

`Task.status = BLOCKED` は LLM Adapter が自動復旧不能と判断したときの隔離状態。Outbox Dispatcher は `BLOCKED` の Task に対するイベントを **再ディスパッチしない**（無限再試行防止）。

復旧経路：

| 経路 | 操作 | 効果 |
|----|----|------|
| UI（Phase 2） | Task 詳細画面の「再試行」ボタン | Task を `IN_PROGRESS` に戻し、最後の Stage を再実行 |
| CLI（MVP） | `bakufu admin list-blocked [--since <iso8601>]` | `BLOCKED` Task 一覧を発見（運用導線の起点） |
| CLI（MVP） | `bakufu admin retry-task <task_id>` | Task を `IN_PROGRESS` に戻し、最後の Stage を再実行 |
| CLI（MVP） | `bakufu admin cancel-task <task_id> --reason <text>` | Task を `CANCELLED` に遷移、関連 Gate も連鎖キャンセル |

dead-letter Outbox イベントの発見と再投入は同様に `bakufu admin list-dead-letters` / `retry-event` で行う（[`domain-model/events-and-outbox.md`](domain-model/events-and-outbox.md) 参照）。Discord Notifier 経由で `OutboxDeadLettered` 通知が常時飛ぶため、Owner が放置に気づける構造になっている。

##### subprocess の出力保全とマスキング

| 項目 | 方針 |
|----|----|
| stdout | `stream-json` をパースして deliverable 本体に変換、**マスキング適用後** Conversation に agent message として保存 |
| stderr | 全文を **マスキング適用後** Conversation に system message として保存（debug 用、デフォルトは UI 上で折り畳み） |
| `last_error` 列 | `Task.block()` 時に保存する文字列も同様にマスキング適用後 |
| マスキング規則 | 環境変数値の伏字化 + 既知 secret 正規表現 + ホームパス置換。詳細は [`domain-model/storage.md`](domain-model/storage.md) §シークレットマスキング規則 |
| 適用層 | `infrastructure/security/masking.py` を **永続化前の単一ゲートウェイ**として呼ぶ。各 Adapter / Repository から直接保存するルートは禁止 |
| 同時実行数 | MVP では Backend プロセスあたり同時 subprocess 数を **1**（シリアル実行）に制限。並列化は Phase 2 |

シリアル実行を採用する理由：
- MVP の検証対象は「Vモデル工程と外部レビューゲートの正しさ」であり、並列性は Out of Scope（requirements/functional-scope.md §非スコープに明記）
- 並列実行は git worktree 分離が前提となり、Phase 2 で `Workspace` Aggregate を別途設計する

##### subprocess の環境変数ハンドリング

子プロセスへの環境変数は **必要最小限の allow list 方式**で渡す。親プロセスの `os.environ` をそのまま継承しない（秘密情報の意図せぬ伝搬を防止）。

| 環境変数 | 引き継ぎ |
|----|----|
| `PATH` | ✓（CLI の解決に必須） |
| `HOME` / `USERPROFILE` | ✓（`~/.claude/` 等の OAuth 設定参照に必須） |
| `LANG` / `LC_ALL` | ✓（出力の文字エンコーディング） |
| `BAKUFU_*` | ✓（bakufu 自身の設定） |
| LLM プロバイダ別の必要キー | ✓（`ANTHROPIC_API_KEY` 等は Adapter が **その Adapter にのみ**渡す。他 Adapter には伝搬させない） |
| 上記以外 | ✗（明示拒否） |

##### 孤児プロセス GC の判定基準（Phase 0 確定）

「同一ユーザーの他プロジェクトの Claude CLI」を誤って kill しないよう、判定基準を以下に固定する。**プロセス名マッチによる kill は禁止**。

| 機構 | 内容 |
|----|----|
| pidfile / DB 登録 | bakufu Backend が `LLMProviderPort` 経由で subprocess を spawn する際、`bakufu_pid_registry` テーブル（`pid` / `parent_pid` / `started_at` / `cmd` / `task_id` / `stage_id`）に同一トランザクションで INSERT |
| 親 pid マーキング | `parent_pid = os.getpid()`（bakufu Backend 自身の pid）を必ず記録。Backend クラッシュ後の起動時 GC は「自分が起こしていた、または再起動前の自分の親 pid に紐づく子孫」だけを対象にする |
| 起動時 GC 動作 | テーブルの全 PID を `psutil.Process(pid)` で確認 → 生存していれば `psutil.Process(pid).children(recursive=True)` で子孫まで列挙 → SIGTERM 送出 → 5 秒 grace → SIGKILL → テーブルから DELETE |
| 子孫追跡 | `recursive=True` で孫プロセスも含める。CLI が内部で fork する子プロセスを取りこぼさない |
| pid 衝突対策 | `pid` だけでなく `started_at` を `psutil.Process(pid).create_time()` と比較し、PID が再利用された別プロセスは対象外（「これは私が起こしたあのプロセスではない」と判定して保護） |
| 通常終了の片付け | subprocess 正常終了時は Adapter が `bakufu_pid_registry` から DELETE。テーブルに残るのは異常終了 / クラッシュ時のみ |

`psutil.process_iter()` でプロセス名 `claude` をマッチして kill するような実装は **禁止**。bakufu 起動前に同一ユーザーが手動で起動した CLI を巻き込む。

#### Admin CLI 運用方針（Phase 0 確定）

Admin CLI は MVP の人間救済経路。すべての操作は `audit_log` テーブルに永続化する（追記のみ、UPDATE / DELETE 不可）。

##### コマンド一覧（MVP）

| コマンド | 用途 | 認可 |
|----|----|----|
| `bakufu admin list-blocked [--since <iso8601>]` | `BLOCKED` Task の一覧表示 | OS ユーザー = bakufu Backend 起動ユーザーであること |
| `bakufu admin list-dead-letters [--since <iso8601>] [--kind <event_kind>]` | dead-letter Outbox 一覧 | 同上 |
| `bakufu admin retry-task <task_id>` | Task を `BLOCKED` → `IN_PROGRESS` に戻し再実行 | 同上 |
| `bakufu admin cancel-task <task_id> --reason <text>` | Task を `CANCELLED` に遷移 | 同上 |
| `bakufu admin retry-event <event_id>` | dead-letter event を `PENDING` に戻して再投入 | 同上 |

##### 認可と監査ログの強制

| 項目 | 方針 |
|----|----|
| 認可 | bakufu Backend を起動した OS ユーザーのみ実行可能。CLI は SQLite ファイルへ直接アクセスせず、Backend の Unix domain socket 経由で要求を発行（Backend が起動していなければ操作不能） |
| audit_log 強制 | コマンド実行の **入口で** `audit_log` に `executed_at=now()`, `actor=os.getlogin()@<hostname>`, `command=<name>`, `args_json=<masked>` を INSERT。INSERT が失敗したら処理続行不可（Fail Fast） |
| マスキング | `args_json` の値は永続化前にマスキング規則を適用 |
| 結果記録 | 完了時 `result=SUCCESS` または `result=FAILURE` + `error_text`（マスキング後）を UPDATE |
| 不変性 | `audit_log` の UPDATE は `result` / `error_text` の null 埋めのみ許可。DELETE は SQLite トリガで全面拒否 |

#### ネットワーク / TLS 方針（Phase 0 確定）

| 項目 | 方針 |
|----|----|
| 既定バインド | `127.0.0.1:8000`（loopback のみ）。プロセス起動時に明示 |
| 外部公開時 | bakufu 自身は **TLS 終端しない**。reverse proxy（Caddy / Nginx + Let's Encrypt）の前段で HTTPS 終端、bakufu には HTTP で接続。bakufu は `Forwarded:` / `X-Forwarded-Proto:` ヘッダで HTTPS 経路を確認 |
| WebSocket | HTTP API と同一プロセス・同一ポート。`wss://` は reverse proxy が終端 |
| 設定 | 環境変数 `BAKUFU_BIND_HOST` / `BAKUFU_BIND_PORT` / `BAKUFU_TRUST_PROXY`（既定 `false`、外部公開時のみ `true`） |
| HSTS / Secure Cookie | reverse proxy 側で設定。bakufu アプリは `Set-Cookie` 発行時に `BAKUFU_TRUST_PROXY=true` なら自動で `Secure` 属性を付与 |

詳細な脅威モデル・OWASP Top 10 対応は [`threat-model.md`](threat-model.md) を参照。

### ローカル開発実行環境（Issue #154 確定）

`docker compose up` 一発で backend + frontend が同時起動できる統合環境を定義する。「bakufu で bakufu の自立開発を指示できる MVP」の前提インフラ。

#### データディレクトリとボリュームのマッピング

コンテナ内では `BAKUFU_DATA_DIR=/app/data` を固定値として使用する。docker-compose の named volume はこのパスにマウントする。

| パス（コンテナ内） | 対応する既存定義 | 内容 |
|----|----|----|
| `/app/data/bakufu.db` | 既存 §データベース `./bakufu-data/bakufu.db` と同一意味 | SQLite WAL データベース本体 |
| `/app/data/bakufu.db-wal` / `/app/data/bakufu.db-shm` | 同上 | WAL / 共有メモリファイル（SQLite が自動生成） |
| `/app/data/attachments/<sha256[0:2]>/<sha256>/` | 既存 §添付ストレージ `./bakufu-data/attachments/<sha256[0:2]>/<sha256>/` と同一意味 | content-addressable 添付ファイル |

`BAKUFU_DATA_DIR` 環境変数は Backend の全コンポーネントが参照するデータルートパス。コンテナ起動では `/app/data` 固定、ネイティブ起動では開発者が任意のパスを設定可能（既定は `./bakufu-data`）。

**⚠️ SQLite WAL × Docker bind mount 警告（Mac 必読）**

Docker Desktop for Mac（osxfs / gRPC FUSE）上では、SQLite WAL モードの locking が正しく機能しない既知問題がある（`*-shm` / `*-wal` ファイルの fsync 誤動作による DB 破損リスク）。**Mac 環境では named volume 必須**。bind mount への変更は Linux ホスト + native FS のみ許可する。CI（Linux runner）では bind mount も選択可。

#### コンテナ構成

| カテゴリ | 採用 | 用途 / 根拠 |
|----|----|----|
| コンテナオーケストレーション | **Docker Compose v2**（`docker compose` サブコマンド） | `docker compose up` 一発で backend + frontend 開発サーバを同時起動。V1（`docker-compose` Python 製）は 2023 年 EOL のため不採用。V2 は Docker Engine 同梱で追加インストール不要 |
| backend コンテナ | **`backend/Dockerfile`**（python:3.12-slim / 2 ステージビルド） | builder ステージで `uv sync --frozen` を実行し venv を構築、runtime ステージに venv のみコピーすることで pip を runtime に持ち込まない。開発 override では `src/` を bind mount し uvicorn `--reload` でホットリロード。**非 root ユーザー `bakufu`（uid=1000）で実行必須**（Dockerfile 末尾の `USER bakufu` + `/app/data` への `chown` で volume 上ファイル所有者を uid=1000 に固定し、root 所有ファイルをホスト側に作らない） |
| frontend コンテナ | **`frontend/Dockerfile`**（node:20-slim + pnpm） | 開発モードでは Vite 開発サーバ（`pnpm dev --host 0.0.0.0`）を起動し HMR を有効化。`--host 0.0.0.0` はコンテナ内部の全インターフェースへのバインドであり、ホスト公開は `ports:` の `127.0.0.1` バインドで制御する。**非 root ユーザー `node`（uid=1000）で実行必須**。リリースビルドでは `pnpm build` 後の静的ファイルを nginx で配信 |
| Vite 開発サーバ設定 | `server.allowedHosts: ["localhost", "127.0.0.1"]` / `server.hmr.clientPort: 5173` | `allowedHosts` を明示しないと Vite 5+ がホスト検証で HMR 接続を拒否する場合がある。`hmr.clientPort` はコンテナ外（ブラウザ）が使うポート番号を固定し、コンテナ内 HMR WebSocket と一致させる。これらを `vite.config.ts` に凍結する |
| データ永続化 | **named volume `bakufu-data`**（Mac では必須、Linux のみ bind mount 可） | named volume は Docker が管理する内部ボリュームで OS の FS 差異を吸収し、SQLite WAL locking 問題を回避する。コンテナ再作成後もデータが保持される |
| backend 環境変数 | **`backend/.env.example` → `backend/.env`**（gitignore 済み） | `.env.example` が必須環境変数を列挙する雛形（シークレット値はプレースホルダー）。`docker compose` は `env_file: backend/.env` で読み込む。**`.env` を git に追加することを `.gitignore` + gitleaks で二重防止** |
| frontend 環境変数 | **`frontend/.env.example` → `frontend/.env`**（gitignore 済み） | Vite は `VITE_` プレフィックスの変数のみビルド成果物に埋め込む（それ以外はビルド時に除去）。`VITE_API_BASE_URL=http://localhost:8000`（ブラウザ → backend の API エンドポイント）等を定義する。**`.env` を git に含めない**（backend と同じく gitleaks 二重防止） |
| ポートバインド（外部公開禁止） | **`"127.0.0.1:8000:8000"` / `"127.0.0.1:5173:5173"`** | `docker-compose.yml` の `ports:` は **必ず `"127.0.0.1:<host>:<container>"` 形式を強制**。`"<host>:<container>"`（= `"0.0.0.0"` バインド）はホスト全インターフェースへ露出するため禁止。CI でも同様 |
| CI / 最小 compose | **`docker-compose.yml`（基底）** | CI と最小起動に使う。override を適用しない状態で backend のみが起動可能な構成にする |
| 開発専用オーバーライド | **`docker-compose.override.yml`** | ソース bind mount・Vite HMR・uvicorn `--reload`・デバッグポートを定義。`docker compose up` は自動的に両ファイルを合成する（Docker Compose 公式挙動）。CI では `-f docker-compose.yml` のみ指定し override を排除する |
| backend ヘルスチェック | `GET http://localhost:8000/health` が HTTP 200 | `docker-compose.yml` の `healthcheck: test: ["CMD-SHELL", "curl -sf http://localhost:8000/health"]` に設定。`docker compose up --wait` で HEALTHY まで待機可能 |
| frontend ヘルスチェック | TCP port 5173 open 検査 | Vite に公式の health endpoint は存在しない。`healthcheck: test: ["CMD-SHELL", "nc -z localhost 5173"]`（netcat による TCP ポート open 検査）を採用する。HTTP GET より軽量で Vite 開発サーバの起動完了を確実に検知できる |
| backend 起動コマンド | **`uv run python -m bakufu.main`** | `bakufu.main`（`backend/src/bakufu/main.py`）は Bootstrap 経由で uvicorn をプロセス内起動する wrapper。マイグレーション実行等の 8 段階コールドスタートを経由させる必要があるため、`uvicorn bakufu.interfaces.http.app:app` を直接呼ぶことは禁止し、必ず `bakufu.main` 経由を強制する |
| CORS | backend `CORSMiddleware` で `http://localhost:5173` を allowedOrigin に追加 | frontend（`localhost:5173`）→ backend（`localhost:8000`）間の cross-origin リクエストに必須。設定詳細は [`docs/features/http-api-foundation/`](../features/http-api-foundation/) §CORS 設定を参照 |
| コンテナ間通信 | frontend コンテナ → `http://backend:8000`（docker internal DNS） | ブラウザ（ホスト側）→ backend は `http://localhost:8000`。Vite dev proxy や SSR を追加する場合はコンテナ間で `http://backend:8000` を使用する。この通信経路の信頼境界は [`threat-model.md §docker-compose ネットワーク境界`](threat-model.md) を参照 |
| just 統合 | `just up` / `just down` / `just logs` / `just env-init` | `justfile` に docker compose コマンドを alias として定義。`just env-init` は OS 横断で `.env.example` → `.env` をコピーする（`justfile` の `windows-shell` 設定により Windows は PowerShell、Unix は sh で実行）。`just up`（コンテナ起動）とネイティブ起動の両方を同一 `justfile` で提供する |

#### ローカル起動手順（OS 横断）

| 手順 | コマンド（cross-platform） | 備考 |
|----|----|----|
| 1. 環境変数準備 | `just env-init` | `justfile` が OS 判定し PowerShell `Copy-Item`（Windows）または `cp`（Unix）を実行。`cp` を直接書かない（Windows 非対応のため） |
| 2. コンテナ起動 | `just up` | 初回はイメージビルドを含む |
| 3. ヘルス確認 | `just health` | `GET http://localhost:8000/health` → `{"status":"ok"}` を確認 |
| 4. UI アクセス | ブラウザで `http://localhost:5173` | Vite HMR 有効 |
| 5. 停止 | `just down` | `just down-v` でボリューム（データ）も削除 |

ネイティブ起動（docker なし）も継続サポートする: `uv run python -m bakufu.main`（backend）、`pnpm dev`（frontend）。docker は**開発者体験の向上手段**であって必須依存にしない。ローカルファースト要件との整合を維持する。

### 開発ワークフロー

詳細は [`docs/features/dev-workflow/`](../features/dev-workflow/) の Vモデル設計書 5 本を参照。

| カテゴリ | 採用 | 用途 |
|----|----|----|
| Git フック | **lefthook** | Go 製、並列実行、Windows ネイティブ |
| タスクランナー | **just** | `justfile` で fmt / lint / typecheck / test / audit を統合 |
| コミット規約 | **convco** | Conventional Commits 検証（commit-msg フック） |
| Secret 検知 | **gitleaks** | staged 差分の汎用 secret スキャン |
| Setup スクリプト | `scripts/setup.{sh,ps1}` | clone 後 1 ステップ、SHA256 検証つき |

### CI / CD

| 用途 | 採用 |
|----|----|
| CI | GitHub Actions（5 ワークフロー: lint / typecheck / test-backend / test-frontend / audit） |
| ガバナンス | branch-policy / back-merge-check / pr-title-check（言語非依存 3 ワークフロー） |
| ブランチ戦略 | GitFlow（main / develop / feature/* / release/* / hotfix/*） |
| マージ戦略 | feature → develop は squash、release/hotfix → main は merge commit |

## 不採用候補と根拠

| 候補 | カテゴリ | 不採用理由 |
|----|----|----|
| Django | Web FW | DDD と相性が悪い（Active Record、ORM とドメイン密結合） |
| Flask | Web FW | OpenAPI 自動生成・WebSocket ネイティブ・Pydantic 統合が弱い |
| Tornado | Web FW | エコシステム縮小、FastAPI が後継として優位 |
| Litestar | Web FW | 新興。FastAPI のエコシステム成熟度に及ばない |
| Postgres（MVP 段階） | DB | ローカルファースト要件に不適合。本番でスケールが必要になった時点で切替（YAGNI） |
| SQLite BLOB（添付保存） | ストレージ | WAL ファイル肥大 + ストリーミング配信不能 + バックアップ単位がモノリシックになる。content-addressable filesystem を採用 |
| Redis / RabbitMQ（Outbox） | メッセージング | ローカルファースト要件で外部依存を増やさない。シングルプロセス前提なら SQLite テーブル + asyncio 常駐 task で十分（YAGNI） |
| Peewee / Tortoise ORM | ORM | SQLAlchemy 2.x の async + Mapper 分離の柔軟性に及ばない |
| poetry | パッケージ管理 | uv の桁違いの速度に劣る。`uv` に統一 |
| pip + venv | パッケージ管理 | lockfile が公式機能でない、バージョン解決の再現性が弱い |
| mypy | 型チェック | pyright より遅い、エラー表現の表現力が低い、strict 運用で IDE 統合差が大きい |
| flake8 / pylint / black / isort | Lint/Format | ruff が機能上位互換、桁違いに高速 |
| safety | 依存監査 | pip-audit が PyPA 公式 |
| Next.js | フロント FW | bakufu はローカルファースト SPA で SSR 不要。Vite + React で十分 |
| Remix | フロント FW | 同上 |
| Astro | フロント FW | コンテンツ寄りで動的 UI 主体の bakufu に不適合 |
| Vue / Svelte / Solid | フロント FW | エコシステムは劣らないが、ClawEmpire 寄せ + PixiJS 統合の事例が React 中心 |
| MobX / Redux | 状態管理 | Zustand + React Query で十分、ボイラープレート削減 |
| eslint + prettier | Lint/Format | biome 単一ツールで統合、Rust 実装で高速 |
| Jest | テスト | vitest が Vite 統合で高速、Jest 互換 API |
| Playwright（MVP） | E2E | UI 完成後に追加（YAGNI） |
| npm / yarn | パッケージ管理 | pnpm のハードリンク方式が省ディスクかつ高速 |
| pre-commit framework（Python） | Git フック | Python ランタイム依存、lefthook の単一バイナリ完結性に劣る |
| husky | Git フック | Node 依存、bakufu はバックエンドが Python のため統一不能 |
| commitlint | コミット規約 | Node 依存、convco は Rust 製単一バイナリ |
| Makefile | タスクランナー | Windows ネイティブ非対応、just の `windows-shell` 設定で代替 |
| npm scripts | タスクランナー | フロント限定、バックエンド Python と統合不能 |
| docker-compose V1（Python 製） | コンテナ起動 | 2023 年 EOL。Docker Engine に同梱の V2（Go 製）で代替。`docker-compose` コマンドは非推奨 |
| Kubernetes / Helm | コンテナオーケストレーション | ローカルファースト単一プロセスの MVP にオーバーエンジニアリング（YAGNI）。スケール要件が生じた段階で検討 |
| Podman / Podman Compose | コンテナ起動 | Podman Desktop は Linux では rootless 動作で優位だが、Mac / Windows では内部 VM を経由するため SQLite WAL locking 問題がより深刻になる。Podman Compose は docker-compose V2 との挙動差異（volume 名前空間・healthcheck コマンド解釈）が未整理で、チーム全員が同一挙動を期待できない。なお Docker Desktop は個人・スタートアップ・教育機関は無償だが、従業員 250 名以上または年商 1000 万 USD 超の企業は有償（Docker Business プラン必須）。本プロジェクトの MVP スコープはローカルファーストの個人 / 小規模チームを想定しており現時点で非対象だが、商用利用時は Podman への移行または OrbStack 採用（Mac 向け代替、MIT 系ライセンス）を別途検討する |

## バージョンピン方針

- **Python ツール（uv 経由）**: `pyproject.toml` の `[dependency-groups]` に dev dependency としてバージョン指定。`uv.lock` で完全固定
- **Node ツール（pnpm 経由）**: `package.json` に dev dependency として指定、`pnpm-lock.yaml` で固定
- **GitHub Releases バイナリ（uv / just / convco / lefthook / gitleaks）**: `scripts/setup.{sh,ps1}` の `<TOOL>_VERSION` 定数 + `<TOOL>_SHA256_*` でピン。`scripts/ci/audit-pin-sync.sh` で sh / ps1 同期検証

## アーキテクチャ層構成

```
┌─────────────────────────────────────────────────────────┐
│ interfaces/ (HTTP router / WebSocket)                   │
└──────────────┬──────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────────┐
│ application/ (Use Case + Port)                          │
└──────┬───────────────────────┬──────────────────────────┘
       ↓                       ↓
┌──────────────┐       ┌──────────────────────────────────┐
│ domain/      │       │ infrastructure/                  │
│ (Aggregate)  │       │ (Repository / LLM / Notifier)    │
└──────────────┘       └──────────────────────────────────┘
```

依存方向: `interfaces` → `application` → `domain`、`infrastructure` → `application`（Port 実装）

詳細な責務・配置は [`domain-model.md`](domain-model.md) §モジュール配置 参照。
