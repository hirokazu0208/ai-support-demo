# Demo 3 Step 4 — 問い合わせ起票案 Tool と Human-in-the-loop の登録導線

| 項目 | 内容 |
|---|---|
| 状態 | 実装・自動検証まで完了（ブラウザでの受入確認は人間が実施） |
| 実施日 | 2026-10-07 |
| 前提 | [Demo 3 Step 3](step3-chat-ui.md)（チャット UI と Agent API の接続）完了 |

## 1. 目的

FAQ で解決できない質問や、利用者がはっきり「問い合わせとして登録して」と頼んだ場合に、Agent が**問い合わせの起票案**を作ります。その起票案を人が確認し、既存の登録画面から登録する流れ（Human-in-the-loop）を完成させます。

```
利用者「プリンタで両面印刷できません。問い合わせとして登録して」
  → Agent（RuleBasedAgent）── search_faqs（関連する FAQ）
                           └─ draft_inquiry（起票案：タイトル・カテゴリ・内容）
  → チャット画面の起票案カード「内容を確認して登録へ」        ※ ここではまだ登録されない
  → 既存の /inquiries/new（起票案を初期値にする。人が確認・修正する）
  → 人が「登録する」を押す → 既存の createInquiryAction → 既存の POST /inquiries → PostgreSQL
```

**変更していないもの：** DB の構造（migration の追加なし）、`POST /inquiries` と登録の検証、FAQ 検索 Tool、Compose の構成とポートの公開方針、`backend/data/app.db`。CORS と API キーは追加していません。

## 2. Human-in-the-loop を採用した理由

- **AI は間違えることがある。** 起票案のタイトルやカテゴリを人が確認・修正できるようにします。問い合わせは担当者が対応する業務データなので、誤った登録や重複した登録を防ぎます。
- **登録の経路を 1 つに保つ。** 登録は既存の `POST /inquiries` だけにし、検証（`InquiryCreate` と frontend の `validation.ts`）、トランザクション、エラー処理をそのまま使います。Agent 用の書き込みの API は作りません。
- **責任の所在がはっきりする。** 「AI は起票を手伝い、確定は人が行う」という形は、業務システムに AI を入れるときに説明しやすい形です（面談でも説明できます）。

## 3. 責務の分担

| 層 | ファイル | 責務 | しないこと |
|---|---|---|---|
| Agent | `app/agents/rule_based.py` | **どの Tool を使うかを決める**（登録の依頼があるか → FAQ 検索 → 起票案）。応答の文言を組み立てる | 起票案の中身を作ること、DB への書き込み |
| Tool | `app/tools/draft_inquiry.py`（**新規**） | 登録の依頼の判定（`has_registration_request`）、依頼部分の除去（`strip_registration_request`）、カテゴリの分類（`classify_category`）、起票案の作成（`draft_inquiry_tool`）。名前は `draft_inquiry`、引数のモデルは `DraftInquiryArgs`（LLM 用の JSON Schema） | **DB へのアクセス**（Session を受け取らない）。問い合わせの登録 |
| Tool | `app/tools/faq_search.py`（変更なし） | FAQ 検索 | — |
| スキーマ | `app/schemas/inquiry.py` | `InquiryDraft`（`InquiryCreate` を継承）。`TITLE_MAX_LENGTH = 100` と `DESCRIPTION_MAX_LENGTH = 2000` を定数にして、`InquiryTitle`、`InquiryDescription`、Tool で共有する | — |
| 登録 | 既存の `/inquiries/new`、`createInquiryAction`、`POST /inquiries` | 人が確認したあとの登録 | — |

**Agent が DB に書き込まないことの保証（テスト）**

- `test_agent_never_writes_inquiries`：Agent が 3 種類のメッセージに応答する間に実行された SQL をすべて記録し、`INSERT`、`UPDATE`、`DELETE` が 1 つもないこと、問い合わせの件数が変わらないことを確かめます。
- `test_agents_and_tools_do_not_register_inquiries`：`agents/` と `tools/` が `app.repositories.inquiries`、`create_inquiry`、`update_inquiry_status`、`Inquiry` を import していないことを、構文解析で確かめます。
- `test_chat_does_not_create_inquiry_but_draft_can_be_registered`：チャットでは件数が増えないこと、起票案を人が `POST /inquiries` に送ると 201 で登録され、件数が 1 増えることを確かめます。

## 4. InquiryDraft の仕様

```json
"inquiryDraft": {
  "title": "プリンタで両面印刷できません",
  "description": "プリンタで両面印刷できません。",
  "category": "OTHER"
}
```

