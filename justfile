# bakufu justfile
# 開発フロー定義の Single Source of Truth。
# ローカルフック (lefthook) / CI ワークフロー / 開発者手動操作はすべてこのファイルのレシピを参照する。
# 詳細設計: docs/features/dev-workflow/detailed-design.md

set windows-shell := ["pwsh", "-Cu", "-c"]
set dotenv-load := false

# Show all recipes (default)
default:
    @just --list

# Check Python (ruff) and TypeScript (biome) formatting
fmt-check:
    uv run ruff format --check .
    pnpm biome format .

# Auto-fix Python (ruff) and TypeScript (biome) formatting
fmt:
    uv run ruff format .
    pnpm biome format --write .

# Lint Python (ruff) and TypeScript (biome)
lint:
    uv run ruff check .
    pnpm biome check .

# Type-check Python (pyright) and TypeScript (tsc)
typecheck:
    uv run pyright
    pnpm tsc --noEmit

# Run backend tests then frontend tests sequentially
test: test-backend test-frontend

# Run backend tests (pytest)
test-backend:
    uv run pytest backend/

# Run frontend tests (vitest)
test-frontend:
    pnpm --dir frontend vitest run

# Audit dependencies (pip-audit for Python, pnpm audit for Node)
audit:
    uv run pip-audit
    pnpm audit

# Scan staged changes for secrets (gitleaks)
audit-secrets:
    gitleaks protect --staged --no-banner

# Verify pin constants are synchronized between setup.sh and setup.ps1
audit-pin-sync:
    bash scripts/ci/audit-pin-sync.sh

# Run all quality gates sequentially (final check)
check-all: fmt-check lint typecheck test audit audit-secrets audit-pin-sync

# Validate commit message via convco (Conventional Commits 1.0)
[script("bash")]
commit-msg-check FILE:
    convco check --from-stdin --strip < {{FILE}}

# Reject AI-generated trailers in commit messages (3 patterns, case-insensitive)
[script("bash")]
commit-msg-no-ai-footer FILE:
    if grep -iqE '🤖.*Generated with.*Claude|Co-Authored-By:.*@anthropic\.com|Co-Authored-By:.*\bClaude\b' {{FILE}}; then
        exit 1
    fi
