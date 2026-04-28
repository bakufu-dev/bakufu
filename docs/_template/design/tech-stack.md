# 採用技術スタック

プロジェクトの採用技術と根拠を凍結する。新規依存追加時は本書を更新する。

## 採用技術

| 区分 | 採用技術 | バージョン | 根拠 |
|---|---|---|---|
| 言語（Backend） | \<Python / Node.js / Go / Rust\> | \<バージョン\> | \<選定根拠\> |
| 言語（Frontend） | \<TypeScript / JavaScript\> | \<バージョン\> | \<根拠\> |
| Backend Framework | \<FastAPI / Express / Gin / Actix\> | \<バージョン\> | \<根拠\> |
| Frontend Framework | \<React / Vue / Svelte\> | \<バージョン\> | \<根拠\> |
| ORM / DB Driver | \<SQLAlchemy / Prisma / GORM\> | \<バージョン\> | \<根拠\> |
| データベース | \<SQLite / PostgreSQL / MySQL\> | \<バージョン\> | \<根拠\> |
| パッケージ管理（Backend） | \<uv / poetry / npm / go mod\> | \<バージョン\> | \<根拠\> |
| パッケージ管理（Frontend） | \<pnpm / npm / yarn\> | \<バージョン\> | \<根拠\> |
| 型検査（Backend） | \<pyright / mypy / tsc\> | \<バージョン\> | \<根拠\> |
| Linter / Formatter | \<ruff / biome / eslint / prettier\> | \<バージョン\> | \<根拠\> |
| テスト | \<pytest / vitest / jest\> | \<バージョン\> | \<根拠\> |
| Git フック | \<lefthook / husky / pre-commit\> | \<バージョン\> | \<根拠\> |
| タスクランナー | \<just / make / npm scripts\> | \<バージョン\> | \<根拠\> |
| CI | \<GitHub Actions / GitLab CI\> | — | \<根拠\> |
| コンテナ | \<Docker / Podman\> | \<バージョン\> | \<根拠\> |

## 不採用ツール（議論済み）

| ツール | 不採用理由 |
|---|---|
| \<不採用ツール A\> | \<理由: 例 - 過剰機能、コミュニティ不足、ライセンス等\> |
| \<不採用ツール B\> | \<理由\> |

## 根拠の書き方ルール

- 「一般的だから」「標準だから」は禁止。具体的な要件（SLA / コスト / スケール / チーム習熟度等）に紐づけて書く
- 根拠が明確なら候補 1 つでもよい。複数候補がある場合は比較根拠を示す

## 関連

- [`architecture.md`](architecture.md) — システム全体構造
- [`../requirements/non-functional.md`](../requirements/non-functional.md) — 非機能要件（採用技術の制約）