| 項目 | 制約（`InquiryCreate` から継承） | 作り方 |
|---|---|---|
| `title` | 前後の空白を除いて 1〜100 文字 | 依頼部分を除いた内容の**最初の文**（句点、感嘆符、疑問符、改行まで）。末尾の句読点は除き、100 文字（コードポイント単位）までに切る |
| `description` | 前後の空白を除いて 1〜2000 文字 | 依頼部分を除いた内容（改行を残す）。2000 文字までに切る |
| `category` | `InquiryCategory` | §5 |

`InquiryDraft` は `InquiryCreate` を継承した Pydantic のモデルで、Tool は最後に `InquiryDraft.model_validate()` で検証します。このため、起票案は**そのまま `POST /inquiries` で受け付けられる値**になります（テスト `test_draft_is_valid_inquiry_create`、API のテスト）。制約は 1 か所にしか定義していません。

## 5. カテゴリの分類のルール

既存の `InquiryCategory`（ACCOUNT / NETWORK / SOFTWARE / OTHER）を使います。HARDWARE はないので、enum は変えません。

| カテゴリ | キーワード（NFKC で正規化し、大文字小文字を区別せずに部分一致） |
|---|---|
| ACCOUNT | パスワード、ログイン、アカウント、多要素認証、MFA、二段階認証、権限、入社、退職 |
| NETWORK | VPN、Wi-Fi、WiFi、無線、ネットワーク、インターネット、LAN、回線 |
| SOFTWARE | Excel、Word、Office、Outlook、Teams、アプリ、ソフト、ライセンス、インストール |
| OTHER | 上のどれにも一致しない場合。**PC、プリンター、モニターなどの機器も OTHER**（既存の seed で、複合機の問い合わせと FAQ が OTHER になっていることに合わせる） |

**決め方：** 一致したキーワードの数が最も多いカテゴリを選びます。同じ数なら ACCOUNT → NETWORK → SOFTWARE の順に優先します。

**ご依頼の例との違い：** ご依頼の例ではプリンタの起票案が SOFTWARE になっていました。しかし既存のデータ（Demo 1 の問い合わせ「複合機で両面印刷ができない」と、FAQ 9）がどちらも OTHER なので、それに合わせて OTHER にしました。

## 6. 登録の依頼の判定

Unicode の NFKC で正規化したメッセージに、次のいずれかの言い回しが含まれていれば、登録の依頼と判定します（正規表現。過剰な自然言語処理はしません）。

| パターン | 例 |
|---|---|
| 問い合わせ（として／を）登録・起票・作成（して／したい／お願いします…） | 「問い合わせとして登録して」「この内容で問い合わせを登録したい」「問い合わせを作成してください」 |
| （担当者／ヘルプデスク／サポート）に問い合わせたい・相談したい・連絡したい | 「担当者に問い合わせたい」「ヘルプデスクに相談したいです」 |
| 問い合わせたい（です） | 「問い合わせたいです」 |
| 起票して／起票したい／起票をお願い | 「起票して」 |
| チケットを作成・起票・登録 | 「チケットを作成してください」 |

一致した部分はメッセージから取り除き、残った句読点を整えます。行頭の句読点とコロン、行末の読点を取り除き、文末の「。」は残します。そのうえで、FAQ の検索と起票案の作成に使います。

「VPN について教えてください」「問い合わせ一覧の見方を教えて」「登録方法がわからない」などは、登録の依頼とは判定しません（テストで確認）。

## 7. Agent の判断のロジックと API の変更点

1. 登録の依頼があるかを判定し、ある場合は依頼部分を取り除いた内容を使います。
2. 内容があれば、FAQ 検索 Tool を呼びます（`query` は依頼部分を除いた内容）。
3. FAQ が見つかり、登録の依頼がなければ、**`FAQ_ANSWER`** を返します（`inquiryDraft: null`）。
4. それ以外のとき（登録の依頼がある、または FAQ が見つからない）は、起票案 Tool を呼びます。
   - 起票案を作れた場合は **`INQUIRY_DRAFTED`** を返します（`inquiryDraft` に値が入り、関連する FAQ があれば `matchedFaqs` にも入ります）。
   - 作れなかった場合（「問い合わせを登録したい」のように内容がない場合）は、**`INQUIRY_SUGGESTED`** を返します（`inquiryDraft: null`、内容の入力を促す文言）。

