# Demo 3 Step 2 — Agent API と FAQ 検索 Tool の呼び出し

| 項目 | 内容 |
|---|---|
| 状態 | 実装・自動検証まで完了 |
| 実施日 | 2026-10-07 |
| 前提 | [Demo 3 Step 1](step1-faq-search.md)（FAQ のデータと検索）完了 |

## 1. 目的

利用者の質問を `POST /agent/chat` で受け取り、Agent が FAQ 検索 Tool を使って回答する、最小の構成を作ります。

```
POST /agent/chat → routers/agent.py → Agent（RuleBasedAgent）→ FAQ 検索 Tool（tools/faq_search.py）
                                                                 → search_faqs()（repositories/faqs.py）→ faqs テーブル
```

**この Step では外部の LLM に接続しません。** ルールベースの Agent で、Agent・Tool・API の責務の分け方を完成させます。LLM の Agent（Step 5）には、同じインターフェースのまま差し替えます。

**変更していないもの：** frontend、問い合わせと FAQ の API の仕様、DB の構造（migration の追加なし）、Compose の構成とポートの公開方針、`backend/data/app.db`。API キーも追加していません。

## 2. 構成と責務

| 層 | ファイル | 責務 | 持たないもの |
|---|---|---|---|
| API | `app/routers/agent.py` | リクエストの検証、Agent の選択（`get_agent()`）、応答の変換 | 判断のロジック、DB への直接のアクセス |
| Agent | `app/agents/base.py` | 共通のインターフェース（`Agent` の Protocol：`respond(session, message) -> AgentReply`）、`AgentAction`、`AgentReply`、`ToolCall` | — |
| Agent | `app/agents/rule_based.py` | どの Tool を呼ぶか、結果からどう答えるかを判断する（`RuleBasedAgent`） | 検索のアルゴリズム、SQL |
| Tool | `app/tools/faq_search.py` | Agent から業務の機能を呼ぶための**薄い層**。名前（`search_faqs`）、説明、引数のモデル（`FaqSearchArgs`）、実行する関数（`search_faq_tool`） | 検索のアルゴリズム（repository を呼ぶだけ） |
| repository | `app/repositories/faqs.py`（Step 1） | FAQ の検索のアルゴリズムと DB へのアクセス | — |
| スキーマ | `app/schemas/agent.py` | `AgentChatRequest`、`AgentChatResponse`（camelCase）、`ToolCallResponse` | — |

**決めごと**

- Agent は FAQ 検索を **Tool を通して**呼びます。repository の `search_faqs()` を直接は呼ばず、自分の `GET /faqs` に HTTP で問い合わせることもありません。テスト `test_agent_calls_faq_search_through_tool_layer` で、呼び出しが Tool を経由していることを確かめています。
- 検索のアルゴリズム（`score_faq`、`normalize`）と DB へのアクセス（`select`、`Faq`）は、repository にしか存在しません。テスト `test_agents_and_tools_do_not_reimplement_faq_search` で、`agents/` と `tools/` の import と関数の定義を構文解析し、これを確かめています。
- `GET /faqs` と Agent の応答は、どちらも `FaqResponse.from_match()` で検索結果を応答の形に変換します。Step 1 のルーターにあった変換の処理をここに移しました（`GET /faqs` の応答は変わりません）。

## 3. API の仕様：`POST /agent/chat`

**リクエスト**

```json
{ "message": "VPNがすぐ切れます" }
```

| 項目 | 検証 |
|---|---|
| `message` | 必須、文字列。前後の空白を除いて 1〜1000 文字（空白だけなら 422） |
| そのほかの項目 | 422（`extra_forbidden`）。会話の履歴（`history`）は Step 2 では受け付けない |

**応答（200）**

```json
{
  "message": "「VPN が頻繁に切断されます」の FAQ が見つかりました。\n\nVPN クライアントを最新版に更新し、…\n\n解決しない場合は、問い合わせとして登録できます。",
  "action": "FAQ_ANSWER",
  "matchedFaqs": [
    { "id": 6, "question": "VPN が頻繁に切断されます", "answer": "…", "category": "NETWORK", "score": 3 }
  ],
  "toolCalls": [
    { "name": "search_faqs", "arguments": { "query": "VPNがすぐ切れます", "limit": 3 } }
  ]
}
```

