# 面談デモ手順書（約 5 分）

AI Support Desk の Demo 3（AIサポート）を、5 分で説明・実演するための台本です（Step 5：LLM Agent 対応版）。
画面は Docker Compose（PostgreSQL）環境の http://localhost:3000 を使います。デモは **`AGENT_PROVIDER=rule`（RuleBasedAgent）** で行います。外部 LLM API を呼ばないため、API キー不要・追加費用なし・結果が毎回同じで、面談中に安定して動きます。起動・停止は [最後のチートシート](#起動停止チートシート) を参照してください。

> 事前に開いておくタブ: ① http://localhost:3000/chat ② http://localhost:3000/inquiries ③ GitHub またはターミナル（`git log --oneline`）④ README の構成図 ⑤ [step5-llm-agent.md](step5-llm-agent.md) の Architecture（第 3 節）

---

## 0:00〜0:30 プロジェクト概要

| 操作 | 見せる画面 |
|---|---|
| README の冒頭を表示 | プロジェクト名・1 行説明・構成図 |

**説明**

> 社内ヘルプデスク向けの問い合わせ管理システムです。Next.js・FastAPI・PostgreSQL で一覧・詳細・登録・ステータス変更を作り、そこに Tool を使う AI Agent を追加しました。Agent は、ルールベースと LLM（OpenAI Responses API）を設定で切り替えられます。
> 利用者がチャットで困りごとを入力すると、Agent が FAQ を検索して回答し、解決しない場合は問い合わせの起票案を作ります。登録は人が確認してから行います。

## 0:30〜1:30 アーキテクチャ説明

| 操作 | 見せる画面 |
|---|---|
| README の構成図を表示 | Browser → Next.js → FastAPI → Agent（rule / openai）→ Tool（search_faqs / draft_inquiry）→ PostgreSQL |
| （任意）タブ⑤ の Architecture | `AGENT_PROVIDER` → RuleBasedAgent ／ FallbackAgent（LLMAgent → LLMClient → OpenAIResponsesClient、障害時は RuleBasedAgent） |

**説明（ポイントを 4 つ）**

1. **ブラウザは Next.js とだけ通信します。** チャットの送信は Server Action で、FastAPI は Next.js のサーバー側から呼びます。FastAPI と PostgreSQL はホストに公開しておらず、公開ポートは 3000 のみ、CORS も不要です。
2. **Agent と Tool を分けています。** Agent は「どの Tool を使うか」を決めるだけで、FAQ 検索は `search_faqs`、起票案の作成は `draft_inquiry` という Tool に分離しています。Tool は既存の業務ロジック（repository）を再利用する薄い層です。
3. **先に RuleBasedAgent で業務フローを固定しました。** LLM なしで Tool の契約と Human-in-the-loop の流れを作り、テストで期待値を固めてから、判断の部分だけを LLM に差し替えられるようにしました。
4. **LLM はプロバイダから分離しています。** LLMAgent は `LLMClient` という Protocol にだけ依存し、OpenAI 固有の処理は `OpenAIResponsesClient`（Adapter）に閉じ込めています。`AGENT_PROVIDER` を `openai` にすると LLM が Tool を選びますが、API・Tool・画面は同じです。今日のデモは費用のかからない rule で動かします。

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

## 4:00〜4:30 LLM Agent の安全設計（Tool Calling・fallback）

| 操作 | 見せる画面 |
|---|---|
| タブ⑤ の Tool Calling・Tool allowlist・Fallback（第 7・8・11 節） | 図と表 |

**説明**

> LLM に切り替えた場合も、LLM が呼べるのは許可リストの `search_faqs` と `draft_inquiry` の 2 つだけで、登録や更新の Tool は存在しません。引数は strict な JSON Schema とサーバー側の検証を通し、ループ回数・Tool の呼び出し回数・時間にも上限があります。
> 画面に出す FAQ や起票案は LLM の文章ではなく Tool の実行結果から作るので、LLM が FAQ をでっち上げても画面のカードにはなりません。
> タイムアウトやレート制限など LLM 側で障害が起きたときは、RuleBasedAgent に自動で切り替えて応答します。API キーは backend の環境変数だけに置き、frontend やイメージ、Git には入れていません。
> OpenAI の Adapter は、Mock と Fake を使ったテストまで実装済みです。実 API への接続は任意で、まだ行っていません。

