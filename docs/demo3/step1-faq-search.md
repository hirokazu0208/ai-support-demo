# Demo 3 Step 1 — FAQ のデータと検索 Tool

| 項目 | 内容 |
|---|---|
| 状態 | 実装・自動検証まで完了 |
| 実施日 | 2026-10-07 |
| 前提 | Demo 2 Step 6B（Docker Compose での PostgreSQL 化）完了 |

## 1. Demo 3 の全体像と Step 1 の位置づけ

Demo 3 では、問い合わせ管理システムを「AI 問い合わせ支援 Agent」に段階的に広げます。

```
ユーザー → Next.js のチャット UI → FastAPI → AI Agent ─┬─ FAQ 検索 Tool ─────────┐
                                                      └─ 問い合わせ起票 Tool ─→ 既存の登録画面 / POST /inquiries → PostgreSQL
```

| Step | 内容 |
|---|---|
| **1** | **FAQ のデータと検索 Tool（本 Step）** |
| 2 | Agent API（ルールベースのエンジン、Tool の登録と実行、`POST /agent/chat`） |
| 3 | Next.js のチャット UI（`/chat`） |
| 4 | 問い合わせ起票 Tool（AI が起票案を作り、人が既存の登録画面で確認して登録する） |
| 5 | LLM への接続（任意。`AgentEngine` を差し替える） |
| 6 | 統合確認、README、デモの台本 |

**Step 1 の目的：** Agent が呼び出す「FAQ 検索」を、DB と repository の層で作ります。FAQ は 10 件だけにし、RAG やベクトル検索は使いません。

**変更していないもの：** 問い合わせの API と画面、frontend、Compose の構成、ポートの公開方針、`backend/data/app.db`

## 2. 変更したファイル

| ファイル | 区分 | 内容 |
|---|---|---|
| `app/models/faq.py` | 新規 | `Faq` モデル |
| `alembic/versions/20261007_84d472b1f0f0_create_faqs_table.py` | 新規 | `faqs` テーブル（revision `84d472b1f0f0`、前の revision は `d39d3345e879`） |
| `app/db/faq_seed_data.py` | 新規 | FAQ 10 件 |
| `app/repositories/faqs.py` | 新規 | `search_faqs()`、`score_faq()`、`normalize()`、`FaqMatch` |
| `app/schemas/faq.py` | 新規 | `FaqResponse`、`FaqSearchParams` |
| `app/routers/faqs.py` | 新規 | `GET /faqs` |
| `app/db/types.py` | 変更 | `portable_enum()` を `models/inquiry.py` から移す（FAQ と共有するため。動作は変わらない） |
| `app/models/inquiry.py` | 変更 | `portable_enum()` を import して使うだけ（DDL は変わらない。`alembic check` で確認） |
| `app/models/__init__.py` | 変更 | `Faq` を登録 |
| `app/main.py` | 変更 | `faqs.router` を登録 |
| `app/db/seed.py` | 変更 | `seed_faqs()` を追加。`main()` で問い合わせと FAQ をそれぞれ投入する（問い合わせのメッセージは今までと同じ） |
| `tests/db/test_faq_search.py`、`tests/test_faqs_api.py` | 新規 | 検索と API のテスト |
| `tests/db/test_migrations.py` | 変更 | **既存のテスト 1 件の期待値**（テーブルの集合）に `faqs` を加える。`faqs` に関するテストを 2 件追加 |
| `tests/db/test_seed.py` | 変更 | FAQ の seed のテストを 3 件追加 |
| `README.md`、`backend/README.md`、`docs/README.md` | 変更 | Demo 3 の進捗、API、seed の手順 |

## 3. migration（`84d472b1f0f0`）

```sql
-- PostgreSQL（SQLite では id INTEGER、日時は DATETIME）
CREATE TABLE faqs (
    id SERIAL NOT NULL,
    question VARCHAR(200) NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(20) NOT NULL,
    keywords VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_faqs PRIMARY KEY (id),
    CONSTRAINT ck_faqs_category CHECK (category IN ('ACCOUNT', 'NETWORK', 'SOFTWARE', 'OTHER'))
);
```

