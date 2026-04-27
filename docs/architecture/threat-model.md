# bakufu 脅威モデル / セキュリティ方針

bakufu の **信頼境界・攻撃者像・主要資産・OWASP Top 10 対応**を凍結する。各 feature 設計書はここで引いた境界に従い、追加の攻撃面を生まない範囲で実装する。

## 信頼境界図

```mermaid
flowchart LR
    User["CEO / Owner Reviewer<br/>ローカル端末ユーザー"]

    subgraph LocalHost["ローカル端末（信頼境界 A: OS ユーザー）"]
        direction TB
        Browser["Web ブラウザ<br/>（同一ユーザー権限）"]
        ReverseProxy["reverse proxy<br/>（Caddy / Nginx、外部公開時のみ）<br/>TLS 終端"]
        Backend["bakufu Backend<br/>FastAPI + uvicorn<br/>127.0.0.1:8000 既定"]
        DB[("SQLite WAL<br/>0600 mode")]
        FS[("BAKUFU_DATA_DIR<br/>添付ファイル<br/>0700 mode")]
        PidReg[("bakufu_pid_registry<br/>子プロセス追跡")]
        AuditLog[("audit_log<br/>追記のみ")]
        SubProc["LLM CLI subprocess<br/>spawn / kill")"]
    end

    subgraph Network["外部ネットワーク（信頼境界 B: 不信）"]
        Discord["Discord API<br/>HTTPS"]
        GitHub["GitHub API / git push<br/>HTTPS"]
        LLMRemote["LLM プロバイダ<br/>Anthropic / OpenAI 等<br/>HTTPS"]
    end

    User -- "HTTPS（外部公開時）<br/>HTTP（loopback）" --> Browser
    Browser -- "HTTP / WebSocket" --> ReverseProxy
    ReverseProxy -. "HTTP（loopback）" .-> Backend
    Browser -. "直接（既定）<br/>loopback" .-> Backend
    Backend <--> DB
    Backend <--> FS
    Backend <--> PidReg
    Backend <--> AuditLog
    Backend -- "fork / exec<br/>env allow-list" --> SubProc
    SubProc -- "HTTPS<br/>OAuth トークン<br/>local file" --> LLMRemote
    Backend -- "HTTPS<br/>Bot Token" --> Discord
    Backend -- "HTTPS<br/>OAuth / SSH" --> GitHub
```

信頼境界は 2 層：

- **境界 A**: ローカル端末上の OS ユーザー領域。Backend / DB / 添付ストレージ / subprocess はすべてこの境界内。攻撃者が既に同一 OS ユーザー権限を取得していたら防御不能（前提）
- **境界 B**: 外部ネットワーク。Discord / GitHub / LLM プロバイダ。すべて不信扱い、TLS 必須、トークンは最小権限

## 主要資産と機密性レベル

| 資産 | 機密性 | 完全性 | 可用性 | 保管場所 |
|----|----|----|----|----|
| Anthropic / OpenAI / Gemini OAuth トークン | **高** | 高 | 中 | OS ユーザーホーム配下（CLI 標準）。bakufu は触らない |
| GitHub トークン | **高** | 高 | 中 | `gh` CLI 標準（`gh auth login`）。bakufu は触らない |
| Discord Bot Token | **高** | 高 | 中 | 環境変数 `BAKUFU_DISCORD_BOT_TOKEN`、または `~/.config/bakufu/secrets.toml`（OS ユーザーのみ可読）|
| Conversation 本文 | **中** | 高 | 中 | SQLite。マスキング後保存 |
| Deliverable 本文 | **中** | 高 | 中 | SQLite。マスキング後保存 |
| `Persona.prompt_body`（Agent システムプロンプト） | **中** | 高 | 中 | SQLite（Agent VO の一部として永続化）。LLM システムプロンプトに展開される自然言語のため、API key / GitHub PAT 等の secret が混入する可能性あり。Repository 永続化前にシークレットマスキング規則（[`domain-model/storage.md`](domain-model/storage.md) §シークレットマスキング規則）の適用必須。Phase 2 で prompt injection 検知（[`feature/llm-adapter`](../features/) 責務）を追加予定 |
| Discord webhook URL token（`NotifyChannel.target` の token 部） | **高** | 高 | 中 | SQLite（NotifyChannel VO の一部）。token を持つ第三者は当該 webhook 経由で任意送信可能。VO の `field_serializer` で `mode='json'` 出力時に `<REDACTED:DISCORD_WEBHOOK>` 化、Repository 層でも追補マスキング（[`feature/workflow`](../features/workflow/detailed-design.md) §確定 G） |
| 添付ファイル | **中** | 高 | 中 | filesystem `BAKUFU_DATA_DIR/attachments/<sha256>/`、`0600` mode |
| audit_log | 低 | **最高**（改ざん不可） | 中 | SQLite、追記のみ |
| domain_event_outbox | 中 | **最高**（at-least-once 保証の基盤） | 高 | SQLite |
| ExternalReviewGate.audit_trail | 中 | **最高**（人間判断履歴） | 中 | SQLite、Gate 内に inline |

