# syntax=docker/dockerfile:1
# 本番を想定した FastAPI イメージ。開発時はホストの venv + uvicorn --reload を使う。
#
# DATABASE_URL は実行時に渡す。未設定の場合は /app/data/app.db（SQLite）を使い、
# compose.yaml では /app/data に名前付き volume をマウントして永続化する。
# migration（alembic upgrade head）はアプリ起動時には実行せず、同じイメージの migrate サービスで実行する。

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# root 以外の実行ユーザー
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --no-create-home --home-dir /app app

# 実行時の依存のみ（pytest 等の開発用依存は含めない）
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# SQLite の保存先。名前付き volume は初回マウント時にこのディレクトリの所有者を引き継ぐ
RUN mkdir -p /app/data && chown app:app /app/data

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
