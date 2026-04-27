# bakufu MVP スコープ

bakufu の MVP（v0.1.0 想定）に含める機能と除外する機能を明示する。「動かして検証する価値が最も高い最小範囲」を選定し、ドメインモデルの正しさを早期に検証する。

## MVP の提供価値

> **「UI で V モデル開発室を作って、Agent 5 体でタスクを実行し、各工程の外部レビューを人間が承認/差し戻しできる」**

これが動けば、bakufu の核心思想（Room First / DAG ワークフロー / External Review Gate）が実証される。

## 含める機能

| 機能 | 詳細 | 根拠 |
|----|----|----|
| **Empire / Room / Agent CRUD** | UI から作成・編集・アーカイブ | 中核ドメインで、なければ何も始まらない |
| **Workflow Designer**（簡易版） | プリセット（V モデル / アジャイル）から選択 + JSON 編集 | 部屋を作れないと検証できない。ビジュアル編集（react-flow）は Phase 2 |
| **V モデル開発室 1 部屋 + Agent 5 体** | leader / developer / tester / reviewer / ux の 5 役 | 標準的なソフトウェア開発工程を実証 |
| **Task の起票 → 工程進行 → 完了** | CEO directive (`$` プレフィックス) → Task 生成 → 各 Stage を Agent が処理 | E2E のフロー検証 |
| **ExternalReviewGate（人間承認画面）** | 承認 / 差し戻し（コメントつき）、複数ラウンド対応 | bakufu の最重要要件 |
| **Discord 通知**（外部レビュー依頼時） | reviewer（CEO）への通知経路 | レビュー忘れ防止、ai-team の運用と互換 |
| **Claude Code CLI Adapter** | ai-team の `claude_code_client.py` を切り出して再利用 | LLM 実行の唯一の道（MVP）。`--session-id` で会話継続 |
| **WebSocket リアルタイム同期** | UI 上で Task 状態 / Agent ステータスがライブ更新 | UX 必須 |
| **SQLite ローカル永続化** | Empire / Room / Workflow / Agent / Task / Gate を保存 | ローカルファースト、再起動後も状態維持 |
| **基本ダッシュボード（普通の UI）** | Tailwind ベースの管理画面、各 Aggregate 一覧 + 詳細 | MVP は機能優先、ピクセルアートは後 |
| **Conversation ログ** | Stage 内の Agent 間対話を時系列表示 | デバッグ・履歴監査 |

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

## マイルストーン

| マイルストーン | 完了基準 |
|----|----|
| **M1: ドメイン骨格** | domain/ の Aggregate が pyright pass、ユニットテスト 80% カバレッジ |
| **M2: SQLite 永続化** | Repository 実装、Alembic マイグレーション、CRUD の結合テスト |
| **M3: HTTP API** | FastAPI router で全 Aggregate の CRUD が動く、OpenAPI で UI 開発開始可能 |
| **M4: WebSocket** | Domain Event の WebSocket ブロードキャスト、UI でリアルタイム反映 |
| **M5: LLM Adapter** | Claude Code CLI で 1 Stage を完走（Agent が deliverable を返す）|
| **M6: ExternalReviewGate UI** | 承認 / 差し戻しの人間操作、Discord 通知 |
| **M7: V モデル E2E** | Workflow プリセット → directive → 全 Stage 完走 → DONE |
| **v0.1.0 リリース** | release/0.1.0 ブランチ、CHANGELOG 確定、main マージ + tag |

## 受入基準（MVP 完了の判定）

1. UI から Empire / Room / Agent / Workflow を作成・編集・アーカイブできる
2. プリセットから V モデル開発室を 1 クリックで作成できる
3. CEO が `$` プレフィックスで directive を入力すると、対象 Room で Task が起票される
4. Task の current_stage が遷移すると、Agent（Claude Code CLI 経由）が deliverable を生成する
5. EXTERNAL_REVIEW Stage で Discord 通知が届き、UI で承認 / 差し戻し操作ができる
6. 差し戻すと Task が前段 Stage に戻り、複数ラウンドの Gate 履歴が保持される
7. すべての Stage が APPROVED で完了すると、Task は DONE になる
8. 再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される
9. WebSocket で UI がリアルタイム更新される（手動リロード不要）
10. `just check-all` がローカル / CI 双方で緑になる

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
