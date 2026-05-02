# bakufu backend Dockerfile
# コンテキスト: リポジトリルート（docker-compose build context: .）
#
# ステージ構成:
#   builder  — uv sync で venv を構築。pip を runtime に持ち込まない。
#   runtime  — venv + src のみコピー。非 root ユーザー bakufu (uid=1000) で実行。
#
# 起動コマンド: python -m bakufu.main
# （Bootstrap 経由で uvicorn をプロセス内起動。直接 uvicorn 起動は禁止）

# ===== builder stage =====
FROM python:3.12-slim AS builder

# uv を pip でインストール（builder 専用。runtime には持ち込まない）
RUN pip install --no-cache-dir uv

WORKDIR /app

# uv workspace の依存解決に必要なファイルを先にコピー（レイヤーキャッシュ最適化）
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/

# ソースは editable install のために必要
COPY backend/src/ backend/src/

# 本番依存のみ同期（dev group は除外）
RUN uv sync --frozen --no-dev

# ===== runtime stage =====
FROM python:3.12-slim AS runtime

# ヘルスチェック用 curl のみインストール。他のパッケージは持ち込まない。
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 非 root ユーザー bakufu (uid=1000, gid=1000) を作成
# USER bakufu を Dockerfile 末尾で強制し、root 所有ファイルをホスト側に作らない
RUN groupadd --gid 1000 bakufu \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin bakufu

WORKDIR /app

# builder から venv のみコピー（pip を runtime に持ち込まない）
COPY --from=builder /app/.venv /app/.venv

# アプリケーションソースをコピー（editable install の .pth が /app/backend/src を指す）
COPY --from=builder /app/backend/src /app/backend/src

# Alembic マイグレーションファイルをコピー
# Bootstrap stage 3 が /app/backend/alembic.ini を参照するため必須
# （src/ のみコピーでは CommandError: Path doesn't exist: /app/backend/alembic が発生する）
COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic/ backend/alembic/

# データディレクトリを事前作成し、bakufu (uid=1000) に所有させる
# volume mount 後もファイル所有者が uid=1000 になる（root 所有ファイルのホスト流出防止）
RUN mkdir -p /app/data \
    && chown -R bakufu:bakufu /app/data /app/.venv /app/backend

USER bakufu

# venv の bin を PATH に追加（uv を使わず python 直接起動）
ENV PATH="/app/.venv/bin:$PATH"

# データディレクトリ: コンテナ起動時は /app/data 固定（tech-stack.md §データディレクトリ）
ENV BAKUFU_DATA_DIR=/app/data

# バインドアドレス: コンテナ内全インターフェース。ホスト公開は docker-compose の
# "127.0.0.1:8000:8000" で制御（0.0.0.0 バインドはコンテナ内部のみ有効）
ENV BAKUFU_BIND_HOST=0.0.0.0
ENV BAKUFU_BIND_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Bootstrap 経由で uvicorn を起動（直接 uvicorn 起動は禁止 — マイグレーション等をスキップするため）
CMD ["python", "-m", "bakufu.main"]
