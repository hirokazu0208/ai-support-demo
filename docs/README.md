# 設計ドキュメント

このディレクトリには、AI Support Desk の開発で**人間が承認した設計・技術判断・検証結果**を、Step 単位の設計資料として残しています。

## 方針

本プロジェクトは、人間が要件定義・設計承認・レビュー・受入判断を行い、AI（ChatGPT / Claude Code）を工程ごとに使い分けて開発しています。その過程を、後から読み返せる開発事例として残すことが目的です。

**残すもの**

- 各 Step の目的とスコープ（やること／やらないこと）
- 確定した設計（構成・API 仕様・設定）
- 技術判断と、その理由・検討した代替案
- 実施した検証と結果
- 次の Step への引き継ぎ事項

**残さないもの**

- AI との会話ログそのもの
- 採用しなかった試行錯誤の細部

**書くタイミング**

各 Step の実装・検証・受入が済んだ後に確定版を書き、実装と合わせて Git 管理します。

## 目次

### Demo 2（FastAPI + SQLAlchemy + SQLite）

| Step | 内容 | ドキュメント |
|---|---|---|
| Step 1 | FastAPI バックエンドの土台構築 | [step1-backend-foundation.md](demo2/step1-backend-foundation.md) |
| Step 2 | SQLAlchemy + SQLite + Alembic による DB 層 | [step2-database-layer.md](demo2/step2-database-layer.md) |
| Step 3 | 問い合わせの読み取り API（一覧・詳細） | [step3-read-api.md](demo2/step3-read-api.md) |
| Step 4 | 問い合わせの書き込み API（登録・ステータス変更） | [step4-write-api.md](demo2/step4-write-api.md) |
| Step 5 | Next.js frontend と FastAPI backend の接続 | [step5-frontend-api-integration.md](demo2/step5-frontend-api-integration.md) |
| Step 6A | frontend / backend の Docker 化と Docker Compose（DB は SQLite） | [step6a-docker.md](demo2/step6a-docker.md) |
| Step 6B | Docker Compose での PostgreSQL 化（SQLite / PostgreSQL の切り替え） | [step6b-postgresql.md](demo2/step6b-postgresql.md) |

### Demo 3（AI 問い合わせ支援 Agent）

| Step | 内容 | ドキュメント |
|---|---|---|
| Step 1 | FAQ のデータと検索 Tool（`faqs` テーブル・`GET /faqs`） | [step1-faq-search.md](demo3/step1-faq-search.md) |
| Step 2 | Agent API（RuleBasedAgent が FAQ 検索 Tool を呼ぶ `POST /agent/chat`） | [step2-agent-api.md](demo3/step2-agent-api.md) |

Demo 1（Next.js + モックデータ）の内容は [frontend/README.md](../frontend/README.md) にまとめています。
