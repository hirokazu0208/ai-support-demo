# syntax=docker/dockerfile:1
# FastAPI イメージ。開発時はホストの venv + uvicorn --reload を使う。
#
#   runtime（既定。最後のステージ）: 本番を想定した実行用イメージ。実行時の依存のみ
#   test: runtime と同じ内容に開発用依存とテストを加えたもの（compose.yaml の test プロファイルで使用）
#
# DATABASE_URL は実行時に渡す。未設定の場合は /app/data/app.db（SQLite）を使う。
# Docker Compose では PostgreSQL の DATABASE_URL を渡す（compose.yaml 参照）。
# migration（alembic upgrade head）はアプリ起動時には実行せず、同じイメージの migrate サービスで実行する。

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# root 以外の実行ユーザー
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --no-create-home --home-dir /app app

# 実行時の依存（psycopg[binary] を含む。コンパイラ等は不要）
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# SQLite を使う場合の保存先（DATABASE_URL 未設定時）
RUN mkdir -p /app/data && chown app:app /app/data


# テスト用（docker compose --profile test run --rm backend-test）
FROM base AS test
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests
USER app
# /app は root 所有で書き込めないため、pytest のキャッシュは作らない
CMD ["pytest", "-q", "-p", "no:cacheprovider"]


# 実行用（既定のビルド対象）
FROM base AS runtime
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
