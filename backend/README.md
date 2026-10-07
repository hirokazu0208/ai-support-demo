# AI Support Desk — Backend

問い合わせ管理アプリの REST API です（Python / FastAPI）。Demo 2 で段階的に構築しています。

現在の到達点は **Demo 3 Step 5（LLM Agent）** です。問い合わせの一覧・詳細の取得、登録、ステータス変更、FAQ 検索、AI Agent との対話（`POST /agent/chat`。Agent が FAQ 検索 Tool と問い合わせ起票案 Tool を選んで呼ぶ。起票案は DB に保存せず、登録は人が既存の登録画面から行う）と、ヘルスチェック（`/health`・`/health/ready`）を提供し、frontend（Next.js）のサーバー側から呼び出されます。DB は `DATABASE_URL` で SQLite / PostgreSQL を切り替えます。Agent は `AGENT_PROVIDER` で RuleBasedAgent（既定。外部 LLM なし）と LLM Agent（OpenAI Responses API。Mock / Fake テストまで実装済みで、実 API への接続は任意）を切り替えます。

設計の詳細は以下を参照してください。

- [Step 1：FastAPI の土台構築](../docs/demo2/step1-backend-foundation.md)
- [Step 2：DB 層](../docs/demo2/step2-database-layer.md)
- [Step 3：読み取り API](../docs/demo2/step3-read-api.md)
- [Step 4：書き込み API](../docs/demo2/step4-write-api.md)
- [Step 6A：Docker 化](../docs/demo2/step6a-docker.md)
- [Step 6B：PostgreSQL 化](../docs/demo2/step6b-postgresql.md)
- [Demo 3 Step 1：FAQ 検索](../docs/demo3/step1-faq-search.md)
- [Demo 3 Step 2：Agent API](../docs/demo3/step2-agent-api.md)
- [Demo 3 Step 4：問い合わせ起票案 Tool](../docs/demo3/step4-inquiry-draft.md)
- [Demo 3 Step 5：LLM Agent](../docs/demo3/step5-llm-agent.md)

## 使用技術

- Python 3.11
- FastAPI / Uvicorn
- SQLAlchemy 2.1（2.x スタイル）/ Alembic（スキーマ管理）
- SQLite（ホストでの開発・既定のテスト）/ PostgreSQL 18 + psycopg 3（Docker Compose。将来 Azure Database for PostgreSQL へ移行）
- pydantic-settings（環境変数の読み込み）
- openai（OpenAI Responses API の SDK。`AGENT_PROVIDER=openai` のときだけ使用）
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
│   │   ├── seed_data.py   # Demo 1 の問い合わせ 8 件
│   │   └── faq_seed_data.py # FAQ 10 件
│   ├── agents/
│   │   ├── base.py        # Agent プロトコル・AgentAction・AgentReply・ToolCall
│   │   ├── rule_based.py  # RuleBasedAgent（どの Tool を呼ぶかを決める。外部 LLM なし）
│   │   ├── factory.py     # AGENT_PROVIDER から Agent を組み立てる
│   │   ├── fallback.py    # FallbackAgent（LLM の障害時は RuleBasedAgent で応答）
│   │   └── llm/
│   │       ├── client.py        # LLMClient Protocol・LLMRequest / LLMTurn・LLMError 系の例外
│   │       ├── agent.py         # LLMAgent（tool calling のループと上限）
│   │       ├── openai_client.py # OpenAIResponsesClient（openai SDK を使うのはここだけ）
│   │       └── prompts.py       # システム指示
│   ├── tools/
│   │   ├── faq_search.py  # FAQ 検索 Tool（repository の search_faqs() を呼ぶ薄い層）
│   │   ├── draft_inquiry.py # 問い合わせ起票案 Tool（登録依頼の判定・カテゴリ分類。DB には書かない）
│   │   └── registry.py    # LLM に公開する Tool の許可リスト（search_faqs / draft_inquiry のみ）
│   ├── models/
│   │   ├── inquiry.py     # Inquiry モデル・InquiryCategory・InquiryStatus
│   │   └── faq.py         # Faq モデル（category は InquiryCategory を再利用）
│   ├── schemas/
│   │   ├── inquiry.py     # API のリクエスト / レスポンス（JSON は camelCase）
│   │   ├── faq.py         # FAQ 検索の応答・クエリ
│   │   └── agent.py       # POST /agent/chat のリクエスト / レスポンス
│   ├── repositories/
│   │   ├── inquiries.py   # 問い合わせのデータアクセス（SQL の組み立て・書き込みの commit / rollback）
│   │   └── faqs.py        # FAQ 検索（キーワード + 部分一致のスコア方式）
│   └── routers/
│       ├── health.py      # GET /health, GET /health/ready
│       ├── inquiries.py   # GET/POST /inquiries, GET /inquiries/{id}, PATCH /inquiries/{id}/status
│       ├── faqs.py        # GET /faqs
│       └── agent.py       # POST /agent/chat（get_agent() で Agent 実装を選ぶ）
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

