# 外部連携

bakufu が連携する外部システムと連携プロトコルを凍結する。各 feature の業務仕様（[`../features/<name>/feature-spec.md`](../features/)）が本書を引用して連携先を共有する。

## Phase 1（MVP）

| 連携先 | 目的 | プロトコル | 認証 |
|----|----|----|----|
| Claude Code CLI | Agent の LLM 実行 | subprocess + stdin/stdout（stream-json） | Claude Max plan OAuth（`~/.claude/`） |
| Discord | 外部レビュー依頼通知 | discord.py（websocket + REST） | Bot Token |
| GitHub | bakufu 成果物のリポ管理 | gh CLI / GitHub REST | gh OAuth トークン |
| pypi.org / npmjs.com / GitHub Releases | 開発ツール配布（uv / just / convco / lefthook / gitleaks / ruff / pyright / pip-audit / biome） | HTTPS + SHA256 検証 | 不要（公開 registry） |

## Phase 2 以降（拡張）

| 連携先 | 目的 |
|----|----|
| Codex CLI / Gemini API / OpenCode / Kimi / GitHub Copilot | マルチプロバイダ Agent |
| Slack / Telegram / iMessage / WhatsApp / Signal | メッセンジャー多対応 |
| BigQuery / GA4 / Drive / Gmail | アシスタント Room の連携機能（ai-team の `assistant` チャネル相当） |

## 関連

- [`system-context.md`](system-context.md) — システムコンテキスト図（連携の概観）
- [`non-functional.md`](non-functional.md) — 非機能要件（セキュリティ含む）
- [`../design/threat-model.md`](../design/threat-model.md) — 外部連携を含む脅威モデル