## 攻撃者像（Threat Actors）

| # | アクター | 動機 | 経路 | 影響 |
|---|---------|-----|-----|------|
| T1 | 同一 OS ユーザー権限を持つ別プログラム | secret 抽出 | DB / FS / 環境変数の読み取り | OAuth トークン漏洩 |
| T2 | ブラウザ経由のローカル攻撃者（XSS / CSRF） | bakufu 機能の悪用 | 添付配信時の MIME / `Content-Disposition` の隙、CSRF トークン欠如 | Task の不正起票・取り消し |
| T3 | ネットワーク上の中間者（外部公開時） | 通信盗聴・改ざん | TLS なし or 弱い TLS、ヘッダ偽装 | Conversation / Deliverable 漏洩、Gate 判断の改ざん |
| T4 | 悪意ある LLM Agent | 出力に prompt injection / コマンド埋め込み | Conversation の本文経由で他 Agent へ伝搬 | 副作用のあるコマンド実行（`gh`, `git`, shell） |
| T5 | サプライチェーン攻撃 | 開発ツール経由で侵入 | npm / PyPI / GitHub Releases の置き換え | Backend 側コード実行 |
| T6 | 物理アクセス | ディスク取得 | 添付ファイル / SQLite の直読み | 全資産漏洩 |

## 攻撃面と対策（要点）

### A1. 添付ファイル経路（T2 対策）

