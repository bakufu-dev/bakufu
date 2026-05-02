# bakufu frontend Dockerfile
# コンテキスト: リポジトリルート（docker-compose build context: .）
#
# ステージ構成:
#   dev    — Vite 開発サーバ。HMR 有効。docker-compose.override.yml で使用。
#   build  — pnpm build で静的ファイルを生成。
#   nginx  — build 成果物を nginx で配信（リリースビルド用）。
#
# 非 root ユーザー: node (uid=1000) — node:20-slim イメージ標準

# ===== dev stage =====
FROM node:20-slim AS dev

# ヘルスチェック用 netcat-openbsd をインストール（node:20-slim に nc は含まれないため）
# nc -z localhost 5173 で Vite 開発サーバの TCP port open を検査する（tech-stack.md §frontend ヘルスチェック）
RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# corepack で pnpm を有効化（node:20-slim に同梱）
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app

# pnpm workspace: root と frontend の package.json / lockfile を先にコピー（キャッシュ最適化）
# tsconfig.json を含める: frontend/tsconfig.json が "extends": "../tsconfig.json" で
# /app/tsconfig.json を参照するため必須（BUG-003）
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.json ./
COPY frontend/package.json frontend/

# 依存インストール（lockfile 厳密検証）
RUN pnpm install --frozen-lockfile

# アプリケーションソースをコピー
COPY frontend/ frontend/

WORKDIR /app/frontend

# USER 切り替え前に所有権を node (uid=1000) に移譲する
# COPY で配置したファイルは root 所有になるため、chown なしで USER node に切り替えると
# Vite が vite.config.ts と同一ディレクトリへ .timestamp-*.mjs を書き込む際に
# EACCES permission denied でクラッシュする（BUG-002）
RUN chown -R node:node /app

# 非 root ユーザー node (uid=1000) — node:20-slim の標準ユーザー
USER node

EXPOSE 5173

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD nc -z localhost 5173 || exit 1

# --host 0.0.0.0: コンテナ内全インターフェースにバインド。
# ホスト公開は docker-compose ports の "127.0.0.1:5173:5173" で制御する。
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

# ===== build stage =====
FROM node:20-slim AS build

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.json ./
COPY frontend/package.json frontend/

RUN pnpm install --frozen-lockfile

COPY frontend/ frontend/

WORKDIR /app/frontend

RUN pnpm build

# ===== nginx stage (リリースビルド配信) =====
FROM nginx:alpine AS nginx

COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