## 4:30〜5:00 Git 履歴・AI 駆動開発の説明

| 操作 | 見せる画面 |
|---|---|
| `git log --oneline` または GitHub のコミット一覧 | Step ごとの `feat` / `refactor` / `docs` コミット |
| `docs/README.md` | Demo ごと・Step ごとの設計記録の目次 |

**説明**

> 生成 AI に全部任せたのではなく、設計・制約・レビュー・テストは私が管理し、実装の作業を Claude Code という AI Agent に任せました。
> Step ごとに「設計案 → 私が判断・承認 → 制約を明示して Claude Code に実装を指示 → 自動テスト・E2E → 不具合の原因調査と修正 → 私が差分と結果をレビュー → 手動でコミット」という流れです。たとえば「実 API を呼ばない」「API キーを frontend に渡さない」「Agent は DB に書かない」といった制約は私が決め、テストで守られていることを確認してから取り込んでいます。
> 設計判断・検証結果・見つかった問題と対応は docs に Step ごとに残しています。

---

## 想定 Q&A

**Q. これは本当に AI Agent ですか？**
A. Agent の構造（入力に応じて Tool を選び、Tool の結果から応答する。Agent・Tool・API の分離、Tool の呼び出し記録）は共通で、判断の部分を 2 通り実装しています。`AGENT_PROVIDER=openai` では LLM が tool calling で Tool を選ぶ LLM Agent になり、`rule`（既定・今日のデモ）では決まった手順で選びます。LLM Agent は Mock / Fake によるテストまで実装済みで、実 OpenAI API での動作確認はまだ行っていません。

**Q. なぜデモでは LLM を使わないのですか？**
A. 面談のデモは、追加費用がかからず、結果が毎回同じで、ネットワークや API の障害に左右されない rule で行っています。LLM の経路は、Fake の LLM クライアントと Mock の HTTP 通信で、tool calling・上限・タイムアウト・レート制限・認証エラー・フォールバックまでテストしています。実 API への接続は設定を変えるだけでできますが、任意としています。

**Q. なぜ最初に RuleBasedAgent を作ったのですか？**
A. Tool の契約と業務フロー（特に Human-in-the-loop）を先に固め、テストで確実に検証するためです。ルールベースなら結果が決まるので期待値をテストでき、その上で「判断の部分」だけを LLM に差し替えました。RuleBasedAgent は LLM 障害時のフォールバック先としても使っています。

**Q. LLM がおかしな Tool 呼び出しや嘘の回答をしたら？**
A. 呼べる Tool は許可リストの 2 つだけで、未知の Tool・不正な引数・上限を超えた呼び出しは実行しません。画面の FAQ カード・起票案・`action` は Tool の実行結果からコードで作るので、LLM の文章に書かれた FAQ や起票案は使いません。起票案には「まだ登録されていません」という案内を必ず付け、登録は人が行います。

**Q. LLM のプロバイダを変えるには？**
A. LLMAgent は `LLMClient` Protocol（`create_turn(request) -> turn`）にだけ依存しています。OpenAI 固有の処理は `OpenAIResponsesClient` に閉じ込めているので、別のプロバイダは Adapter を 1 つ追加するだけで、Agent・Tool・API・画面は変わりません。

**Q. Agent と普通の API の違いは？**
A. 普通の API は呼び出し側が処理を決めます。Agent は入力に応じて使う Tool を選び、複数の Tool の結果を組み合わせて応答します。この実装では、同じ `POST /agent/chat` でも、FAQ 回答だけの場合（search_faqs）と起票案まで作る場合（search_faqs + draft_inquiry）があり、応答の `toolCalls` に何を使ったかが残ります。

**Q. Tool とは何ですか？**
A. Agent が呼び出せる業務機能の単位です。ここでは名前・説明・引数モデル（JSON Schema）・実行関数を持つ Python モジュールで、中身は既存の repository などを呼ぶ薄い層です。検索アルゴリズムなどの業務ロジックを Tool や Agent に重複実装しないよう、テストで確認しています。

