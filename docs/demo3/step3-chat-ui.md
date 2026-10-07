# Demo 3 Step 3 — Next.js チャット UI と Agent API の接続

| 項目 | 内容 |
|---|---|
| 状態 | 実装・自動検証まで完了（ブラウザでの受入確認は人間が実施） |
| 実施日 | 2026-10-07 |
| 前提 | [Demo 3 Step 2](step2-agent-api.md)（`POST /agent/chat`、RuleBasedAgent、FAQ 検索 Tool）完了 |

## 1. 目的

Step 2 の `POST /agent/chat` を Next.js の画面から使えるようにし、ブラウザからデータベースまでを 1 本の流れでつなぎます。

```
ブラウザ /chat（ChatPanel）
  → Next.js の Server Action（sendChatMessageAction）    ※ ブラウザの通信先は localhost:3000 だけ
  → lib/agent/repository.ts（server-only）→ lib/api/http.ts
  → FastAPI POST /agent/chat → RuleBasedAgent → FAQ 検索 Tool → search_faqs() → PostgreSQL
  → 応答（message / action / matchedFaqs / toolCalls）→ チャット画面に表示
```

**変更していないもの：** backend（差分 0 件）、DB、Compose の構成とポートの公開方針、`backend/data/app.db`。CORS と API キーは追加していません。

## 2. ブラウザ → Next.js → FastAPI の構成と、Server Action を選んだ理由

| 判断 | 理由 |
|---|---|
| **送信は Server Action で行う** | ブラウザは Next.js（`localhost:3000`）にだけ POST し、FastAPI は Next.js のサーバー側から呼びます。FastAPI の URL や Docker の内部ネットワークの情報（`backend:8000`）を、ブラウザに渡さずに済みます。CORS も、FastAPI をホストに公開することも要りません。既存の登録やステータス変更（`useActionState` と Server Action）と同じ形です |
| Route Handler やブラウザの `fetch` は使わない | Route Handler を経由しても、結局 Next.js のサーバーが代わりに呼ぶことになり、Server Action より手間が増えるだけです。ブラウザから直接呼ぶ形は、今の構成の方針に反します |
| **HTTP の共通処理を `src/lib/api/http.ts` に切り出す**（承認済みの設計） | 問い合わせと Agent の repository で、`API_BASE_URL` の解決、10 秒のタイムアウト、`cache: "no-store"`、`ensureOk`、`readJson`、`ApiError` を共有します。移した 4 つの関数（`request`、`getApiBaseUrl`、`ensureOk`、`readJson`）の本体は、元のコードとまったく同じであることを確かめました |
| 会話は画面の状態（`useActionState` の state）にだけ持つ | Step 2 の API は会話の状態を持ちません。会話の履歴は DB に保存せず、再読み込みすると消えます。画面に保つのは最新の 40 件までです |

## 3. チャット画面の構成

| ファイル | 種類 | 役割 |
|---|---|---|
| `src/app/chat/page.tsx` | Server Component（静的） | 見出しと説明、`ChatPanel` |
| `src/app/chat/actions.ts` | Server Action（`"use server"`） | `sendChatMessageAction(prevState, formData)`。メッセージを検証（前後の空白を除き、空なら不可、1000 文字まで）し、Agent API を呼んで会話に「利用者」と「AI サポート」の発言を追加する。失敗したときは利用者向けの定型文と入力した内容を返す |
| `src/components/chat/ChatPanel.tsx` | Client Component | 会話の一覧（`aria-live="polite"`）、入力欄（`<label>` 付きの `textarea`、`maxLength=1000`）、送信ボタン（送信中は無効にして「送信中…」と表示）、送信中の表示、エラー（`role="alert"`）、新しい発言が届いたら下までスクロール |
| `src/components/chat/AgentMessage.tsx` | 表示用の部品 | Agent の回答（改行を残す）、FAQ カード、使用した Tool、`INQUIRY_SUGGESTED` のときの「問い合わせを登録する」 |
| `src/components/chat/FaqCard.tsx` | 表示用の部品 | FAQ の質問、回答、カテゴリ（日本語のラベル）、一致度 |
| `src/app/layout.tsx` | 変更 | ヘッダーに「問い合わせ一覧」と「AIサポート」のナビゲーション（`<nav aria-label="メインメニュー">`）を追加 |

**デザイン：** 既存の画面と同じ Tailwind のクラス（zinc の配色、`bg-foreground` のボタン、赤い警告）を使っています。利用者の発言は右寄せ、AI サポートの発言は左寄せの吹き出しです。

## 4. Agent API との型の対応

