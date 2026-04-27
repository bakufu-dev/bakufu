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
| データベース | **SQLite 3.40+**（WAL モード） | ローカルファースト、ゼロコンフィグ、後段で Postgres への切替可能。BLOB は使わず、添付ファイルは content-addressable filesystem に分離（`domain-model.md` §Attachment 参照） |
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
| Anthropic API | **anthropic** SDK | 公式 Python SDK、tool use 対応 |
| OAuth 認証 | Claude Max plan OAuth + Codex device-auth | API key 不要（従量課金回避） |

各 Adapter は application 層の `LLMProviderPort` を実装する。Agent から呼ばれる際は Provider 配下の Strategy パターン。

#### LLM Adapter 運用方針（Phase 0 確定）

ai-team の `claude_code_client.py` を移植するにあたり、subprocess ベースの Claude Code CLI を本番運用する上で MVP として必要な「クラッシュ回復・セッション TTL・孤児プロセス処理」の方針を凍結する。各 LLM Adapter は本節の方針に従って `LLMProviderPort` を実装する。

##### セッションライフサイクル

| 項目 | 方針 | 根拠 |
|----|----|----|
| セッション識別 | Claude Code CLI の `--session-id <uuid>` を活用。Stage ごとに一意の session_id を Task に紐づけて永続化 | CLI 標準機能、再接続で同一文脈継続が可能 |
| Idle TTL | 最終アクセスから **2 時間** 経過した session_id は破棄、次回プロンプト時に再生成 | ai-team `claude_code_client.py` 実績準拠。長時間アイドルで CLI 内部状態が劣化する経験的閾値 |
| プロセス寿命 | 1 プロンプトごとに subprocess を spawn → 応答完了で正常終了。プロセス常駐はしない | subprocess 残置を最小化し、孤児リスクを下げる |
| 起動時 GC | Backend 起動時に「過去に起動した CLI プロセスのうち bakufu の管理外で生存しているもの」を `psutil` で列挙し SIGKILL | クラッシュ後の孤児プロセスがリソースを食い続ける問題を防止 |

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
| CLI（MVP） | `bakufu admin retry-task <task_id>` | 同上 |
| CLI（MVP） | `bakufu admin cancel-task <task_id> --reason <text>` | Task を `CANCELLED` に遷移 |

##### subprocess の出力保全

| 項目 | 方針 |
|----|----|
| stdout | `stream-json` をパースして deliverable 本体に変換、Conversation に agent message として保存 |
| stderr | 全文を Conversation に system message として保存（debug 用、デフォルトは UI 上で折り畳み） |
| 同時実行数 | MVP では Backend プロセスあたり同時 subprocess 数を **1**（シリアル実行）に制限。並列化は Phase 2 |

シリアル実行を採用する理由：
- MVP の検証対象は「Vモデル工程と外部レビューゲートの正しさ」であり、並列性は Out of Scope（mvp-scope.md §非スコープに明記）
- 並列実行は git worktree 分離が前提となり、Phase 2 で `Workspace` Aggregate を別途設計する

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
