# 面談デモ手順書（約 5 分）

AI Support Desk の Demo 3（AIサポート）を、5 分で説明・実演するための台本です。
画面は Docker Compose（PostgreSQL）環境の http://localhost:3000 を使います。起動・停止は [最後のチートシート](#起動停止チートシート) を参照してください。

> 事前に開いておくタブ: ① http://localhost:3000/chat ② http://localhost:3000/inquiries ③ GitHub またはターミナル（`git log --oneline`）④ README の構成図

---

## 0:00〜0:30 プロジェクト概要

| 操作 | 見せる画面 |
|---|---|
| README の冒頭を表示 | プロジェクト名・1 行説明・構成図 |

**説明**

> 社内ヘルプデスク向けの問い合わせ管理システムです。Next.js・FastAPI・PostgreSQL で一覧・詳細・登録・ステータス変更を作り、そこに Tool を使う AI Agent を追加しました。
> 利用者がチャットで困りごとを入力すると、Agent が FAQ を検索して回答し、解決しない場合は問い合わせの起票案を作ります。登録は人が確認してから行います。

## 0:30〜1:30 アーキテクチャ説明

| 操作 | 見せる画面 |
|---|---|
| README の構成図を表示 | Browser → Next.js → FastAPI → Agent（search_faqs / draft_inquiry）→ PostgreSQL |

**説明（ポイントを 3 つ）**

1. **ブラウザは Next.js とだけ通信します。** チャットの送信は Server Action で、FastAPI は Next.js のサーバー側から呼びます。FastAPI と PostgreSQL はホストに公開しておらず、公開ポートは 3000 のみ、CORS も不要です。
2. **Agent と Tool を分けています。** Agent は「どの Tool を使うか」を決めるだけで、FAQ 検索は `search_faqs`、起票案の作成は `draft_inquiry` という Tool に分離しています。Tool は既存の業務ロジック（repository）を再利用する薄い層です。
3. **現在の Agent はルールベース（RuleBasedAgent）です。** LLM に依存せず、Tool の契約と業務フローを先に固めました。Agent は共通インターフェースで、後から LLM 実装に差し替えられる構造です。

## 1:30〜2:15 FAQ 回答デモ

| 操作 | 見せる画面 |
|---|---|
| ヘッダーの「AIサポート」→ `/chat` | チャット画面 |
| 「**VPNがすぐ切れます**」と入力して送信 | Agent の回答「「VPN が頻繁に切断されます」の FAQ が見つかりました。」と対処法、FAQ カード（カテゴリ: ネットワーク、一致度）、小さな表示「使用した Tool: search_faqs」 |

**説明**

> Agent が FAQ 検索 Tool を呼び、PostgreSQL の FAQ から一致度の高いものを選んで回答しています。どの Tool を使ったかは画面下に表示しています。FAQ で解決できる場合は起票案は作りません。

## 2:15〜4:00 問い合わせ起票デモ（Human-in-the-loop）

| 手順 | 操作 | 見せる画面 |
|---|---|---|
| 1 | 「**プリンタで両面印刷できません。**（改行）**問い合わせとして登録して**」と入力して送信 | 「問い合わせの起票案を作成しました。」「（まだ登録されていません）」、関連 FAQ カード（複合機で両面印刷ができません）、**問い合わせ起票案カード**（タイトル: プリンタで両面印刷できません／カテゴリ: その他／内容）、「まだ登録されていません」、「使用した Tool: **search_faqs, draft_inquiry**」 |
| 2 | （任意）タブ②の問い合わせ一覧で件数を見せる | 「N件」 |
| 3 | 起票案カードの「**内容を確認して登録へ**」 | `/inquiries/new` に起票案が初期入力され、「AIサポートが作成した起票案を入力しました。…（まだ登録されていません）」と表示 |
| 4 | タイトルを少し修正（例: 末尾に「（3階複合機）」） | 人が修正できること |
| 5 | 「登録する」 | 登録された問い合わせの詳細画面へ移動 |
| 6 | 一覧へ戻る | 件数が 1 件増え、先頭に表示 |

