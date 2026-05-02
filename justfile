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
    pnpm --filter @bakufu/frontend exec tsc --noEmit

# Run backend tests then frontend tests sequentially
test: test-backend test-frontend

# Run backend tests (pytest)
test-backend:
    uv run pytest backend/

# Run frontend tests (vitest)
test-frontend:
    pnpm --filter @bakufu/frontend exec vitest run

# Audit dependencies (pip-audit for Python, pnpm audit --prod for Node)
# pnpm audit は --prod 限定。dev-only 脆弱性（vitest 等）は配布バイナリに含まれないため監査対象外。
audit:
    uv run pip-audit
    pnpm audit --prod

# Scan staged changes for secrets (gitleaks)
audit-secrets:
    gitleaks protect --staged --no-banner

# Verify pin constants are synchronized between setup.sh and setup.ps1
audit-pin-sync:
    bash scripts/ci/audit-pin-sync.sh

# CI 三層防衛 (1/3): masking 対象カラムが Masked* TypeDecorator で
# 宣言されていることを strict 検証する (R1-D 補強条項 / storage.md §逆引き表).
audit-masking-columns:
    bash scripts/ci/check_masking_columns.sh

# Run all quality gates sequentially (final check)
check-all: fmt-check lint typecheck test audit audit-secrets audit-pin-sync audit-masking-columns

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

# ============================================================
# Docker Compose（統合起動環境）
# ============================================================

# Start backend + frontend containers (build if needed)
up:
    docker compose up --build -d

# Stop containers
down:
    docker compose down

# Stop containers and remove volumes (データ削除)
down-v:
    docker compose down -v

# Follow container logs
logs:
    docker compose logs -f

# Check backend health: GET http://localhost:8000/health → {"status":"ok"}
health:
    curl -sf http://localhost:8000/health

# Initialize .env files from .env.example (Unix)
[unix]
env-init:
    @[ -f backend/.env ] || cp backend/.env.example backend/.env && echo "✓ backend/.env initialized" || true
    @[ -f frontend/.env ] || cp frontend/.env.example frontend/.env && echo "✓ frontend/.env initialized" || true

# Initialize .env files from .env.example (Windows / PowerShell)
[windows]
env-init:
    @if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env; Write-Host "✓ backend/.env initialized" }
    @if (-not (Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env; Write-Host "✓ frontend/.env initialized" }