| backend（`app/schemas/agent.py`） | frontend（`src/lib/agent/types.ts`） |
|---|---|
| `AgentAction`（`FAQ_ANSWER` / `INQUIRY_SUGGESTED`） | `AgentAction`（`AGENT_ACTIONS` から導出） |
| `FaqResponse`（`id`、`question`、`answer`、`category`、`score`） | `AgentFaq`（`category` は既存の `InquiryCategory`） |
| `ToolCallResponse`（`name`、`arguments`） | `AgentToolCall`（`arguments` は `Record<string, unknown>`） |
| `AgentChatResponse`（`message`、`action`、`matchedFaqs`、`toolCalls`） | `AgentChatResponse` |
| `AGENT_MESSAGE_MAX_LENGTH = 1000` | `AGENT_MESSAGE_MAX_LENGTH = 1000`（コードポイント単位） |

`lib/agent/repository.ts` は、API の応答を `unknown` として受け取り、形を検証します。確かめるのは、`action` が既知の値か、各 FAQ の型、category が既知の値か、`toolCalls` の形です。そのうえで必要な項目だけを取り出してから、画面に渡します。形が想定と違えば例外にし、§6 のエラー処理に任せます。

## 5. Tool の可視化

`toolCalls` の名前を、Agent の回答の下に小さく（`text-xs`、灰色）「使用した Tool: `search_faqs`」と表示します。利用者向けの画面として目立ちすぎず、面談では「Agent が業務の Tool を呼んで回答している」ことを説明できます。

FAQ カードの「一致度」は、Tool の結果の `score` です。

## 6. エラー処理

| 状況 | 画面 | ログ |
|---|---|---|
| 空のメッセージ | 「メッセージを入力してください」（ブラウザの `required` に加えて、サーバーでも確かめる） | — |
| 1000 文字を超える | 「メッセージは1000文字以内で入力してください」。入力した内容は残る | — |
| Agent API に接続できない、5xx、JSON が壊れている、応答の形が違う、タイムアウト | **「AIサポートに接続できませんでした。時間をおいて再度お試しください。」**。入力した内容は残り、会話には追加しない | Next.js のサーバーのログにだけ、`[chat] Agent API の呼び出しに失敗しました` と原因（例：`ENOTFOUND backend`）を出力する |

内部の URL、スタックトレース、DB の情報は、画面にも Server Action の応答にも含めません。既存の問い合わせの Server Action の方針（定型文だけを返す）に合わせ、そのうえで原因をサーバーのログに残すようにしました。

## 7. テストと検証の結果

**frontend の自動テストのライブラリは、これまでの方針どおり導入していません。** 静的チェック、本番ビルドの検査、Docker Compose での実際のブラウザ（ヘッドレス Chrome）による E2E で確かめました。

### 静的チェックとビルド

| 確認内容 | 結果 |
|---|---|
| `npx tsc --noEmit` | 終了コード 0 |
| `npm run lint` | 終了コード 0 |
| `npm run build` | 終了コード 0。`/chat` は `○`（静的。描画時に API を呼ばない）、`/inquiries` と `/inquiries/[id]` は `ƒ` |
| ブラウザ向けのファイル（`.next/static`） | `localhost:8000`、`backend:8000`、`API_BASE_URL`、`/agent/chat`、接続エラーの文言は、どれも 0 件（すべてサーバー側にだけある） |
| 共通処理の切り出し | 移した 4 つの関数の本体が、元のコードと完全に同じ |

### backend の回帰

backend の差分は 0 件で、SQLite・PostgreSQL のどちらでも **168 passed** でした（SQLite では、非推奨警告をエラー扱いにしても 168 passed）。

### Docker Compose での E2E（ヘッドレス Chrome を CDP で操作）

`docker compose up -d --build` で、db・migrate・backend・frontend の順に起動し、すべて healthy になりました。

検証用のスクリプト（scratchpad に置き、リポジトリには含めていません）は、一時プロファイルのヘッドレス Chrome を Chrome DevTools Protocol で操作します。`/chat` を開いて入力欄にメッセージを入れて送信し、JavaScript を実行したあとの画面を読み取るとともに、ブラウザが送ったすべての通信先を記録しました。

| 送信したメッセージ | 画面の表示 |
|---|---|
| 「VPNがすぐ切れます」 | 「「VPN が頻繁に切断されます」の FAQ が見つかりました。」と対処法。FAQ カード（VPN が頻繁に切断されます／カテゴリ：ネットワーク／一致度：3）。「使用した Tool: search_faqs」 |
| 「パスワードを忘れました」 | パスワードの FAQ（カテゴリ：アカウント、一致度：6）。Tool: search_faqs |
| 「宇宙旅行に行きたいです」 | 「FAQ では解決できませんでした。…」。FAQ カードなし。「問い合わせを登録する」（`/inquiries/new`）。Tool: search_faqs |
| 「パスワードを忘れたうえに VPN もつながりません」 | FAQ カードが 2 枚（パスワード：6、VPN：4）。会話は 8 件（4 往復）まで、画面の上に残っていく |
| （送信のたび） | 入力欄は空になり、送信ボタンは押せる状態に戻る |