| 変更点 | 内容 |
|---|---|
| `AgentAction` | `INQUIRY_DRAFTED` を追加しました。`FAQ_ANSWER` と `INQUIRY_SUGGESTED` は残しています |
| 応答 | `inquiryDraft` を追加しました（`INQUIRY_DRAFTED` 以外は `null`）。そのほかの項目は変えていません |
| **FAQ が見つからない場合** | **Step 2 では `INQUIRY_SUGGESTED` でしたが、起票案を作れる場合は `INQUIRY_DRAFTED` に変えました**（ご依頼の方針どおり）。`INQUIRY_SUGGESTED` は「起票案を作れなかった」という意味で残しています |
| `toolCalls` | 起票案を作るときは `search_faqs, draft_inquiry` の 2 つになります（内容がない場合は `draft_inquiry` だけ） |

**この仕様変更で更新した既存のテスト（件数は変えていません）**

- `test_rule_based_agent.py`：
  - FAQ が見つからない場合のテストを、`test_no_faq_suggests_inquiry` から `test_no_faq_drafts_inquiry` に改名し、期待値を更新しました。
  - `test_no_faq_when_table_is_empty` の期待値を更新しました。
- `test_agent_api.py`：
  - FAQ が見つからない場合のテストを、`test_no_faq_suggests_inquiry` から `test_no_faq_drafts_inquiry` に改名し、期待値を更新しました。
  - 応答のキーに `inquiryDraft` を加えました（`RESPONSE_KEYS`、VPN の応答、`get_agent()` の差し替え）。
  - OpenAPI の `AgentAction` の enum に `INQUIRY_DRAFTED` を加えました。

## 8. Next.js への引き継ぎと、既存の登録画面の再利用

| 変更 | 内容 |
|---|---|
| `src/lib/agent/types.ts` | `AGENT_ACTIONS` に `INQUIRY_DRAFTED` を追加。`InquiryDraft` の型を追加。`AgentChatResponse.inquiryDraft: InquiryDraft \| null` を追加 |
| `src/lib/agent/repository.ts` | `inquiryDraft` が `null` か、正しい形（文字列、既知のカテゴリ）かを検証し、必要な項目だけを取り出す |
| `src/components/chat/InquiryDraftCard.tsx`（新規） | 「問い合わせ起票案」として、タイトル、カテゴリ（日本語のラベル）、内容を表示する。「内容を確認して登録へ」と「まだ登録されていません」も表示する |
| `src/components/chat/AgentMessage.tsx` | `inquiryDraft` があれば起票案のカードを表示する。`INQUIRY_SUGGESTED` のときは、今までどおり空の登録画面へのリンクを表示する。「使用した Tool」の表示は変えない |
| **引き継ぎの方法** | `URLSearchParams` で URL エンコードし、`/inquiries/new?title=…&category=…&description=…` に移動するだけ（`next/link`）。**移動しただけでは登録されない** |
| `src/lib/inquiries/validation.ts` | `parseInquiryPrefill(searchParams)` を追加。値がなければ `undefined`（通常の空のフォーム）を返す。不正なカテゴリは未選択にし、タイトルと内容は上限の文字数で切る |
| `src/app/inquiries/new/page.tsx` | `searchParams` から初期値を取り出し、あれば「AIサポートが作成した起票案を入力しました。内容を確認・修正してから「登録する」を押してください（まだ登録されていません）。」と表示する（`role="status"`）。このためページは動的（`ƒ`）になった |
| `src/components/inquiries/InquiryForm.tsx` | 初期値を受け取る `defaultValues` を追加。送信したあとは、今までどおり Server Action が返す入力値を優先する |

**クエリパラメータの改ざんへの対策：** クエリの値は「入力欄の初期値」として表示するだけです。登録するときは、既存の `parseCreateInquiryInput`（Server Action の検証）と `POST /inquiries`（`InquiryCreate`）で改めて検証されるので、改ざんしても検証は回避できません。

**URL の長さ：** Agent API のメッセージは 1000 文字までなので、起票案の内容も 1000 文字以内です。エンコード後の URL は最大でも約 10 KB で、Node.js の HTTP ヘッダーの上限（16 KB）に収まります。

## 9. テストの結果

### backend（41 件を追加し、合計 209 件）