| 攻撃面 | 対策 | 配置先 |
|----|----|----|
| filename によるパストラバーサル | NFC 正規化 + 拒否文字（`/`, `\`, `\0`, 制御文字, `..`, Windows 予約名）+ `os.path.basename()` 二重防護 | [`domain-model/storage.md`](domain-model/storage.md) §filename サニタイズ |
| MIME spoofing による XSS / RCE | `python-magic` 実コンテンツ判定 + ホワイトリスト（`text/html` 拒否） | 同上 §MIME タイプ検証 |
| 巨大ファイルによる DoS | 単一 10 MiB / Task 100 MiB / Empire 5 GiB 上限 | 同上 §サイズ上限 |
| ブラウザ実行（XSS） | `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff` + `Content-Security-Policy: sandbox` を**配信時に強制** | 同上 §配信時のセキュリティ要件 |
| 配信側でも allow list 再検証（多層防御） | リクエスト時 MIME 再判定、storage allow list と差分があれば 415 Unsupported Media Type | 同上 |

### A2. subprocess 経路（T1 / T4 対策）

| 攻撃面 | 対策 | 配置先 |
|----|----|----|
| 環境変数経由の secret 漏洩 | 子プロセス env を allow-list 化（`PATH` / `HOME` / `LANG` / `BAKUFU_*` / Adapter 限定キーのみ） | [`tech-stack.md`](tech-stack.md) §subprocess の環境変数ハンドリング |
| stderr / stdout への secret 流出 | 永続化前にマスキング規則適用（環境変数値伏字 + 既知正規表現） | [`domain-model/storage.md`](domain-model/storage.md) §シークレットマスキング規則 |
| 孤児プロセス GC の誤 kill | pidfile + `parent_pid` + `create_time()` 比較で「自分が起こした子孫」だけ kill。プロセス名マッチ禁止 | [`tech-stack.md`](tech-stack.md) §孤児プロセス GC の判定基準 |
| Agent の prompt injection 経由のコマンド埋め込み | LLM 出力は **deliverable / conversation メッセージ**としてしか扱わない。「LLM 出力を直接 shell に渡す」ような経路は提供しない | application 層の設計上の禁則 |

### A3. ネットワーク経路（T3 対策）

| 攻撃面 | 対策 | 配置先 |
|----|----|----|
| HTTP 平文での通信盗聴 | 既定バインド `127.0.0.1:8000`（loopback）。外部公開は reverse proxy + TLS 必須 | [`tech-stack.md`](tech-stack.md) §ネットワーク / TLS 方針 |
| Cookie 漏洩 | `BAKUFU_TRUST_PROXY=true` 時、`Set-Cookie` に `Secure` / `HttpOnly` / `SameSite=Strict` を強制 | 同上 |
| CSRF | SameSite=Strict + 状態変更 API は `Origin` ヘッダ検証 | feature `docs/features/http-api/` で詳細 |
| WebSocket origin 偽装 | `Sec-WebSocket-Origin` 検証で許可 origin のみ受け入れ | 同上 |

### A4. 管理操作（T1 / T6 対策）

| 攻撃面 | 対策 | 配置先 |
|----|----|----|
| Admin CLI の不正実行 | Unix domain socket 経由で Backend に要求。SQLite 直接編集経路は持たない（Backend が落ちていれば操作不能） | [`tech-stack.md`](tech-stack.md) §Admin CLI 運用方針 |
| 監査ログの改ざん | `audit_log` は追記のみ。DELETE / UPDATE（`result` 以外）を SQLite トリガで拒否 | [`domain-model/value-objects.md`](domain-model/value-objects.md) §audit_log |
| ファイル権限 | `bakufu.db` 0600 / `BAKUFU_DATA_DIR` 0700 / `~/.config/bakufu/secrets.toml` 0600。起動時に確認、緩い場合は警告ログ + 起動中止 | feature `docs/features/persistence/` で詳細 |

### A5. サプライチェーン（T5 対策）

CONTRIBUTING.md §AI 生成フッターの禁止 / §開発ツール SHA256 検証 と既存の以下の枠組みで対応済み：

- `scripts/setup.{sh,ps1}` の SHA256 検証
- `pip-audit` / `osv-scanner` の依存監査 CI ジョブ
- `gitleaks` の secret 検知（pre-commit + CI）
- branch protection の `Require signed commits`

## OWASP Top 10 (2021) 対応表

| # | カテゴリ | bakufu での該当 | 対応 |
|---|----|----|----|
| A01 | Broken Access Control | Admin CLI / API の権限境界 | OS ユーザー = Backend 起動ユーザーのみ。マルチユーザー RBAC は Phase 2（YAGNI、シングルユーザー前提なので MVP は不要） |
| A02 | Cryptographic Failures | OAuth トークン / Discord Bot Token / Cookie | OAuth は CLI 標準ストア。Cookie は `Secure`/`HttpOnly`/`SameSite=Strict`。OS file mode 0600。SQLite 暗号化は Phase 2 |
| A03 | Injection | パストラバーサル / SQL Injection / コマンドインジェクション | filename サニタイズ二重防護、SQLAlchemy パラメータバインド強制、subprocess は `args` 配列で渡す（shell 経由しない） |
| A04 | Insecure Design | Aggregate 境界・Tx 境界・補償設計 | Outbox / pre-validate / BLOCKED 隔離 / pidfile GC で意図せぬ副作用を排除 |
| A05 | Security Misconfiguration | バインドアドレス / 権限 / TLS | 既定 loopback、`BAKUFU_TRUST_PROXY` で TLS 経路を明示、ファイル権限を起動時に検査 |
| A06 | Vulnerable / Outdated Components | 依存ライブラリ脆弱性 | `pip-audit` + `osv-scanner` を CI で定期実行、SHA256 ピン |
| A07 | Identification / Auth Failures | OS ユーザー認証への委譲 | Unix domain socket と OS ユーザー権限。MVP では Web UI のセッションも loopback 前提で軽量。外部公開時は reverse proxy 側で Basic / OIDC 終端（Phase 2） |
| A08 | Software / Data Integrity Failures | コミット署名 / Outbox の at-least-once / audit_log 不変性 | branch protection（`Require signed commits`）、Outbox の `event_id` 冪等性、`audit_log` の DELETE 禁止トリガ |
| A09 | Security Logging / Monitoring Failures | 監査追跡 | `audit_log` 強制、`OutboxDeadLettered` の Discord 通知、Conversation のフル保存 |
| A10 | Server-Side Request Forgery (SSRF) | 添付ファイル URL / 外部 fetch | bakufu Backend は LLM プロバイダ / Discord / GitHub のみへ通信。任意 URL fetch 機能は MVP に含めない（Assistant Room の Web 検索は Phase 2 で URL allow list 方式） |

## 受入確認（脅威モデル観点）

[`mvp-scope.md`](mvp-scope.md) §受入基準 11/12 に加え、本書の凍結後は以下を E2E テスト時に確認する：

1. 添付ファイルに `..%2F` を含む filename を投入 → 拒否
2. `image/png` を装った `text/html` を投入 → 拒否（実コンテンツ MIME 判定）
3. 11 MiB の添付を投入 → 拒否（サイズ上限）
4. 添付配信レスポンスに `Content-Disposition: attachment` / `X-Content-Type-Options: nosniff` が付与される
5. subprocess の stderr に `sk-ant-api03-XXXX...` を含めて流す → DB に保存される文字列は `<REDACTED:ANTHROPIC_KEY>`
6. 環境変数 `ANTHROPIC_API_KEY=sk-ant-api03-XXXX` を起動時に設定し、Conversation に同値を含む文字列を流す → DB は `<REDACTED:ENV:ANTHROPIC_API_KEY>` に置換
7. 別プロジェクトの `claude` CLI を bakufu 起動前に手動 spawn 状態で bakufu Backend を起動 → 当該プロセスは GC されない（pidfile に登録がないため）
8. Admin CLI の全コマンドが `audit_log` に記録される
9. `BAKUFU_TRUST_PROXY=false` で外部 IP からアクセス → 接続不可（loopback バインド）

## 残課題（Phase 2 以降）

- マルチユーザー RBAC（A01）
- SQLite 暗号化（A02）
- WebAuthn / Passkey（A07）
- Web 検索の URL allow list 機構（A10）
- Conversation 全文検索のインデックス漏洩対策（インデックスにも secret が乗らないこと）
