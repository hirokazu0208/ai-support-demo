# Demo 2 Step 3 — 問い合わせの読み取り API

| 項目 | 内容 |
|---|---|
| 状態 | 完了 |
| 実施日 | 2026-10-07 |
| 前提 | [Demo 2 Step 2](step2-database-layer.md)（SQLAlchemy + SQLite + Alembic による DB 層、seed、`/health/ready`）完了 |

## 1. 目的とスコープ

Step 2 で作った DB 層を使い、問い合わせを読み取る REST API（一覧・詳細）を作ります。レスポンスの形は、Demo 1 の frontend（`frontend/src/lib/inquiries/repository.ts` の `getInquiries` / `getInquiryById`）からそのまま置き換えられるように設計します。

**やること**

- `GET /inquiries`（一覧、キーワード検索、status の絞り込み、両者の組み合わせ）
- `GET /inquiries/{id}`（詳細、404）
- レスポンスのスキーマ（JSON は camelCase）、クエリパラメータのスキーマ
- 読み取り用のデータアクセス層（repository）
- 入力の検証（422）と、DB の例外の内容をレスポンスに出さないこと
- repository と API の pytest

**やらないこと（後続 Step で実施）**

- `POST /inquiries`、`PATCH /inquiries/{id}/status`、DELETE
- frontend との接続、`mock-data.ts` の削除、CORS
- Docker、PostgreSQL / Azure、認証・認可

**変更していないもの：** DB のモデル、migration、seed、`/health`、`/health/ready`、frontend

## 2. ファイル構成

```
backend/app/
├── main.py                 # 変更：inquiries.router を登録
├── schemas/
│   └── inquiry.py          # InquiryResponse, InquiryListParams
├── repositories/
│   └── inquiries.py        # list_inquiries(), get_inquiry()
└── routers/
    └── inquiries.py        # GET /inquiries, GET /inquiries/{inquiry_id}
backend/tests/
├── conftest.py             # 変更：make_inquiry, client fixture を追加
├── db/test_inquiry_repository.py
└── test_inquiries_api.py
```

| ファイル | 役割 |
|---|---|
| `schemas/inquiry.py` | API の入出力の型。snake_case と camelCase の変換はここだけで行う |
| `repositories/inquiries.py` | SQL の組み立てと実行。HTTP のことは扱わない |
| `routers/inquiries.py` | HTTP の処理（パラメータの受け取り、404 への変換）。SQLAlchemy を直接使わない |

依存の向きは `routers → repositories → models`、`routers → schemas → models` です。

## 3. 技術判断

