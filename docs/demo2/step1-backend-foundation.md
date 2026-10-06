# Demo 2 Step 1 — FastAPI バックエンドの土台構築

| 項目 | 内容 |
|---|---|
| 状態 | 完了 |
| 実施日 | 2026-10-06 |
| 前提 | Demo 2 Step 0（モノレポ構成への移行：`frontend/` への移動、ルート README・.gitignore の追加）完了 |

## 1. 目的とスコープ

Demo 2 では、Demo 1 のインメモリのモックデータを Python / FastAPI の REST API と SQLite による永続化に置き換えます。Step 1 では、その土台として **FastAPI アプリが起動し、`GET /health` が 200 を返す** ところまでを構築します。

**やること**

- `backend/` ディレクトリと FastAPI アプリの骨組み
- Python 仮想環境（venv）と依存パッケージの定義
- 環境変数の読み込み（`DATABASE_URL`）
- `GET /health` とその自動テスト（pytest）
- backend 用の `.gitignore`・`.env.example`・README
- 本設計記録

**やらないこと（後続 Step で実施）**

- SQLAlchemy の導入、SQLite DB の作成、テーブル定義
- Alembic によるマイグレーション
- Inquiry API（一覧・詳細・登録・ステータス変更）
- frontend との接続、CORS 設定

## 2. ディレクトリ構成

```
ai-support-demo/
├── backend/
│   ├── .gitignore
│   ├── .env.example
│   ├── README.md
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       └── health.py
│   └── tests/
│       ├── __init__.py
│       └── test_health.py
└── docs/
    ├── README.md
    └── demo2/
        └── step1-backend-foundation.md
```

| ファイル | 役割 |
|---|---|
| `app/main.py` | FastAPI インスタンスの生成とルーター登録。起動は `uvicorn app.main:app` |
| `app/config.py` | `pydantic-settings` の `Settings` で環境変数を読み込む |
| `app/routers/health.py` | `GET /health`。今後のルーター（inquiries 等）も `routers/` に同じ形で追加する |
| `tests/test_health.py` | `TestClient` による `/health` のテスト |
| `requirements.txt` | 実行時の依存 |
| `requirements-dev.txt` | `-r requirements.txt` ＋ テスト用の依存 |
| `.env.example` | 環境変数のサンプル（Git 管理対象） |
| `.gitignore` | backend 固有の除外設定 |

## 3. 技術判断

| 判断 | 理由 | 検討した代替案 |
|---|---|---|
| 仮想環境は標準の `venv`、依存管理は `pip` + `requirements*.txt` | 追加ツールなしで再現でき、Demo 1 の「標準機能で作る」方針と揃う | uv、Poetry（ツールの導入が別途必要。規模に対して過剰） |
| venv は `backend/.venv/` に作成 | backend 専用の環境であることが構成から明確。frontend の `node_modules/` と同じ考え方。エディタが自動認識しやすい | リポジトリ直下の `.venv/`（frontend と backend の境界があいまいになる） |
| 依存は直接指定したパッケージのみを `==` で固定 | 再現性を確保しつつ、ファイルを読みやすく保つ | `pip freeze` で推移的依存まで固定（行数が増え、意図が読み取りにくい） |
| 実行時の依存とテスト用の依存を分離 | 本番実行に不要なパッケージを入れないため | 1 ファイルにまとめる |
| 環境変数は `pydantic-settings` で読み込む | 型付きで検証でき、`.env` にも対応。FastAPI 公式ドキュメントでも推奨 | `os.environ` を直接参照、python-dotenv |
| `/health` は liveness（プロセスの応答確認）のみ | Step 1 では DB がないため。内部情報を返さない | DB 接続確認を含む readiness（DB 導入の Step で再検討） |
| SQLAlchemy は Step 1 では導入しない | Step ごとの差分を小さく保ち、DB 導入を独立した Step として記録するため | 先に依存だけ追加しておく |
| ルーターは `app/routers/` に分割 | `main.py` を登録処理だけに保ち、API が増えても構成を変えずに済む | `main.py` に直接エンドポイントを定義 |
| テストは Step 1 から pytest で導入 | 後続 Step の API テストの土台にするため | 手動確認（curl）のみ |
| `TestClient` の HTTP クライアントは `httpx2` を使う（当初は `httpx`。検証工程で変更、§6 参照） | Starlette 1.7.0 の `TestClient` が `httpx2` を優先し、`httpx` の利用を非推奨としているため | `httpx` のまま（非推奨警告が残り、将来の Starlette で動かなくなるおそれ） |

## 4. API 仕様：`GET /health`