# Demo 1 の問い合わせ 8 件と FAQ 10 件を投入（テーブルごとに、空のときだけ投入。何度実行しても重複しません）
# Demo 3 より前に作成した DB では、先に alembic upgrade head で faqs テーブルを追加してください
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
| `GET /faqs?q=&limit=5` | FAQ 検索。キーワード + 部分一致のスコア順（同点は id 順）。`q` 未指定は id 順。`limit` は 1〜20、`q` は最大 200 文字。応答は `id`・`question`・`answer`・`category`・`score` |
| `POST /agent/chat` | AI Agent との対話。本文は `{"message": "..."}`（前後の空白を除いて 1〜1000 文字、未定義の項目は 422）。応答は `message`・`action`（`FAQ_ANSWER` / `INQUIRY_SUGGESTED` / `INQUIRY_DRAFTED`）・`matchedFaqs`・`toolCalls`・`inquiryDraft`（起票案。`InquiryCreate` と同じ制約、`INQUIRY_DRAFTED` 以外は `null`）。会話の状態は保持せず、問い合わせを登録しない |

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

PostgreSQL で実行する場合は、`TEST_DATABASE_URL` にテスト専用の DB を指定します（DB 名に `test` を含まない URL は拒否されます。各テストの開始時に `public` スキーマを作り直すため、開発用の DB を指定しないでください）。Docker Compose の test プロファイルを使うと、使い捨ての PostgreSQL で全テストを実行できます。

```bash
# リポジトリ直下で実行（.env が必要）
docker compose --profile test run --rm backend-test
```

## migration の追加

```bash
alembic revision --autogenerate -m "<変更内容>"
# 生成されたファイルを必ずレビューしてから適用する
alembic upgrade head
alembic check   # モデルと migration に差分がないことを確認
```

autogenerate の結果はそのまま使わず、必ず内容を確認してください。Alembic 1.20.0 と SQLAlchemy 2.1 の組み合わせでは、Enum の CHECK 制約が重複して出力される既知の問題があります（[Step 2 設計記録](../docs/demo2/step2-database-layer.md) 参照）。

## Docker

`backend/Dockerfile` は本番を想定したイメージです（`python:3.11-slim`、root 以外のユーザー `app`、実行時の依存のみ、テスト・`.env`・`data/` は含めない）。既定のビルド対象は `runtime` ステージで、`test` ステージ（開発用の依存とテストを追加）は PostgreSQL でのテスト実行にのみ使います。起動はリポジトリ直下の `compose.yaml` から行います（[README](../README.md#docker-compose-での起動)）。

```bash
# Compose 環境での seed・任意コマンド（コンテナは実行後に削除）
docker compose run --rm backend python -m app.db.seed
docker compose run --rm backend alembic current
```

Docker Compose では `DATABASE_URL`（PostgreSQL。ルートの `.env` から組み立て）を渡します。`DATABASE_URL` を渡さずにイメージを起動した場合は、既定値の `/app/data/app.db`（SQLite）を使います。

## 環境変数

| 変数名 | 既定値 | 説明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<backend の絶対パス>/data/app.db` | DB 接続 URL。既定値は起動ディレクトリによらず `backend/data/app.db` を指します。PostgreSQL は `postgresql+psycopg://user:password@host:5432/db`（Azure では `?sslmode=require`） |
| `TEST_DATABASE_URL` | なし（テストごとの一時 SQLite） | pytest 用。テスト専用の DB のみ（DB 名に `test` を含むこと） |
| `AGENT_PROVIDER` | `rule` | `rule`（RuleBasedAgent）/ `openai`（LLM Agent） |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | なし | `AGENT_PROVIDER=openai` のときだけ必須（不足していると起動時に検証エラー）。キーは frontend に渡さない |

- 環境変数 → `backend/.env` → 既定値の順で解決します。`.env` は Git 管理対象外です。
- SQLite の場所を変える場合は絶対パスで指定してください（`sqlite:////absolute/path/to/app.db`）。相対パスは起動ディレクトリ基準で解決されます。
- Agent の上限値（`AGENT_MAX_LLM_ROUNDS` など）と OpenAI の設定の一覧は [Step 5 の設計記録](../docs/demo3/step5-llm-agent.md#4-provider-switching) を参照してください。設定エラーのメッセージには入力値（API キーなど）を表示しません。