| 判断 | 理由 | 検討した代替案 |
|---|---|---|
| ルーターとデータアクセスを分け、repository は関数で書く | SQL と HTTP の処理をそれぞれ単独でテストできる。frontend の `repository.ts` と同じ単位で対応づけられる | ルーターで SQLAlchemy を直接使う、repository をクラスにする、service 層を設ける（読み取りだけでは業務ロジックがなく、層が増えるだけ） |
| 一覧は**配列をそのまま返す**（`[...]`） | frontend の `getInquiries(): Promise<Inquiry[]>` と一致する。ページングは対象外 | `{ "items": [...], "total": n }`（ページングを入れるときに検討） |
| Python・DB は snake_case、API の JSON は camelCase。変換は `alias_generator=to_camel` で行う | frontend の `createdAt` とそのまま一致する。変換する場所が 1 か所で済む | API も snake_case にして frontend で変換する |
| id は API では integer。frontend の `id: string` へは Step 5 で変換する | DB の型と OpenAPI を一致させる | API で文字列を返す |
| 日時は `AwareDatetime` にし、ISO 8601 の UTC で `Z` 付きにする | タイムゾーンのない値を返そうとしたら検証エラーにできる。日本時間への変換は Demo 1 と同じく frontend で行う | 文字列に整形してから返す |
| Enum は `app.models` の `StrEnum` を再利用する | DB・API・OpenAPI で値が一つに定まる | API 用に別の Enum を定義する |
| キーワード検索は `icontains(q, autoescape=True)` | SQLite では `lower() LIKE`、PostgreSQL では `ILIKE` になり、DB ごとに分岐しなくてよい。`%` と `_` は文字どおりに扱われる | `like` / `ilike` を直接使う（エスケープを自分で書く必要がある） |
| 並び順は `created_at DESC, id DESC` | 同じ作成日時でも順序が決まる | `created_at DESC` だけ（順序が不定になる） |
| **不正な status は 422** | API としては厳密にする。Demo 1 の「未知の値は指定なし」という扱いは frontend の `parseInquiryQuery` が引き続き担う | 無視して全件を返す |
| **定義していないクエリパラメータは 422**（`extra="forbid"`） | 綴りの間違い（`?stauts=`）を見逃さない | 無視する |
| **q は 200 文字まで** | LIKE 検索の負荷を抑える。title の上限 100 より余裕を持たせた | 上限なし |
| 空白だけの q は指定なしとして扱い、前後の空白は除く | Demo 1 と同じ（Python の `str.strip()` は全角スペースも除く。JS の `trim()` と同じ） | 空文字で検索する |
| id は `1〜2147483647` の範囲外なら 422 | PostgreSQL の SERIAL（int4）の上限。SQLite では 2⁶³ 以上の整数で `OverflowError` が起きて 500 になるのを防ぐ | 検証しない（500 になる） |
| DB の例外には独自のハンドラーを作らず、Starlette の標準の 500 にする | 標準（`debug=False`）でも、例外の内容や接続先を返さない。テストでこのことを保証する | 独自の例外ハンドラーで JSON を返す（必要になったら検討） |
| 読み取りでは commit しない | Session のライフサイクルは `get_db()` が管理する（Step 2 の方針どおり） | — |

## 4. API 仕様

### `GET /inquiries`

| パラメータ | 型 | 説明 |
|---|---|---|
| `q` | string（最大 200 文字）、省略可 | title **または** description の部分一致。大文字小文字を区別しない（ASCII）。前後の空白は除き、空になれば指定なし。`%` と `_` は文字どおりに扱う。category は検索の対象外 |
| `status` | `OPEN` / `IN_PROGRESS` / `CLOSED`、省略可 | 完全一致。q と組み合わせると AND になる |

| 応答 | 条件 |
|---|---|
| `200` `InquiryResponse[]` | 正常（0 件なら `[]`）。並び順は `created_at DESC, id DESC` |
| `422` | 不正な status、q が 201 文字以上、定義していないパラメータ |
| `500` `Internal Server Error`（text/plain） | DB の障害など。内部の情報は含めない |

### `GET /inquiries/{inquiry_id}`

| 応答 | 条件 |
|---|---|
| `200` `InquiryResponse` | 存在する |
| `404` `{"detail": "Inquiry not found"}` | 存在しない |
| `422` | 整数でない（`abc`、`1.5`）、範囲外（`0`、`-1`、`2147483648` 以上） |
| `500` | DB の障害など |

### `InquiryResponse`

```json
{
  "id": 1,
  "title": "パスワードを忘れてログインできない",
  "description": "社内ポータルのパスワードを失念しました。リセット手順を教えてください。",
  "category": "ACCOUNT",
  "status": "OPEN",
  "createdAt": "2026-09-28T00:15:00Z",
  "updatedAt": "2026-09-28T00:15:00Z"
}
```

### OpenAPI

| 項目 | 内容 |
|---|---|
| パス | `GET /inquiries`（200、422）、`GET /inquiries/{inquiry_id}`（200、404、422） |
| パラメータ | 一覧は `q` と `status`。詳細は `inquiry_id`（minimum 1、maximum 2147483647） |
| スキーマ | `InquiryResponse`（プロパティは camelCase）、`InquiryCategory`、`InquiryStatus`（enum） |
| タグ | `inquiries` |

## 5. 検証結果