| 項目 | 内容 |
|---|---|
| `message` | Agent の回答（改行を含む文字列） |
| `action` | `FAQ_ANSWER`（FAQ をもとに回答した）または `INQUIRY_SUGGESTED`（FAQ で解決できず、問い合わせの登録を提案した）。値の書き方は、既存の `InquiryStatus` と同じく大文字のスネークケース |
| `matchedFaqs` | FAQ 検索 Tool の結果（`GET /faqs` と同じ形）。最大 3 件 |
| `toolCalls` | Agent が呼んだ Tool の名前と引数。デモの画面で「どの Tool を使ったか」を見せるためと、デバッグのため |

| 状態 | 条件 |
|---|---|
| 200 | 正常（FAQ が見つからなくても 200 で、`action` が `INQUIRY_SUGGESTED`） |
| 422 | 検証エラー、JSON でない本文 |
| 500 | DB の障害（本文は `Internal Server Error` だけで、内部の情報は返さない） |

**会話の状態は保持しません**（会話のテーブルは作っていません）。読み取りだけなので、commit もしません。

## 4. RuleBasedAgent の判断のロジック

1. 利用者のメッセージ（前後の空白を除いたもの）を引数に、FAQ 検索 Tool を `limit=3` で呼ぶ（`toolCalls` に記録する）。
2. 一致した FAQ があれば `FAQ_ANSWER` を返す。回答は、最上位の FAQ の質問と回答に、2 件目以降を「関連する FAQ」として添え、最後に「解決しない場合は、問い合わせとして登録できます。」を付ける。
3. 一致がなければ（FAQ のテーブルが空の場合も）、`INQUIRY_SUGGESTED` と、「FAQ では解決できませんでした。問い合わせとして登録すると、ヘルプデスクの担当者が対応します。」を返す。

**RuleBasedAgent を採用した理由**

- API キー、ネットワーク、料金、応答の遅さに左右されずに、面談のデモを確実に最後まで動かせる。
- 応答が決まっているので、テストで期待値をはっきり確かめられる（SQLite と PostgreSQL の両方で、同じ結果になることも確認済み）。
- Agent・Tool・API の境界を先に決めておけば、Step 5 では「頭脳」だけを差し替えれば済む。

## 5. 将来 LLM の Agent に交換するときの変更点

| 交換する箇所 | 内容 |
|---|---|
| `app/agents/` に `llm.py` を追加 | `Agent` の Protocol（`respond(session, message) -> AgentReply`）を実装する。LLM に Tool の定義を渡し、Tool の呼び出しを実行して、結果を LLM に返すループにする |
| Tool の定義 | `tools/faq_search.py` の `NAME`、`DESCRIPTION`、`FaqSearchArgs.model_json_schema()` を、そのまま LLM の tool 定義に使う |
| `routers/agent.py` の `get_agent()` | 設定（例：`AGENT_PROVIDER`）によって `RuleBasedAgent` か LLM の Agent を返す。テスト `test_agent_can_be_replaced_via_dependency` で、ここを差し替えられることを確かめている |
| 変えないもの | API の仕様（`AgentChatRequest` と `AgentChatResponse`）、Tool、repository、frontend（Step 3 以降） |
| 安全策（Step 5 で実装） | LLM がエラーやタイムアウトになったら、`RuleBasedAgent` で応答する |

## 6. テスト

**追加したテスト（24 件）**

| ファイル | 件数 | 内容 |
|---|---|---|
| `tests/agents/test_rule_based_agent.py` | 7 | FAQ が見つかる（VPN、action、回答の本文、`toolCalls`）、複数の FAQ（点数の順、関連する FAQ の案内）、`matched_faqs` が Tool（repository）の結果と一致、FAQ が見つからない、FAQ のテーブルが空、Tool の層を経由した呼び出し（スパイで引数 `(query, limit)` を確認）、`agents/` と `tools/` が検索や DB アクセスを重複して実装していない（構文解析で確認） |
| `tests/test_agent_api.py` | 17 | VPN（200、camelCase のキー、id 6、NETWORK、点数 3、`toolCalls`）、パスワード、複数の FAQ、FAQ なし（`INQUIRY_SUGGESTED` と `[]`）、前後の空白の除去、1000 文字は受け付ける、422（項目なし、空文字、空白だけ（全角スペースや改行を含む）、1001 文字、型の誤り、未定義の項目の 6 パターン）、JSON でない本文は 422、`get_agent()` の差し替え、DB の障害時は 500 で情報を漏らさない、既存の `/faqs` と `/inquiries` が動くこと、OpenAPI（`/agent/chat`、`additionalProperties: false`、`maxLength: 1000`、`AgentAction` の enum） |