- **category：** `InquiryCategory` を再利用します。保存のしかたは inquiries と同じ（VARCHAR と名前付きの CHECK 制約）で、制約名は命名規則により `ck_faqs_category` になります。
- **インデックス：** 付けません。件数が少なく、全件を読み込んで検索するためです。
- **autogenerate の結果の手直し：** Step 2 の初期 migration と同じ 2 つの問題が出たので、同じ方針で直しました（§7 を参照）。
  - CHECK 制約が 3 つ重なって出力された。
  - `UTCDateTime` を参照するコードが、その import なしに出力された。
- **downgrade：** `drop_table("faqs")` だけで、inquiries には影響しません（テストで確認）。

## 4. FAQ の seed

`python -m app.db.seed` は、問い合わせ（8 件）と FAQ（10 件）を、**テーブルごとに独立して**「空のときだけ」投入します。問い合わせが既にある環境（Step 6B までの DB）でも、FAQ は投入されます。

| id | category | 質問 | キーワード |
|---|---|---|---|
| 1 | ACCOUNT | パスワードを忘れてログインできません | パスワード 忘れ リセット 再設定 ログイン |
| 2 | ACCOUNT | 新入社員のアカウントを発行してほしい | 新入社員 入社 アカウント発行 発行 |
| 3 | ACCOUNT | 退職者のアカウントを無効化したい | 退職 退職者 無効化 停止 削除 |
| 4 | ACCOUNT | 多要素認証（MFA）の認証アプリを再設定したい | 多要素認証 MFA 二段階認証 認証アプリ 機種変更 |
| 5 | NETWORK | 社内 Wi-Fi に接続できません | Wi-Fi WiFi 無線 無線LAN 接続できない ネットワーク |
| 6 | NETWORK | VPN が頻繁に切断されます | VPN 切断 切れる 在宅 リモート |
| 7 | SOFTWARE | Excel や Word が起動直後に終了します | Excel Word Office 起動 強制終了 落ちる |
| 8 | SOFTWARE | ソフトウェアのライセンスを追加したい | ライセンス 追加 購入 インストール ソフトウェア |
| 9 | OTHER | 複合機で両面印刷ができません | 複合機 プリンター プリンタ 印刷 両面 ドライバー |
| 10 | OTHER | PC が故障したので代替機を借りたい | PC パソコン 故障 代替機 貸出 交換 |

回答の全文は `app/db/faq_seed_data.py` にあります。`created_at` と `updated_at` は、投入した時刻（同じ値）です。

## 5. 検索のアルゴリズム（キーワード + 部分一致のスコア方式）

1. **正規化：** 質問文と FAQ の文字列を、NFKC で正規化したうえで casefold（大文字小文字を区別しない形）にします。全角・半角と、大文字・小文字の違いがなくなります（例：「ＶＰＮ」→「vpn」）。
2. **点数の付け方**（FAQ ごと）：

| ルール | 点数 |
|---|---|
| FAQ のキーワードが、質問文に含まれる（1 つにつき） | +3 |
| 質問文の全体が、FAQ の質問に含まれる | +2 |
| 質問文の全体が、FAQ の回答に含まれる | +1 |
| 質問文が空白で複数の語に分かれる場合に、各語が FAQ の質問かキーワードに含まれる（1 語につき） | +1 |

3. **結果：** 点数が 0 より大きいものを、点数の高い順（同じ点数なら id の昇順）に、最大 `limit` 件返します。質問文が空のときは、id の順に `limit` 件（点数は 0）を返します。

**判断の理由**

