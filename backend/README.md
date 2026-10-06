# AI Support Desk — Backend

問い合わせ管理アプリの REST API です（Python / FastAPI）。Demo 2 で段階的に構築しています。

現在の到達点は **Demo 2 Step 1（FastAPI の土台構築）** です。ヘルスチェック用の `GET /health` のみを提供し、DB・問い合わせ API はまだありません。設計の詳細は [docs/demo2/step1-backend-foundation.md](../docs/demo2/step1-backend-foundation.md) を参照してください。

## 使用技術

- Python 3.11
- FastAPI / Uvicorn
- pydantic-settings（環境変数の読み込み）
- pytest / httpx2（テスト。FastAPI の TestClient が使用）

## ディレクトリ構成

```
backend/
├── app/
│   ├── main.py            # FastAPI アプリ本体・ルーター登録
│   ├── config.py          # 環境変数の読み込み（Settings）
│   └── routers/
│       └── health.py      # GET /health
├── tests/
│   └── test_health.py
├── requirements.txt       # 実行時の依存
├── requirements-dev.txt   # 開発・テスト用の依存（requirements.txt を含む）
└── .env.example           # 環境変数のサンプル
```

## セットアップ

以下はすべて `backend/` ディレクトリで実行します。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # 任意。未作成の場合は既定値が使われます
```

## 起動

```bash
uvicorn app.main:app --reload --port 8000
```

- ヘルスチェック: <http://localhost:8000/health> → `{"status":"ok"}`
- API ドキュメント（Swagger UI）: <http://localhost:8000/docs>

## テスト

```bash
pytest -q
```

## 環境変数

| 変数名 | 既定値 | 説明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./app.db` | DB 接続 URL。Step 1 では読み込みのみで、DB には接続しません |

環境変数 → `backend/.env` → 既定値の順で解決します。`.env` は Git 管理対象外です。