**結果**

| 確認内容 | 結果 |
|---|---|
| ホストでの pytest（SQLite） | **168 passed**（既存の 144 件と追加の 24 件）。非推奨警告をエラー扱いにしても 168 passed |
| PostgreSQL 18（`docker compose --profile test run --rm backend-test`） | **168 passed**。非推奨警告をエラー扱いにしても 168 passed |
| `alembic check` | 一時 SQLite と Compose の PostgreSQL のどちらも `No new upgrade operations detected.`（DB の構造は変えていない） |

## 7. Docker Compose での確認結果

既存の `pgdata`（Step 1 で seed 済み）に対して `docker compose up -d --build` を実行しました。終了コードは 0 で、db、migrate、backend、frontend の順に起動し、すべて healthy でした。seed を再び実行すると、問い合わせも FAQ もスキップされました。

frontend のコンテナから `http://backend:8000/agent/chat` を呼んで確かめました。

| メッセージ | 結果 |
|---|---|
| 「VPNがすぐ切れます」 | 200、`FAQ_ANSWER`、`matchedFaqs` は `[[6, 3, "NETWORK"]]`。回答は「「VPN が頻繁に切断されます」の FAQ が見つかりました。」と VPN の対処法 |
| 「パスワードを忘れました」 | 200、`FAQ_ANSWER`、`matchedFaqs` は `[[1, 6, "ACCOUNT"]]`（パスワードの FAQ） |
| 「宇宙旅行に行きたいです」 | 200、`INQUIRY_SUGGESTED`、`matchedFaqs` は `[]`。回答は「FAQ では解決できませんでした。…」 |
| 空白だけ | 422 |

| 既存の機能・方針 | 結果 |
|---|---|
| `GET /inquiries`（内部から） | 200、8 件（7, 6, 5, 8, 3, 2, 1, 4） |
| `GET /faqs?q=VPN`（内部から） | 200、id 6 |
| ホスト → `localhost:3000/inquiries` | 200 |
| ホスト → `localhost:8000`、`localhost:5432` | 接続できない（ホストで待ち受けているのは 3000 番だけ） |

ほかに影響していないことも確かめました。frontend の差分は 0 件です。`backend/data/app.db` は SHA-256 が `9641ac22…4440`、更新時刻が `Oct 6 23:24:13` で、変わっていません。`git diff --check` も問題ありませんでした。

## 8. 見つかった問題と対応

### テストの期待値の誤り（実装は正しかった）

- **現象：** `test_faq_answer_for_vpn` で、点数を 6 と期待していたのに、実際は 3 でした。
- **原因：** 「VPNがすぐ切れ**ます**」には、キーワードの「切れ**る**」が含まれません。そのため一致するのは「VPN」だけです。Step 1 で、Compose から「VPNがすぐ切れ**る**」を検索したときの点数（6）を、そのまま期待値にしてしまいました。
- **対応：** 期待値を 3 に直し、理由をコメントに書きました。選ばれる FAQ（id 6）は期待どおりです。

活用形の違い（「切れる」と「切れます」）を吸収したくなった場合は、seed のキーワードに「切れ」のような語幹を加えるか、Step 5 の LLM や形態素解析に任せます。Step 2 では、検索の仕様（Step 1）は変えていません。

## 9. Step 3 への引き継ぎ

- frontend は `POST /agent/chat` を Server Action から呼びます（ブラウザは FastAPI を直接呼ばない）。応答の `action` で表示を出し分けます（`INQUIRY_SUGGESTED` なら、Step 4 で「問い合わせとして登録」へつなげる）。
- `toolCalls` を画面に小さく表示すると、面談で「Agent が Tool を呼んだこと」を見せられます。
- 会話の履歴（`history`）は、Step 2 では受け付けていません。複数の発言をまたぐ文脈が必要になったら（Step 4 の起票案、または Step 5 の LLM）、リクエストに追加することを検討します。