- **「キーワードが質問文に含まれるか」という逆向きの判定：** 日本語は単語の区切りがないので、分かち書きをせずに、質問文の中に FAQ のキーワードがあるかで判定します。たとえば「VPN がすぐ切れる」には、キーワードの「VPN」と「切れる」が含まれるので、点数は 6 になります。形態素解析の辞書も外部のサービスも要りません。
- **DB ではなく Python で点数を付ける：** FAQ を全件読み込んで計算するので、SQLite と PostgreSQL で結果がまったく同じになります（テストで確認）。SQLite の `lower()` が ASCII にしか効かないという制約や、`LIKE` のワイルドカードの扱いも関係ありません（`%` や `_` は普通の文字として扱われ、0 件になります）。
- **キーワードの選び方：** 多くの質問に出てくる汎用的な語（例：「申請」）はキーワードにしません。無関係な FAQ に一致してしまうためです（§7 を参照）。
- **今後の拡張：** FAQ が数百件を超えたり、言い換えに対応したくなったりしたら、`search_faqs(session, q, limit)` のシグネチャはそのままにして、中身を PostgreSQL の全文検索、pgvector、Azure AI Search などに置き換えます（Agent の Tool やルーターは変えなくてよい）。

## 6. API の仕様：`GET /faqs`

| パラメータ | 型 | 説明 |
|---|---|---|
| `q` | string（最大 200 文字）、省略可 | 質問文。前後の空白は除き、空なら「指定なし」 |
| `limit` | integer（1〜20）、既定値 5 | 最大件数 |

| 応答 | 条件 |
|---|---|
| `200` `FaqResponse[]` | 点数の高い順（同じ点数なら id の順）。一致がなければ `[]`。`q` を指定しなければ id の順（点数は 0） |
| `422` | `limit` が範囲外か整数でない、`q` が 201 文字以上、定義していないパラメータ |
| `500` | DB の障害（内部の情報は返さない。Step 3 と同じ） |

```json
[
  {
    "id": 6,
    "question": "VPN が頻繁に切断されます",
    "answer": "VPN クライアントを最新版に更新し、…",
    "category": "NETWORK",
    "score": 6
  }
]
```

- **キーの書き方：** 1 語のキーだけなので、camelCase との違いは生じません（`alias_generator=to_camel` は付けてあります）。
- **読み取り専用：** commit はしません。
- **Agent からの使い方（Step 2）：** HTTP を経由せず、repository の `search_faqs()` を直接呼びます。

## 7. 実装中に見つかった問題と対応

### 問題 1：autogenerate の出力をそのままでは使えない（既知の問題の再発）

**現象：**

- CHECK 制約が、`name='category'` と `ck_faqs_category` の 2 つで出力され、Enum 自身が作る制約と合わせて 3 つになりました。
- `app.db.types.UTCDateTime` を、その import なしに参照していました。

**原因：** Step 2 で調べたものと同じで、Alembic 1.20.0 が SQLAlchemy 2.1 の Enum の制約を判別できないことと、TypeDecorator をそのまま出力することによるものです。

**対応：** 初期 migration と同じ方針で手直ししました（Enum は `create_constraint=False`、CHECK 制約は名前付きで 1 つだけ明示、日時は `sa.DateTime(timezone=True)`）。SQLite と PostgreSQL（オフライン）の DDL で、制約が 1 つだけであることを確かめています。テスト `test_faqs_table_is_created` でも、制約名が `["ck_faqs_category"]` だけであることを確かめています。

### 問題 2：一致する FAQ がないはずの質問が、無関係な FAQ に一致した

**現象：** テスト `test_no_match_returns_empty_list` で、「宇宙旅行の申請方法」が FAQ 2（新入社員のアカウント発行）に一致しました。

**原因：** 検索の処理は正しく、FAQ 2 のキーワードに、どの申請にも当てはまる汎用的な語「申請」が入っていたためでした。

**対応：** テストの質問文を変えて通すのではなく、データを直しました（FAQ 2 のキーワードから「申請」を外す）。キーワードの選び方の方針として、`faq_seed_data.py` の説明文にも書いています。

### 補足：ホストの開発用 DB

ホストの `backend/data/app.db` は、まだ migration の 1 本目（`d39d3345e879`）のままです（「変更しない」という条件のため、実行していません）。ホストで FAQ を使うには、`backend/` で `alembic upgrade head` と `python -m app.db.seed` を実行してください。

## 8. 検証結果

確認日：2026-10-07。

### テスト