確認日：2026-10-07（macOS / Python 3.11.9）。パッケージの追加はありません。

### 実際の DB（seed の 8 件）での API 確認

| 確認内容 | リクエスト | 結果 |
|---|---|---|
| 一覧と並び順 | `GET /inquiries` | 200。id の順は `[7, 6, 5, 8, 3, 2, 1, 4]`。createdAt は `2026-10-03T06:10:00Z` から `2026-09-24T05:30:00Z` へ降順 |
| q の検索 | `?q=vpn` | `[5]`（大文字小文字を区別しない） |
| q の検索（日本語） | `?q=アカウント` | `[8, 4]` |
| status | `?status=CLOSED` | `[8, 4]` |
| q（status なし） | `?q=できない` | `[7, 2, 1]` |
| q と status | `?q=できない&status=OPEN` | `[7, 1]`（IN_PROGRESS の 2 が除かれる） |
| 空白だけの q | `?q=%20%20` | 8 件（全件） |
| 0 件 | `?q=存在しない語` | `200 []` |
| 詳細 | `GET /inquiries/1` | 200。§4 の JSON（camelCase、`Z` 付きの UTC） |
| 存在しない id | `GET /inquiries/999` | `404 {"detail":"Inquiry not found"}` |
| 不正な status | `?status=PENDING` | 422（`loc: ["query","status"]`、許可される値を表示） |
| 不正な id | `/inquiries/abc`、`/inquiries/0` | 422（`int_parsing`、`greater_than_equal`） |
| 極端に大きい id | `/inquiries/9223372036854775808` | **422**（`less_than_equal`。500 にならない） |
| 定義していないパラメータ | `?stauts=OPEN` | 422（`extra_forbidden`） |
| DB の障害 | 開けない `DATABASE_URL` で起動 | `/inquiries` と `/inquiries/1` は `500 Internal Server Error`（text/plain、21 バイト）。例外の内容はサーバーログにだけ出る。`/health/ready` は 503 |
| 既存のエンドポイント | `/health`、`/health/ready` | どちらも 200（変更なし） |

### その他の確認

| 確認内容 | 結果 |
|---|---|
| `pytest -q` | 68 passed |
| `pytest -q -W error::DeprecationWarning` | 68 passed |
| `alembic check` | `No new upgrade operations detected.`（モデル・migration の変更なし） |
| `git check-ignore -v backend/data/app.db` | 除外されている |
| frontend の差分 | なし |

### 追加したテスト

| ファイル | 件数 | 確認すること |
|---|---|---|
| `tests/db/test_inquiry_repository.py` | 11 | 並び順（同時刻は id の降順）、0 件、title と description の両方を対象にした検索、ASCII の大文字小文字を区別しない、日本語の部分一致、`%` と `_` を文字どおりに扱う、status、q と status の AND、一致なし、1 件取得、見つからない場合の `None` |
| `tests/test_inquiries_api.py` | 28 | seed での並び順、同時刻の順序、0 件、camelCase のキーと `Z` 付きの UTC、q の検索・前後の空白の除去・空白だけ（半角・全角）、status、q と status、一致なし、422（status、未定義のパラメータ、201 文字の q）、詳細、404、不正な id 7 パターンが 422、上限の id は 404、DB の障害時の 500 で内部情報を出さない（一覧・詳細）、OpenAPI |

テストのデータは、基本的にテストごとに専用のデータ（`make_inquiry`）を作ります。seed の 8 件は、Demo 1 のデータでの並び順と検索結果を確かめる結合テストでだけ使います。どちらも一時ディレクトリの SQLite に migration を適用して使い、`backend/data/app.db` には触れません。

### 検証で見つかった問題と対応

#### 問題 1：検索結果の想定が実際のデータと違っていた（テスト側の誤り）

**現象**

設計の段階では「`q=アカウント` は id 1・4・8 に一致する」と想定し、そのとおりにテストを書いていました。しかし API は `[8, 4]` を返し、テストが 2 件失敗しました。

**原因**