| 項目 | 内容 |
|---|---|
| メソッド・パス | `GET /health` |
| 正常時の応答 | `200 OK`、`Content-Type: application/json` |
| レスポンス本文 | `{"status": "ok"}` |
| 応答の型 | `HealthResponse`（`status: Literal["ok"]`）。OpenAPI（`/docs`）に表示される |
| 認証 | なし |
| 確認する範囲 | プロセスが起動して応答できるか（liveness）。DB 接続は確認しない |
| 返さない情報 | バージョン、環境変数、`DATABASE_URL` など内部の情報 |

## 5. 環境変数

| 変数名 | 既定値 | Step 1 での扱い |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./app.db` | `Settings.database_url` に読み込むだけで、DB には接続しない（`app.db` も作られない） |

- 読み込む順番は、環境変数 → `backend/.env` → 既定値です。
- `.env.example` はコミットし、`.env` は Git 管理対象外にします。

## 6. 検証結果

確認日：2026-10-06（macOS / Python 3.11.9）

### インストールしたパッケージ

| パッケージ | バージョン | 区分 |
|---|---|---|
| fastapi | 0.142.2 | 実行 |
| uvicorn[standard] | 0.54.0 | 実行 |
| pydantic-settings | 2.15.0 | 実行 |
| pytest | 9.1.1 | 開発 |
| httpx2 | 2.13.1 | 開発 |

主な推移的依存：starlette 1.7.0、pydantic 2.13.5

### 実施した確認

| 確認内容 | コマンド | 結果 |
|---|---|---|
| ヘルスチェック | `curl -i http://localhost:8000/health` | `HTTP/1.1 200 OK`、`content-type: application/json`、`{"status":"ok"}` |
| Swagger UI | `GET /docs` | 200 |
| OpenAPI 定義 | `GET /openapi.json` | パスは `/health` のみ、スキーマは `HealthResponse` |
| 未定義のパス | `GET /nope` | 404 |
| 自動テスト | `pytest -q` | 1 passed、警告なし（`httpx2` へ変更後。下記参照） |
| 非推奨警告がないことの確認 | `pytest -q -W error::DeprecationWarning` | 1 passed |
| 環境変数の既定値 | `settings.database_url` | `sqlite:///./app.db` |
| 環境変数による上書き | `DATABASE_URL=... python -c ...` | 指定した値が反映される |
| `.env` からの読み込み | 一時的に `backend/.env` を作成して確認（確認後に削除） | `.env` の値が反映される |
| Git 管理対象外の確認 | `git check-ignore -v` | `.venv/`、`__pycache__/`、`.pytest_cache/`、`.env`、`*.db`（`backend/data/app.db` を含む）が除外され、`.env.example` は管理対象 |

### 検証で見つかった問題：TestClient の非推奨警告と httpx2 への変更

**見つかった問題**

設計段階では、テスト用の依存として `httpx`（0.28.1）を採用していました。FastAPI の `TestClient` が内部で使うためです。しかし最初の検証で `pytest` を実行したところ、テストは通ったものの次の警告が 1 件出ました。

```
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

**原因**

Starlette 1.7.0 の `starlette/testclient.py` は、まず `httpx2` を読み込もうとし、見つからなかった場合にだけ `httpx` を使ったうえで、この警告を出す作りになっていました。`fastapi.testclient.TestClient` は Starlette の `TestClient` をそのまま公開しているので、FastAPI でも同じ動きになります。

**判断**

テスト用の依存を `httpx` から `httpx2`（2.13.1）に変更しました（人間がレビューで承認）。

- 非推奨の経路を使い続けると、将来 Starlette を更新したときに `TestClient` が動かなくなるおそれがあります。
- `httpx2` は Starlette 自身が案内している移行先です。パッケージのメタデータを見て、pydantic の GitHub 組織が公開していること（作者は httpx と同じ Tom Christie 氏、ライセンスは BSD-3-Clause）を確認してから導入しました。
- テストコードは変更していません。引き続き `fastapi.testclient.TestClient` を使っています。

**反映した内容**

- `requirements-dev.txt` の `httpx==0.28.1` を `httpx2==2.13.1` に変更しました。
- 仮想環境に `httpx2` を入れ、`httpx` と、`httpx` だけが使っていた `httpcore`・`certifi` を削除しました（`pip check` で依存関係に問題がないことを確認）。
- `pytest -q` が警告なしで 1 passed になりました。非推奨警告をエラーとして扱う `-W error::DeprecationWarning` を付けても通ります。

## 7. 次の Step への引き継ぎ

- **SQLite のファイルは `backend/data/app.db` に統一する（承認済みの方針）。** Step 2 で `DATABASE_URL` の既定値と `.env.example` を変更します。相対パスは起動したディレクトリによって指す場所が変わるため、パスの解決方法もあわせて設計します。`*.db` は `.gitignore` で除外済みです。
- `/health` に DB 接続の確認（readiness）を加えるかは、DB を導入する Step で判断します。
- CORS は frontend との接続方法（Server Component からのサーバー間通信かどうか）を決める Step で判断します。