| 確認内容 | 結果 |
|---|---|
| ホストでの pytest（SQLite） | **144 passed**（既存の 111 件と追加の 33 件）。非推奨警告をエラー扱いにしても 144 passed |
| PostgreSQL 18（`docker compose --profile test run --rm backend-test`） | **144 passed**。非推奨警告をエラー扱いにしても 144 passed |
| `alembic check`（一時 SQLite、Compose の PostgreSQL） | どちらも `No new upgrade operations detected.` |
| migration の往復（一時 SQLite） | `upgrade head` → `downgrade -1` → `upgrade head` |

**追加したテスト（33 件）**

| ファイル | 件数 | 内容 |
|---|---|---|
| `tests/db/test_faq_search.py` | 18 | 正規化、キーワードの逆向きの判定、全角・小文字（3 パターン）、キーワードが多く一致するほど上位、質問・回答の部分一致、空白で分けた語、同じ点数は id 順、一致なし、ワイルドカードを文字として扱う、空の質問文（3 パターン）、件数の上限、seed の FAQ の代表的な 5 つの質問で期待した FAQ が先頭に来る（両方の DB で同じ）、CHECK 制約 |
| `tests/test_faqs_api.py` | 10 | 点数の順、camelCase のキー、既定の件数 5、`limit` と前後の空白の除去、一致なしは `[]`、422（5 パターン）、OpenAPI |
| `tests/db/test_migrations.py` | 2 | `faqs` のカラム・NOT NULL・PK・CHECK 制約、`downgrade -1` で `faqs` だけが消える |
| `tests/db/test_seed.py` | 3 | FAQ の投入と冪等性、問い合わせとは独立していること、migration が未適用のときのエラー |

既存のテストで変えたのは、`test_upgrade_creates_inquiries_table` の期待値（テーブルの集合に `faqs` を加える）1 か所だけです。

### Docker Compose（PostgreSQL）

| 確認内容 | 結果 |
|---|---|
| `up -d --build`（Step 6B のデータが入った既存の `pgdata`） | 終了コード 0。db、migrate、backend、frontend の順に起動し、すべて healthy、migrate は `Exited (0)` |
| migrate | `Running upgrade d39d3345e879 -> 84d472b1f0f0, create faqs table` |
| `alembic current` / `alembic check` | `84d472b1f0f0 (head)` / 差分なし |
| seed 1 回目 | 「既にデータがあるため seed をスキップしました。」（問い合わせ）と「10 件の FAQ を投入しました。」 |
| seed 2 回目 | 問い合わせも FAQ もスキップ |
| `GET /faqs`（frontend のコンテナから `backend:8000` に接続） | 「VPNがすぐ切れる」→ 6:VPN（点数 6）。「ＷｉＦｉにつながらない」→ 5:Wi-Fi（全角も一致）。「パスワードを忘れた」→ 1:パスワード（点数 6）。「宇宙旅行の申請方法」→ `[]`。q の指定なし → id 1〜5。`limit=0` → 422 |
| 既存の機能 | `/inquiries` は 200（8 件、同じ並び順）、`/inquiries/1` は 200 |
| ポート | ホストからは `localhost:3000` だけに届く。`8000` と `5432` には接続できない（方針は変えていない） |

### ほかに影響していないこと

| 確認内容 | 結果 |
|---|---|
| frontend | 差分なし |
| `backend/data/app.db` | SHA-256 `9641ac22…4440`、`Oct 6 23:24:13`、revision `d39d3345e879`、8 件（Step 1 の前と同じ） |
| `git diff --check` | 問題なし |

## 9. Step 2 への引き継ぎ

- FAQ 検索 Tool は、`app.repositories.faqs.search_faqs(session, q, limit=…)` を呼び、`FaqMatch(faq, score)` を受け取ります。Tool の引数は `{query: str, limit: int}` の Pydantic モデルにし、Step 5 で LLM の tool 定義（JSON Schema）にそのまま使います。
- 点数が 0 のとき（一致なし）は、Step 4 で起票案につなぎます。
- `Faq.category` は `InquiryCategory` なので、Step 4 の起票案でカテゴリを推定するときの手がかりに使えます。