| 確認内容 | 結果 |
|---|---|
| ブラウザが通信した先 | `GET http://localhost:3000` と `POST http://localhost:3000` だけ（8000 番への通信はない） |
| JavaScript 実行後の DOM | `localhost:8000`、`backend:8000`、`API_BASE_URL`、`Traceback`、`psycopg`、`ECONNREFUSED`、`ENOTFOUND`、`fetch failed` は含まれない |
| backend を止めて送信 | 「AIサポートに接続できませんでした。時間をおいて再度お試しください。」。入力欄に送った文字列が残り、会話には追加されない。内部の情報は出ない。Next.js のログには `[chat] … TypeError: fetch failed … ENOTFOUND backend` |
| backend を再開（healthy）して再送信 | 再び FAQ の回答が表示される |
| `/inquiries`、`/inquiries/1`、`/inquiries/new`、`/chat` | すべて 200。ヘッダーに「メインメニュー」のナビゲーションと「AIサポート」のリンクがある |
| `/inquiries/999` | 404「問い合わせが見つかりません」。JavaScript の実行後にヘッダーとナビゲーションが表示される |
| 既存の登録とステータス変更（共通処理を切り出したあとの経路） | JavaScript なしのフォーム送信で、303 で `/inquiries/9` へ移動し、「ステータスを更新しました」（対応中）。Compose のデモ用 DB に 1 件追加された |
| ポート | ホストで待ち受けているのは 3000 番だけ。`localhost:8000` と `localhost:5432` には接続できない |

## 8. セキュリティの確認

| 確認内容 | 結果 |
|---|---|
| API キー | 追加していない（`backend/app`、`frontend/src`、`compose.yaml`、`.env.example` に API キー関連の設定はない） |
| backend の URL | ブラウザ向けのファイル、DOM、ブラウザの通信先のどれにも出てこない。`lib/agent/repository.ts` と `lib/api/http.ts` は `server-only` |
| スタックトレースと DB の情報 | 画面には出ない（定型文だけ）。原因は Next.js のサーバーのログだけに出る |
| CORS | 追加していない（`CORSMiddleware` などの設定はない）。別のオリジンからの `OPTIONS /chat` に `Access-Control-*` ヘッダーは付かない |
| backend と PostgreSQL の公開 | ホストに公開していない（変更なし） |
| Server Action に渡る会話の履歴 | クライアントが渡した会話を、そのまま返すだけ。サーバー側では信頼せず、保存も判断にも使わない（改ざんされても、その利用者の画面に表示されるだけ）。長さは 40 件までに抑える |

## 9. 見つかった問題と対応

### 問題 1：`"use server"` のファイルから定数を export していた

**現象：** 最初の実装では、`src/app/chat/actions.ts` から、エラーの文言の定数（`CONNECTION_ERROR_MESSAGE`）を export していました。

**原因：** Server Action のファイルから export できるのは、非同期の関数だけです。そのため、ビルドのときにエラーになるおそれがありました。

**対応：** export をやめ、ファイルの中だけで使う定数にしました。型（`ChatState`）の export は、コンパイル時に消えるので問題ありません。

### 問題 2：404 の HTML にナビゲーションが含まれていないように見えた（今回の変更による問題ではない）

**現象：** `curl` で取得した `/inquiries/999` の HTML に、`<header>` 要素がありませんでした。

**原因：** Next.js 16 では、動的なルートで `notFound()` を呼ぶと、ヘッダーとナビゲーションをストリーミング用のデータとして返し、JavaScript でそれを描画します。Step 3 より前から、ヘッダーは同じ形で返っていました。

**対応：** ヘッドレス Chrome で、JavaScript の実行後にヘッダー、ナビゲーション、「問い合わせが見つかりません」が表示されることを確かめました。コードの変更は不要です。

## 10. Step 4 への引き継ぎ

- `AgentMessage.tsx` で `action === "INQUIRY_SUGGESTED"` のときに表示している「問い合わせを登録する」（`/inquiries/new`）を、Agent が作る起票案（タイトル、カテゴリ、本文）を引き継ぐ導線に置き換えます。たとえば `/inquiries/new?title=&category=&description=` へ移動し、既存の `InquiryForm` に初期値として入れ、登録は既存の `createInquiryAction`（`POST /inquiries`）で行います。
- 起票案は、backend の Agent の応答に追加します（例：`inquiryDraft`）。frontend の型（`AgentChatResponse`）と repository の検証にも、同じ項目を加えます。
- 会話の文脈が必要になったら（例：直前の FAQ では解決しなかった、という前提で起票する）、リクエストに会話の履歴を加えることを検討します。画面は会話を `entries` として持っているので、そこから送れます。