**説明**

> 登録を頼まれたので、Agent は FAQ 検索 Tool で関連 FAQ を示したうえで、起票案 Tool を選んでタイトル・カテゴリ・内容の起票案を作りました。
> ただし AI は登録しません。起票案は既存の登録画面に引き継ぐだけで、この時点では DB に入っていません。人が内容を確認・修正して「登録する」を押したときだけ、既存の POST /inquiries で登録されます。
> 登録経路を既存 API の 1 本に保つことで、バリデーションやエラー処理をそのまま使え、誤登録も防げます。

（時間があれば）「**宇宙旅行に行きたいです**」→ FAQ なしでも起票案が作られることを見せる。

## 4:00〜4:30 Git 履歴・AI 駆動開発の説明

| 操作 | 見せる画面 |
|---|---|
| `git log --oneline` または GitHub のコミット一覧 | Step ごとの `feat` / `refactor` / `docs` コミット |
| `docs/README.md` | Demo ごと・Step ごとの設計記録の目次 |

**説明**

> Step ごとに「設計案 → 人が判断・承認 → Claude Code が実装 → 自動テスト・E2E → 不具合修正 → 人が差分と結果を確認 → 手動コミット」で進めました。
> 設計判断・検証結果・見つかった問題と対応は docs に残しています。AI が作ったものを人がレビューし、テストで裏付けてから取り込む流れです。

## 4:30〜5:00 今後の LLM 接続について

**説明**

> 次の段階は LLM の接続です。Tool は名前・説明・引数の JSON Schema を持っているので、LLM の tool calling 定義にそのまま渡せます。Agent の差し替えは get_agent() の 1 か所で、API・Tool・画面は変えません。
> LLM が失敗した場合はルールベースに戻す、LLM でも DB には直接書かず起票案までにする、という方針を維持します。プロバイダ（Azure OpenAI など）はこれから決める段階で、まだ実装していません。

---

## 想定 Q&A

**Q. これは本当に AI Agent ですか？**
A. 現在の Agent はルールベースで、LLM は使っていません。ただし「利用者の入力から、どの Tool を使うかを判断し、Tool の結果をもとに応答する」という Agent の構造（Agent・Tool・API の分離、Tool の呼び出し記録）は実装しています。判断部分を LLM に置き換えるのが次の段階です。

**Q. なぜ最初から LLM を使っていないのですか？**
A. Tool の契約と業務フロー（特に Human-in-the-loop）を先に固め、テストで確実に検証するためです。ルールベースなら結果が決まるので期待値をテストでき、API キーやネットワーク・コストに左右されずにデモも安定します。LLM はその上で「判断部分」だけを差し替えます。

**Q. Agent と普通の API の違いは？**
A. 普通の API は呼び出し側が処理を決めます。Agent は入力に応じて使う Tool を選び、複数の Tool の結果を組み合わせて応答します。この実装では、同じ `POST /agent/chat` でも、FAQ 回答だけの場合（search_faqs）と起票案まで作る場合（search_faqs + draft_inquiry）があり、応答の `toolCalls` に何を使ったかが残ります。

**Q. Tool とは何ですか？**
A. Agent が呼び出せる業務機能の単位です。ここでは名前・説明・引数モデル（JSON Schema）・実行関数を持つ Python モジュールで、中身は既存の repository などを呼ぶ薄い層です。検索アルゴリズムなどの業務ロジックを Tool や Agent に重複実装しないよう、テストで確認しています。

**Q. なぜ Agent から直接 DB 登録しないのですか？**
A. AI の出力は誤りうるため、業務データの登録には人の確認を入れる Human-in-the-loop にしました。また登録経路を既存の `POST /inquiries` 1 本に保つことで、既存のバリデーション・トランザクション・エラー処理を再利用できます。Agent の応答処理中に INSERT/UPDATE/DELETE が発生しないことはテストで確認しています。

