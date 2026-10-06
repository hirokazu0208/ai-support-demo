# AI Support Desk — Backend

問い合わせ管理アプリの REST API です（Python / FastAPI）。Demo 2 で段階的に構築しています。

現在の到達点は **Demo 2 Step 4（問い合わせの書き込み API）** です。問い合わせの一覧・詳細の取得、登録、ステータス変更と、ヘルスチェック（`/health`・`/health/ready`）を提供します。frontend との接続はまだ行っていません。

設計の詳細は以下を参照してください。

- [Step 1：FastAPI の土台構築](../docs/demo2/step1-backend-foundation.md)
- [Step 2：DB 層](../docs/demo2/step2-database-layer.md)
- [Step 3：読み取り API](../docs/demo2/step3-read-api.md)
- [Step 4：書き込み API](../docs/demo2/step4-write-api.md)

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
│   ├── schemas/
│   │   └── inquiry.py     # API のリクエスト / レスポンス（JSON は camelCase）
│   ├── repositories/
│   │   └── inquiries.py   # 問い合わせのデータアクセス（SQL の組み立て・書き込みの commit / rollback）
│   └── routers/
│       ├── health.py      # GET /health, GET /health/ready
│       └── inquiries.py   # GET/POST /inquiries, GET /inquiries/{id}, PATCH /inquiries/{id}/status
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

## API

| メソッド・パス | 内容 |
|---|---|
| `GET /inquiries` | 一覧。作成日時の新しい順（同時刻は id の降順）。`q`（タイトル・本文の部分一致、大文字小文字を区別しない、最大 200 文字）と `status`（`OPEN` / `IN_PROGRESS` / `CLOSED`）で絞り込み。空白だけの `q` は指定なし扱い |
| `GET /inquiries/{id}` | 詳細。存在しない id は 404、整数でない・範囲外（1〜2147483647 以外）の id は 422 |
| `POST /inquiries` | 登録。本文は `title`（前後の空白を除いて 1〜100 文字）、`description`（同 1〜2000 文字）、`category`。status は `OPEN` 固定、`createdAt` と `updatedAt` は同じ時刻。成功時は 201 と `Location: /inquiries/{id}` |
| `PATCH /inquiries/{id}/status` | ステータス変更。本文は `status` のみ。変更した場合だけ `updatedAt` を更新し、同じ status なら何も更新せずに 200 を返す。存在しない id は 404 |

レスポンスの JSON は camelCase（`createdAt`・`updatedAt`）、日時は UTC の ISO 8601（例：`2026-09-28T00:15:00Z`）です。不正な `status`・`category`、定義していないクエリパラメータ・本文の項目（`id`・`status`・`createdAt` などのサーバーが決める項目を含む）は 422 になります。

```bash
curl -s "localhost:8000/inquiries?q=vpn&status=OPEN"
curl -s localhost:8000/inquiries/1
curl -s -X POST localhost:8000/inquiries -H "Content-Type: application/json" \
  -d '{"title":"プリンタが動かない","description":"3階の複合機","category":"OTHER"}'
curl -s -X PATCH localhost:8000/inquiries/9/status -H "Content-Type: application/json" \
  -d '{"status":"IN_PROGRESS"}'
```

POST・PATCH は DB に書き込みます。開発用の `data/app.db` を変更したくない場合は、`DATABASE_URL` を一時ファイルに向けてから `alembic upgrade head` と seed を実行してください。

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