**Q. なぜ Agent から直接 DB 登録しないのですか？**
A. AI の出力は誤りうるため、業務データの登録には人の確認を入れる Human-in-the-loop にしました。また登録経路を既存の `POST /inquiries` 1 本に保つことで、既存のバリデーション・トランザクション・エラー処理を再利用できます。Agent の応答処理中に INSERT/UPDATE/DELETE が発生しないことはテストで確認しています。

**Q. なぜ Next.js からブラウザで FastAPI を直接 fetch しないのですか？**
A. FastAPI の URL や内部ネットワークをブラウザに公開せず、FastAPI と DB をホストに公開しない構成にするためです。ブラウザは Next.js だけと通信し、Server Action / Server Component から FastAPI を呼びます。CORS も不要になり、公開ポートは 3000 のみです。ブラウザ向けバンドルに backend の URL が含まれないことも確認しています。

**Q. PostgreSQL にした理由は？**
A. 将来 Azure Database for PostgreSQL へ移行する前提で、Docker Compose では PostgreSQL 18 を使っています。ホストでの開発と通常のテストは SQLite のままで、`DATABASE_URL` で切り替えます。全テスト（378 件）を SQLite と PostgreSQL の両方で実行しています。

**Q. Azure へ持っていく場合は？**
A. frontend・backend の Docker イメージを Azure Container Apps などで動かし、DB は Azure Database for PostgreSQL Flexible Server（18）に `DATABASE_URL`（`sslmode=require`）で接続する想定です。migration は同じイメージの `alembic upgrade head` をジョブとして実行し、`/health`・`/health/ready` をプローブに使えます。backend は内部向けにして公開しない構成を維持します。まだデプロイはしておらず、Step 5 の後に無料枠を中心にした別の工程として設計・デプロイする予定です。

**Q. Claude Code はどのように使いましたか？**
A. 生成 AI に全部任せたのではなく、設計・制約・レビュー・テストを私が管理し、実装の作業を Claude Code に任せました。Step ごとに Claude Code に既存コードと同梱ドキュメントを調査させて設計案を出させ、判断事項を私が選んで承認し、承認した範囲と制約（実 API を呼ばない、キーを frontend に渡さない、DB に書かない など）を明示して実装させました。実装後は Claude Code にテスト・ビルド・Docker 上の E2E まで実行させ、結果と差分を私が確認してから手動でコミットしています。

**Q. AI が生成したコードをどう品質保証しましたか？**
A. backend は pytest 378 件を SQLite と PostgreSQL の両方で（警告をエラー扱いにしても）実行し、Alembic でモデルと migration の差分も確認しています。frontend は型チェック・lint・本番ビルド、さらに Docker Compose 上でヘッドレス Chrome を操作する E2E で、FAQ 回答・起票案・登録画面への引き継ぎ・人の操作時だけ DB 件数が増えること・障害時の安全なエラー表示を確認しました。テストが通るように仕様を変えるのではなく、失敗したら原因を調べて修正し、その経緯を docs に残しています。

**Q. 実際に LLM を接続するには？ 費用は？**
A. `.env` に `AGENT_PROVIDER=openai`・`OPENAI_API_KEY`・`OPENAI_MODEL` を設定して再起動するだけです（キーは backend コンテナにだけ渡ります）。OpenAI API の利用料金がかかるため任意としています。費用と時間を抑えるため、1 回の応答での LLM の呼び出しは最大 4 回、出力は 1 回 800 トークンまで、応答全体は 20 秒（frontend の待機は 30 秒）を上限にしています。LLM の障害時は RuleBasedAgent で応答します。

---

## 起動・停止チートシート

すべてリポジトリ直下（`ai-support-demo/`）で実行します。Docker Desktop を起動しておきます。

### 面談直前

```bash
# 0. デモは rule で行う（.env の AGENT_PROVIDER が rule か未設定、OPENAI_API_KEY が空であること）
grep -E '^AGENT_PROVIDER=' .env     # 何も出ない、または AGENT_PROVIDER=rule

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