| ファイル | 追加 | 内容 |
|---|---|---|
| `tests/agents/test_draft_inquiry_tool.py`（新規） | 32 | デモのシナリオ（プリンタ）、タイトルは最初の文、内容は問題を残して依頼部分を除く、カテゴリの分類（10 パターン。全角、同数のときの優先順、一致数の多さを含む）、登録の依頼の判定（8 パターン）、依頼ではない質問（3 パターン）、先頭の依頼の除去、依頼だけの場合や空白の場合は `None`、上限（100 / 2000）、起票案が `InquiryCreate` で検証を通る（4 パターン）、引数の JSON Schema |
| `tests/agents/test_rule_based_agent.py` | 5 | FAQ あり ＋ 登録の依頼（`INQUIRY_DRAFTED`、2 つの Tool、検索は依頼部分を除いた内容で行う、関連する FAQ）、FAQ の回答には起票案がない、内容のない依頼（`INQUIRY_SUGGESTED`、`draft_inquiry` だけ）、**Agent が INSERT・UPDATE・DELETE をしない**、**agents と tools が問い合わせの登録処理を参照しない** |
| `tests/test_agent_api.py` | 4 | 登録の依頼に対する起票案の JSON、内容のない依頼は `inquiryDraft: null`、**チャットでは登録されず、起票案を人が POST /inquiries に送ると登録される**、OpenAPI の `InquiryDraft` |

| 確認内容 | 結果 |
|---|---|
| ホストでの pytest（SQLite） | **209 passed**（非推奨警告をエラー扱いにしても 209 passed） |
| PostgreSQL 18（`docker compose --profile test run --rm backend-test`） | **209 passed**（非推奨警告をエラー扱いにしても 209 passed） |
| `alembic check`（Compose の PostgreSQL） | `No new upgrade operations detected.`（DB の構造は変えていない） |

### frontend

| 確認内容 | 結果 |
|---|---|
| `npx tsc --noEmit` | 終了コード 0 |
| `npm run lint` | 終了コード 0 |
| `npm run build` | 終了コード 0。`/inquiries/new` は `ƒ`（クエリを読むため）、`/chat` は `○` |
| ブラウザ向けのファイル | `localhost:8000`、`backend:8000`、`API_BASE_URL`、`/agent/chat` は 0 件 |

## 10. Docker Compose ＋ ブラウザでの E2E の結果

`docker compose up -d --build` で、db・migrate・backend・frontend の順に起動し、すべて healthy になりました。

検証用のスクリプト（scratchpad に置き、リポジトリには含めていません）は、一時プロファイルのヘッドレス Chrome を CDP で操作します。DB の件数は `psql` で直接数えました。

| ケース | 結果 |
|---|---|
| 1：「VPNがすぐ切れます」 | 「「VPN が頻繁に切断されます」の FAQ が見つかりました。」、FAQ カード（VPN）、「使用した Tool: search_faqs」。**起票案なし** |
| 2：「プリンタで両面印刷できません。\n問い合わせとして登録して」 | 「問い合わせの起票案を作成しました。」、関連する FAQ のカード（複合機で両面印刷ができません）、**起票案のカード（タイトル：プリンタで両面印刷できません／カテゴリ：その他／内容：プリンタで両面印刷できません。）**、「内容を確認して登録へ」、「使用した Tool: search_faqs, draft_inquiry」 |
| 3：「宇宙旅行に行きたいです」 | 「FAQ では解決できませんでした。問い合わせの起票案を作成しました。」、起票案のカード（宇宙旅行に行きたいです／その他）、「使用した Tool: search_faqs, draft_inquiry」 |
| 補足：「問い合わせを登録したい」 | 「問い合わせとして登録できます。困っている内容（いつ・何が・どうなるか）を入力してください。」、空の登録画面へのリンク。使用した Tool は `draft_inquiry` |
| **4：ケース 2 の起票案 →「内容を確認して登録へ」** | `/inquiries/new?title=…` に移動し、案内文とともに、タイトル「プリンタで両面印刷できません」、カテゴリ OTHER、内容「プリンタで両面印刷できません。」が入力済み。**DB の件数：移動前 9 → 移動後 9（増えていない）** |
| **4（続き）：人がタイトルを修正して「登録する」** | `/inquiries/10` へ移動し、見出しは「プリンタで両面印刷できません（3階複合機）」（人の修正が反映された）。**DB の件数は 10（1 件だけ増えた）** |
| 通常の `/inquiries/new` | 案内文なし。タイトル、カテゴリ、内容はすべて空 |
| ブラウザの通信先 | `GET` と `POST` の `http://localhost:3000` だけ |
| JavaScript 実行後の DOM | backend の URL や内部の情報は含まれない |

| 回帰の確認 | 結果 |
|---|---|
| `/inquiries`、`/inquiries/1`、`/inquiries/new`、`/chat` | すべて 200 |
| ステータス変更（id 10 を対応中に） | 「ステータスを更新しました」 |
| `GET /faqs?q=VPN`（内部から） | [6] |
| Agent の FAQ 回答 | ケース 1 のとおり |

