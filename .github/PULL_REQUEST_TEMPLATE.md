## Summary

<!-- 変更内容を箇条書きで記述してください -->
-
-

## 種別

<!-- 該当するものにチェックを入れてください -->
- [ ] `feature/*` → `develop`（新機能・改善）
- [ ] `release/*` → `main`（リリース）
- [ ] `release/*` → `develop`（back-merge）
- [ ] `hotfix/*` → `main`（緊急修正）
- [ ] `hotfix/*` → `develop`（back-merge）

## 関連 Issue

<!-- Closes #XXX または Refs #XXX -->
Closes #

## チェックリスト

- [ ] PR タイトルが Conventional Commits に従っている（例: `feat(room): add workflow DAG validator`）
- [ ] `just lint` が通る（ruff + biome）
- [ ] `just typecheck` が通る（pyright + tsc）
- [ ] `just test` が通る（pytest + vitest）
- [ ] `uv.lock` / `pnpm-lock.yaml` のみが変更されている場合は `deps-lockfile-only` ラベルを付与し、意図的な更新である理由を本文に記載している

---

<!-- ▼ release/* または hotfix/* → main PR の場合のみ記入 ▼ -->

## リリース PR 責任確認（release/* / hotfix/* → main のみ）

> このセクションは `release/*` / `hotfix/*` → `main` PR の場合のみ記入してください。
> feature → develop PR では削除または空欄で構いません。

- [ ] バージョン bump（`backend/pyproject.toml` / `frontend/package.json`）が完了している
- [ ] `CHANGELOG.md` の内容を確認・校正済み
- [ ] **本 PR のマージから 24h 以内に `develop` への back-merge PR を作成する**（`back-merge-check` CI が監視します）

back-merge PR 予定: <!-- 作成済みの場合は PR リンクを貼ってください -->
