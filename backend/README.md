# AI Support Desk — Backend

問い合わせ管理アプリの REST API です（Python / FastAPI）。Demo 2 で段階的に構築しています。

現在の到達点は **Demo 2 Step 2（SQLAlchemy + SQLite + Alembic による DB 層）** です。問い合わせテーブルと migration・seed、ヘルスチェック（`/health`・`/health/ready`）を提供します。問い合わせの API（`/inquiries`）はまだありません。

設計の詳細は以下を参照してください。

- [Step 1：FastAPI の土台構築](../docs/demo2/step1-backend-foundation.md)
- [Step 2：DB 層](../docs/demo2/step2-database-layer.md)

## 使用技術

- Python 3.11
- FastAPI / Uvicorn
- SQLAlchemy 2.1（2.x スタイル）/ Alembic（スキーマ管理）
- SQLite（将来 Azure Database for PostgreSQL へ移行できる構成）
- pydantic-settings（環境変数の読み込み）
- pytest / httpx2（テスト。FastAPI の TestClient が使用）

## ディレクトリ構成

```
backend/
├── alembic.ini
├── alembic/
│   ├── env.py             # 接続 URL は app.config から取得
│   └── versions/          # migration ファイル
├── app/
│   ├── main.py            # FastAPI アプリ本体・ルーター登録
│   ├── config.py          # 環境変数の読み込み（Settings）
│   ├── db/
│   │   ├── base.py        # DeclarativeBase・制約の命名規則
│   │   ├── session.py     # Engine・Session・get_db()
│   │   ├── sqlite.py      # SQLite 固有の設定（ここだけに隔離）
│   │   ├── types.py       # UTCDateTime（UTC で保存・取得する日時型）
│   │   ├── seed.py        # seed コマンド
│   │   └── seed_data.py   # Demo 1 の問い合わせ 8 件
│   ├── models/
│   │   └── inquiry.py     # Inquiry モデル・InquiryCategory・InquiryStatus
│   └── routers/
│       └── health.py      # GET /health, GET /health/ready
├── data/                  # SQLite の DB ファイル（app.db は Git 管理対象外）
├── tests/
├── requirements.txt       # 実行時の依存
├── requirements-dev.txt   # 開発・テスト用の依存（requirements.txt を含む）
└── .env.example           # 環境変数のサンプル
```

## セットアップ

以下は `backend/` ディレクトリで実行します。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # 任意。未作成の場合は既定値が使われます

# DB の作成（テーブルは Alembic migration で作成します）
alembic upgrade head

# Demo 1 の問い合わせ 8 件を投入（テーブルが空のときだけ投入。何度実行しても重複しません）
python -m app.db.seed
```

DB を初期状態に戻す場合:

```bash
alembic downgrade base && alembic upgrade head && python -m app.db.seed
```

## 起動

```bash
uvicorn app.main:app --reload --port 8000
```

| URL | 内容 |
|---|---|
| <http://localhost:8000/health> | liveness。プロセスが応答できれば `{"status":"ok"}`（DB は確認しない） |
| <http://localhost:8000/health/ready> | readiness。DB に接続できれば 200 `{"status":"ok"}`、できなければ 503 `{"status":"unavailable"}` |
| <http://localhost:8000/docs> | API ドキュメント（Swagger UI） |

## テスト

```bash
pytest -q
```

テストは一時ディレクトリの SQLite に Alembic migration を適用して実行します。`data/app.db` には触れません。

## migration の追加

```bash
alembic revision --autogenerate -m "<変更内容>"
# 生成されたファイルを必ずレビューしてから適用する
alembic upgrade head
alembic check   # モデルと migration に差分がないことを確認
```

autogenerate の結果はそのまま使わず、必ず内容を確認してください。Alembic 1.20.0 と SQLAlchemy 2.1 の組み合わせでは、Enum の CHECK 制約が重複して出力される既知の問題があります（[Step 2 設計記録](../docs/demo2/step2-database-layer.md) 参照）。

## 環境変数

| 変数名 | 既定値 | 説明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<backend の絶対パス>/data/app.db` | DB 接続 URL。既定値は起動ディレクトリによらず `backend/data/app.db` を指します |

- 環境変数 → `backend/.env` → 既定値の順で解決します。`.env` は Git 管理対象外です。
- SQLite の場所を変える場合は絶対パスで指定してください（`sqlite:////absolute/path/to/app.db`）。相対パスは起動ディレクトリ基準で解決されます。