id 1（「パスワードを忘れてログインできない」）は category が `ACCOUNT` ですが、title にも description にも「アカウント」という語が含まれていません。検索の対象は設計どおり title と description だけで、category は含みません。誤っていたのは API ではなく、テストの想定でした。DB に直接問い合わせて、一致するのが 4 と 8 だけであることを確かめています。

**対応**

- テストの期待値を `[8, 4]` に直し、「category は検索の対象外」であることをコメントで残しました。
- q と status の AND で実際に絞り込まれることを確かめるため、複数の status にまたがって一致する `q=できない` を使うテストに変えました。結果は 7（OPEN）、2（IN_PROGRESS）、1（OPEN）で、`status=OPEN` を加えると `[7, 1]` になります。
- 「category は検索の対象外」であることを §4 の API 仕様に明記しました。

## 6. Step 2 からの引き継ぎ事項の扱い

| 事項 | 対応 |
|---|---|
| Session のライフサイクル | `get_db()` をそのまま使った（1 リクエスト 1 Session、close されると読み取りのトランザクションは rollback される） |
| トランザクション境界を明示する方針 | 読み取りだけなので commit 処理は加えていない。方針は Step 4 に引き継ぐ |
| `ilike` を使う方針 | `icontains` で実現した |
| `created_at DESC, id DESC` | 採用した |
| readiness | 変更なし。業務 API が DB 障害のときは 500、DB に接続できるかの確認は `/health/ready`（503）が担う |
| Alembic とモデルのずれ | モデル・migration は変更していない。`alembic check` で差分がないことを確認した |

## 7. Step 4 への引き継ぎ

- **トランザクション境界を明示する（Step 2 から引き継いだ方針）。** 書き込み処理（repository）の中で `add` → `commit()` → `refresh()` を行い、例外が起きたら `rollback()` してから例外を投げ直します。失敗したときにデータが残らないことをテストで確かめます。
- **`POST /inquiries`**
  - 入力スキーマは `InquiryCreate`（title、description、category）です。
  - 検証：前後の空白を除いたうえで、title は 1〜100 文字、description は 1〜2000 文字（どちらもコードポイント単位で Demo 1 と同じ。Pydantic の `max_length` も Python の `len()` と同じく数える）。
  - status は `OPEN` 固定です。入力に含まれていても受け付けません（`extra="forbid"`）。
  - 応答は `201` と `InquiryResponse`。`Location` ヘッダーを付けるかは Step 4 で決めます。
- **`created_at` と `updated_at`：** 登録処理の中で `utc_now()` を 1 回だけ呼び、両方に同じ値を設定します（Step 2 で残した「マイクロ秒単位でずれる」問題の解消）。
- **`PATCH /inquiries/{id}/status`**
  - 本文は `{"status": "..."}`。存在しない id は 404、不正な status は 422 です。
  - id のパスの検証は `routers/inquiries.py` の `InquiryId` を再利用します。
  - `updated_at` は `onupdate` で更新されるので、テストで確かめます。
  - 同じ status に変更した場合に `updated_at` を更新するかは Step 4 で決めます。
- **入力の camelCase：** 今の入力の項目は 1 語なので、camelCase との違いは生じません。複数語の項目を受け付けるようになったら、入力スキーマにも `to_camel` を適用します。
- **422 のメッセージ：** FastAPI の標準（英語）です。画面の項目ごとのエラーを API の 422 から作るのか、frontend の検証を残すのかは、Step 5（frontend との接続）で決めます。
- **Step 5 で行う変換：** frontend の repository で `String(json.id)` への変換と、404 を `null` に変換する処理を行います。frontend の型に `updatedAt` を加えるかも Step 5 で決めます。
- **既知の制約：** SQLite の `lower()` は ASCII しか小文字にしないので、全角英字の大文字小文字は区別されます（Demo 1 の JS の `toLowerCase()` とは違います。PostgreSQL の `ILIKE` はロケールによります）。必要になったら別途検討します。
