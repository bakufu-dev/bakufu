# 機能スコープ

bakufu MVP（v0.1.0）に含める機能と除外する機能を明示する。「動かして検証する価値が最も高い最小範囲」を選定し、ドメインモデルの正しさを早期に検証する。

## 含める機能

| 機能 | 詳細 | 根拠 |
|----|----|----|
| **Empire / Room / Agent CRUD** | UI から作成・編集・アーカイブ | 中核ドメインで、なければ何も始まらない |
| **Workflow Designer**（簡易版） | プリセット（V モデル / アジャイル）から選択 + JSON 編集 | 部屋を作れないと検証できない。ビジュアル編集（react-flow）は Phase 2 |
| **V モデル開発室 1 部屋 + Agent 5 体** | leader / developer / tester / reviewer / ux の 5 役 | 標準的なソフトウェア開発工程を実証 |
| **Task の起票 → 工程進行 → 完了** | CEO directive (`$` プレフィックス) → Task 生成 → 各 Stage を Agent が処理 | E2E のフロー検証 |
| **InternalReviewGate（内部レビュー機構）** | Workflow.Stage 末尾で GateRole（reviewer / ux / security 等、Workflow 定義時に任意観点を指定）が並列・独立に judging し、全 APPROVED で次フェーズへ。1 人でも REJECTED で前段に差し戻し。観点別レビュワーは ai-team から移植 | 1 対 1 CLI 使用と人間チェック前の品質が変わらない問題を解決。Vモデルの「ピアレビュー」相当、bakufu 差別化価値の核心 |
| **ExternalReviewGate（人間承認画面）** | 承認 / 差し戻し（コメントつき）、複数ラウンド対応。**内部レビュー全合格を経由しないと到達しない**（Workflow 強制） | bakufu の最重要要件 |
| **Discord 通知**（外部レビュー依頼時） | reviewer（CEO）への通知経路 | レビュー忘れ防止、ai-team の運用と互換 |
| **Claude Code CLI Adapter** | ai-team の `claude_code_client.py` を切り出して再利用 | LLM 実行の唯一の道（MVP）。`--session-id` で会話継続 |
| **WebSocket リアルタイム同期** | UI 上で Task 状態 / Agent ステータスがライブ更新 | UX 必須 |
| **SQLite ローカル永続化** | Empire / Room / Workflow / Agent / Task / Gate を保存 | ローカルファースト、再起動後も状態維持 |
| **基本ダッシュボード（普通の UI）** | Tailwind ベースの管理画面、各 Aggregate 一覧 + 詳細 | MVP は機能優先、ピクセルアートは後 |
| **Conversation ログ** | Stage 内の Agent 間対話を時系列表示 | デバッグ・履歴監査 |
| **Admin CLI**（最低限 5 本） | `list-blocked` / `list-dead-letters` / `retry-task` / `cancel-task` / `retry-event` | BLOCKED Task と dead-letter event を **発見** し、人手で救済する最終経路。発見系（`list-*`）が無いと放置されるため必須。すべて `audit_log` に強制記録。UI は Phase 2 |
| **シークレットマスキング** | 環境変数値伏字 + 既知 secret 正規表現 + ホームパス置換、永続化前の単一ゲートウェイ | LLM subprocess の出力経由で OAuth トークン等が DB に流入するのを物理的に防ぐ |
| **subprocess pidfile GC** | `bakufu_pid_registry` テーブル + 親 pid + `create_time()` で自分の子孫だけを kill | 同一ユーザーの他プロジェクト Claude CLI を巻き込まない |
| **添付ファイル安全配信** | filename サニタイズ + MIME ホワイトリスト + サイズ上限 + `Content-Disposition: attachment` / `X-Content-Type-Options: nosniff` | XSS / パストラバーサル / DoS の防止 |
| **TLS / loopback バインド** | 既定 `127.0.0.1:8000`、外部公開時は reverse proxy + TLS 終端 | 外部公開を意図しない MVP 既定で安全 |
| **audit_log（追記のみ）** | Admin CLI / GC / セキュリティ対応の全操作を不可逆に記録 | 監査性（OWASP A08） |

## 含めない機能（フェーズ 2 以降）

| 機能 | 理由 / 後回し根拠 |
|----|----|
| 雑談 Room | ai-team の `discussion` チャネル相当。MVP の核心ではない |
| アシスタント Room | ai-team の `assistant` チャネル相当。Web 検索 / GA4 / GitHub 操作等の統合は別 feature |
| ブログ編集部 Room | 同上、プラグイン的位置づけ |
| マルチプロバイダ（Codex / Gemini / OpenCode 等） | Claude Code CLI 1 本で MVP は十分。後段で `LLMProviderPort` 経由で追加 |
| ピクセルアート UI（PixiJS） | MVP は機能ベースで、まずドメインモデルの正しさを検証。Phase 2 で UI を磨く |
| ビジュアル Workflow Designer（react-flow 等） | MVP は JSON 編集 + プリセットで十分 |
| メッセンジャー多対応（Slack / Telegram / iMessage 等） | Discord 単独で MVP の通知要件は満たす |
| マルチユーザー / RBAC | bakufu はシングルユーザー（CEO = リポジトリオーナー）前提。組織配備は後段 |
| Agent CLI セッション継続の TTL 高度化 | ai-team の 2h TTL を踏襲。チューニングは運用で判断 |
| OAuth トークン暗号化保存 | MVP は `.env` で十分。SQLite 暗号化は Sub-issue C 相当の Phase 2 で対応 |
| Conversation 全文検索 | MVP は単純な時系列表示で十分 |
| Office Pack Profiles（ClawEmpire 由来） | bakufu は Workflow Designer で代替可。プロファイルは Phase 3 |
| git worktree 統合（並列作業隔離） | Agent 同士の並列性は MVP では試さない。シリアル実行で OK |
| Kanban ビュー | Task 一覧 + Stage 列挙で MVP は OK |
| Web 検索 / GA4 / BigQuery 統合 | Assistant Room 相当、Phase 2 |

## 非スコープの明示

以下は MVP では**意図的に除外**する。要望が出ても MVP の範囲では対応しない:

- ピクセルアート UI（後段の見栄え強化）
- マルチエージェント並列実行（Stage 内で複数 Agent を同時動作させる）
- Agent の自動採用（人間が UI で 1 名ずつ採用）
- Agent 間の自発的協議（leader が指揮し、シリアル実行）
- 自然言語 Workflow 生成（"アジャイル開発室を作って" でプリセット生成 — Phase 3）
- 別マシンへのデータ同期（ローカルファーストを徹底）
- bakufu インスタンス間の連携（社外連携 — 別プロダクト）

これらは v0.2.0 以降で順次追加する。

## 関連

- [`milestones.md`](milestones.md) — マイルストーン M1〜M7
- [`acceptance-criteria.md`](acceptance-criteria.md) — MVP 完了の判定基準
- [`../analysis/business-vision.md`](../analysis/business-vision.md) — bakufu 全体のビジョン