**Q. なぜ Next.js からブラウザで FastAPI を直接 fetch しないのですか？**
A. FastAPI の URL や内部ネットワークをブラウザに公開せず、FastAPI と DB をホストに公開しない構成にするためです。ブラウザは Next.js だけと通信し、Server Action / Server Component から FastAPI を呼びます。CORS も不要になり、公開ポートは 3000 のみです。ブラウザ向けバンドルに backend の URL が含まれないことも確認しています。

**Q. PostgreSQL にした理由は？**
A. 将来 Azure Database for PostgreSQL へ移行する前提で、Docker Compose では PostgreSQL 18 を使っています。ホストでの開発と通常のテストは SQLite のままで、`DATABASE_URL` で切り替えます。全テスト（209 件）を SQLite と PostgreSQL の両方で実行しています。

**Q. Azure へ持っていく場合は？**
A. frontend・backend の Docker イメージを Azure Container Apps などで動かし、DB は Azure Database for PostgreSQL Flexible Server（18）に `DATABASE_URL`（`sslmode=require`）で接続する想定です。migration は同じイメージの `alembic upgrade head` をジョブとして実行し、`/health`・`/health/ready` をプローブに使えます。backend は内部向けにして公開しない構成を維持します。まだデプロイはしていません。

**Q. Claude Code はどのように使いましたか？**
A. Step ごとに、Claude Code に既存コードと同梱ドキュメントを調査させて設計案を出させ、判断事項を私が選んで承認し、承認した範囲だけ実装させました。実装後は Claude Code にテスト・ビルド・Docker 上の E2E まで実行させ、結果と差分を私が確認してから手動でコミットしています。

**Q. AI が生成したコードをどう品質保証しましたか？**
A. backend は pytest 209 件を SQLite と PostgreSQL の両方で実行し、Alembic でモデルと migration の差分も確認しています。frontend は型チェック・lint・本番ビルド、さらに Docker Compose 上でヘッドレス Chrome を操作する E2E で、FAQ 回答・起票案・登録画面への引き継ぎ・人の操作時だけ DB 件数が増えること・障害時の安全なエラー表示を確認しました。テストが通るように仕様を変えるのではなく、失敗したら原因を調べて修正し、その経緯を docs に残しています。

**Q. 今後 LLM を接続するならどうしますか？**
A. 同じ Agent インターフェースで LLM Agent を実装し、既存 Tool の JSON Schema を tool calling に渡します。`get_agent()` で設定に応じて切り替え、LLM の失敗時はルールベースに戻します。API キーは backend の環境変数のみに置き、frontend には渡しません。LLM でも DB には書かず、起票案までに留める方針は変えません。

---

## 起動・停止チートシート

すべてリポジトリ直下（`ai-support-demo/`）で実行します。Docker Desktop を起動しておきます。

### 面談直前

```bash
# 1. 起動（初回のみ cp .env.example .env で .env を用意。既にある場合は不要）
docker compose up -d --build

# 2. 4 サービスの状態を確認（db / backend / frontend が healthy、migrate が Exited (0)）
docker compose ps -a

# 3. 初期データ（空のときだけ投入。既にあればスキップされる）
docker compose run --rm backend python -m app.db.seed

# 4. ブラウザで開く
open http://localhost:3000/chat
```

うまく表示されない場合の確認:

```bash
docker compose logs --tail=50 backend
docker compose logs --tail=50 frontend
```

### 面談終了後（データを残して停止）

```bash
docker compose down
```

- コンテナは削除されますが、PostgreSQL のデータ（volume `ai-support-desk_pgdata`）は残ります。次回は `docker compose up -d` で同じデータのまま再開できます。
- `docker compose down -v` は volume ごとデータを削除するため、面談終了時には使いません。