## 11. セキュリティの確認

| 確認内容 | 結果 |
|---|---|
| Agent は問い合わせを DB に書き込まない | SQL の記録（INSERT・UPDATE・DELETE が 0）、import の構文解析、E2E（移動しただけでは件数が増えない）で確認 |
| 登録は既存の `POST /inquiries` だけ | 起票案から登録した場合も、既存の Server Action と `POST /inquiries` を通る |
| クエリパラメータの改ざん | `title` が 150 文字なら、初期値は 100 文字に切る（`maxLength=100`）。`category=HACK` なら未選択。`description=<script>alert(1)</script>` はエスケープして表示し、生のスクリプトは含まれない。改ざんした値をそのまま送ると（101 文字のタイトルと不正なカテゴリ、空白だけのタイトル）、「タイトルは100文字以内で入力してください」「タイトルを入力してください」となり、**DB の件数は 10 → 10** |
| API キー | 追加していない |
| CORS | 追加していない（`CORSMiddleware` などの設定はない） |
| ブラウザ向けのファイルに backend の URL がない | §9 のとおり |
| スタックトレースや DB の情報 | 画面に出ない |
| backend と PostgreSQL の公開 | ホストで待ち受けているのは 3000 番だけ。`localhost:8000` と `localhost:5432` には接続できない |
| `backend/data/app.db` | SHA-256 `9641ac22…4440`、`Oct 6 23:24:13`（変わっていない） |

## 12. 見つかった問題と対応

### 問題 1：「担当者に問い合わせたい」を登録の依頼と判定できなかった

**原因：** 最初の正規表現が「問い合わせ＋したい」の形だけを想定していて、「問い合わせ**たい**」という動詞の形が抜けていました。

**対応：** 「（担当者／ヘルプデスク／サポート）に問い合わせたい・相談したい・連絡したい」と、単独の「問い合わせたい（です）」のパターンを加えました。判定のテスト（8 パターン）でこの形を確かめています。

### 問題 2：起票案の内容の末尾の「。」が消えた

**原因：** 依頼部分を取り除いたあとの句読点の後始末で、行の両端から「。」も取り除いていました。

**対応：** 取り除くのを、行頭の句読点と行末の読点だけにし、文末の「。」は残すようにしました（例：「プリンタで両面印刷できません。」）。

### 問題 3：依頼が先頭にある場合、コロンが残った

**原因：** 「問い合わせとして登録して：パスワードを忘れました」の全角コロン「：」が、NFKC で半角の「:」に変わり、内容の先頭に残っていました。

**対応：** 行頭から取り除く記号に「:」を加えました（テスト `test_request_at_the_beginning_is_removed`）。

### 問題 4：上限の値を、Pydantic のフィールドの内部情報から取り出していた

**原因：** 最初の実装では、タイトルと本文の上限を `InquiryDraft.model_fields[...].metadata[0].max_length` から取り出していました。これは Pydantic の内部の構造に依存していて、壊れやすい書き方でした。

**対応：** `schemas/inquiry.py` に `TITLE_MAX_LENGTH` と `DESCRIPTION_MAX_LENGTH` を定数として置きました。`InquiryTitle`、`InquiryDescription`、Tool はこの定数を使うので、定義は 1 か所のままです。

### 問題 5：カテゴリの例との違い（判断の記録）

ご依頼の例では、プリンタの起票案が SOFTWARE、HARDWARE も例に挙がっていました。しかし既存の `InquiryCategory` に HARDWARE はなく、既存のデータでは複合機は OTHER です。そのため enum は変えずに、機器を OTHER に分類しました（§5）。

## 13. Step 5 / Step 6 への引き継ぎ

- **LLM の Agent（Step 5）：** `draft_inquiry` の `NAME`、`DESCRIPTION`、`DraftInquiryArgs` を、LLM の tool 定義にそのまま使います。LLM が作った起票案も `InquiryDraft` で検証すれば、同じ制約が保証されます。また、LLM であっても DB に書き込まない（Human-in-the-loop を保つ）ことを方針として引き継ぎます。
- 今のルールベースの方式では、タイトルは利用者の文をそのまま使います（例：「できません」のまま）。要約したり言い換えたりするのは、LLM に任せる部分です。
- **会話の文脈：** 直前の FAQ の回答では解決しなかった、という文脈を起票案に入れたくなったら、リクエストに会話の履歴を加えることを検討します。
