# Demo 2 Step 6B — Docker Compose での PostgreSQL 化（SQLite / PostgreSQL の切り替え）

| 項目 | 内容 |
|---|---|
| 状態 | 実装・自動検証まで完了（ブラウザでの受入確認は人間が実施） |
| 実施日 | 2026-10-07 |
| 前提 | [Demo 2 Step 6A](step6a-docker.md)（frontend / backend の Docker 化、DB は SQLite）完了 |
| 環境 | Docker 28.5.1、Docker Compose v2.40.2-desktop.1、`postgres:18-alpine`（PostgreSQL 18.6）、psycopg 3.3.6 |

## 1. 目的とスコープ

`Next.js → FastAPI → SQLAlchemy → SQLite` の構成を、**`DATABASE_URL` を変えるだけで PostgreSQL でも動く**ようにします。Docker Compose では PostgreSQL を使います。

SQLite は、ホストでの開発と既定の pytest のために残します。Step 2 で「SQLite 固有の処理を隔離し、`DATABASE_URL` を変えるだけで移行できる」ように設計したことを、ここで実証します。

**やること**

- psycopg 3 の追加
- Compose への `db` サービス（PostgreSQL 18）の追加
- 秘密情報の管理（ルートの `.env`）
- テストを PostgreSQL でも実行できるようにする（`TEST_DATABASE_URL`、Compose の test プロファイル）
- docs と README

**やらないこと：** アプリの機能追加、frontend の変更、SQLite から PostgreSQL へのデータ移行（デモデータなので migration と seed で作り直す）、CI、Azure

**変更していないもの：** `backend/app/**`（アプリのコード）、migration、seed、frontend のすべて、`backend/data/app.db`

## 2. 構成

```mermaid
flowchart LR
  Browser["ブラウザ"] -->|":3000（ホストに公開するのはここだけ）"| FE["frontend<br/>(node)"]
  FE -->|"http://backend:8000"| BE["backend<br/>(app)"]
  MIG["migrate<br/>alembic upgrade head"] -->|"postgresql+psycopg://…@db:5432"| DB
  BE --> DB[("db: postgres:18-alpine<br/>volume: pgdata<br/>ポートは公開しない")]
```

**起動の順番：** `db`（`pg_isready` で healthy）→ `migrate`（`service_completed_successfully`）→ `backend`（`/health/ready` で healthy）→ `frontend`

| 実行のしかた | DB | 指定方法 |
|---|---|---|
| ホストで開発（`uvicorn --reload`） | SQLite（`backend/data/app.db`） | `DATABASE_URL` を指定しない（今までどおり） |
| ホストで `pytest` | SQLite（テストごとに一時ファイル） | — |
| PostgreSQL でのテスト | 使い捨ての `db-test`（tmpfs） | `docker compose --profile test run --rm backend-test`（`TEST_DATABASE_URL` を指定） |
| Docker Compose | PostgreSQL 18（`db`、volume `pgdata`） | `compose.yaml` で `.env` の値から `DATABASE_URL` を組み立てる |
| Azure（Step 7） | Azure Database for PostgreSQL Flexible Server 18 | `DATABASE_URL=…?sslmode=require`（Container Apps の secrets） |

## 3. 変更したファイル

| ファイル | 区分 | 内容 |
|---|---|---|
| `backend/requirements.txt` | 変更 | `psycopg[binary]==3.3.6` |
| `backend/tests/conftest.py` | 変更 | `TEST_DATABASE_URL` への対応と安全装置（DB 名に `test` が必要）。pytest のヘッダーに使う DB を表示（パスワードは伏せる）。PostgreSQL ではテストの開始前に `public` スキーマを作り直す。`fail_writes` を方言ごとに用意する |
| `backend/tests/db/test_inquiry_model.py` | 変更 | 保存された値の確認を方言ごとにする（PostgreSQL は `to_char(created_at AT TIME ZONE 'UTC', …)`）。NOT NULL 違反のメッセージを、両方の DB に合う正規表現にする |
| `backend/Dockerfile` | 変更 | `base` → `test` → `runtime` の多段階にする（既定のビルド対象は最後の `runtime` で、中身は 6A と同じ。psycopg だけ追加） |
| `backend/.dockerignore` | 変更 | `tests` の除外をやめる（`test` ステージでだけコピーし、`runtime` には含めない） |
| `compose.yaml` | 変更 | `db`、`DATABASE_URL`（YAML のアンカーで 1 か所に定義）、`depends_on`、volume `pgdata`、test プロファイル（`db-test`、`backend-test`）。SQLite の volume `backend-data` を外す |
| `.env.example`（ルート） | 新規 | `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`（仮の値）と、パスワードの作り方 |
| `.gitignore`（ルート） | 変更 | `.env` と `.env.*` を除外し、`!.env.example` で記入例は残す |
| `backend/.env.example` | 変更 | SQLite、PostgreSQL、Azure（`sslmode=require`）、`TEST_DATABASE_URL` の例 |
| `README.md`、`backend/README.md`、`docs/README.md` | 変更 | `.env` の用意、`db` サービス、PostgreSQL でのテストの実行方法。backend の README は、冒頭が Step 4 の時点の記述のままだったので更新 |

## 4. 技術判断

| 判断 | 理由 | 検討した代替案 |
|---|---|---|
| **PostgreSQL 18**（`postgres:18-alpine`） | Azure Database for PostgreSQL Flexible Server が正式に対応している（標準サポートは 2030-11-14 まで。新しく作るサーバーは 18.6）。イメージも 18.6 で、マイナーバージョンまで揃う | 17（2029-11 まで） |
| **psycopg 3**（`psycopg[binary]`、`postgresql+psycopg://`） | SQLAlchemy 2.x が推奨する同期のドライバ。`[binary]` なら slim イメージにコンパイラが要らない。Azure の Entra ID 認証にもドライバを変えずに対応できる | psycopg2（保守のみの段階）、asyncpg（非同期。今の設計と合わない） |
| アプリのコードは変更しない | `session.create_db_engine()` が URL で分岐し、PostgreSQL では `pool_pre_ping=True` を使う。Alembic の batch モードは SQLite のときだけ。Enum は VARCHAR と CHECK 制約、日時は `UTCDateTime`（Step 2 の設計） | — |
| `DATABASE_URL` は `compose.yaml` で組み立て、YAML のアンカー（`x-database-url`）で 1 か所に定義する | `.env` に置く秘密情報を `POSTGRES_*` だけにでき、db・migrate・backend で値が食い違わない。`${VAR:?…}` で未設定なら起動を止める | `.env` に `DATABASE_URL` をそのまま書く（値が重複する） |
| **秘密情報はルートの `.env`**（Git の管理対象外）に置き、記入例は `.env.example` | Compose が自動で読み込む。ビルドの対象は `./backend` と `./frontend` なので、イメージに入らない | `compose.yaml` に直接書く |
| パスワードには `openssl rand -hex 24` を推奨する | `DATABASE_URL` に埋め込むので、URL で特別な意味を持つ記号を避ける（エンコードしなくてよい） | 記号を含めてパーセントエンコードする |
| **`db` のポートは公開しない** | ブラウザもホストも DB に直接アクセスしない。確認には `docker compose exec db psql` を使う | `127.0.0.1:5432` に公開する |
| PostgreSQL 18 の volume は **`/var/lib/postgresql`** にマウントする | 18 の公式イメージは `PGDATA=/var/lib/postgresql/18/docker`、`VOLUME /var/lib/postgresql`（実際のイメージで確認）。17 以前のように `/var/lib/postgresql/data` にマウントすると、データが volume の外に書かれてしまう | `/var/lib/postgresql/data` |
| **テストの既定は SQLite のままで、`TEST_DATABASE_URL` を指定したときだけ PostgreSQL** | ホストでの開発体験を変えない。開発用の `DATABASE_URL` とは別の変数にして、取り違えを防ぐ | `DATABASE_URL` を流用する |
| **`TEST_DATABASE_URL` の DB 名に `test` が含まれていなければ、pytest を開始しない** | テストはスキーマを作り直すので、開発用・本番用の DB を誤って指定したときにデータを守る | 安全装置なし |
| **テストの開始前に `public` スキーマを作り直す**（PostgreSQL） | テーブル、シーケンス、`alembic_version` が空になり、SERIAL の id も 1 から始まるので、SQLite と同じ前提（`id == 1`、seed の 1〜8）がそのまま成り立つ。終了時ではなく開始時に行うので、失敗したテストのデータが残っていても次に影響しない | テストごとに `CREATE DATABASE`（遅い）、終了時に `downgrade base` |
| PostgreSQL の `fail_writes` は、`RAISE EXCEPTION … USING ERRCODE = 'integrity_constraint_violation'` を出すトリガー | SQLite の `RAISE(ABORT)` と同じく `IntegrityError` になるので、テスト側（`pytest.raises(IntegrityError, match="forced failure")`）を変えずに済む | 既定の `RAISE EXCEPTION`（`InternalError` になり、テストの書き換えが必要） |
| PostgreSQL でのテストは Compose の test プロファイル（`db-test` は tmpfs で、ポートは公開しない。`backend-test` は Dockerfile の `test` ステージ） | 開発用の `db` に触れない。データを残さない。ホストに PostgreSQL のクライアントやポートの公開が要らない | ホストの pytest から公開したポートに接続する |
| `db-test` は `.env` の `POSTGRES_USER` と `POSTGRES_PASSWORD` を使い、DB 名は `ai_support_desk_test` に固定する | 秘密情報の置き場所を `.env` だけにする。DB 名に `test` を含めて安全装置を通す | テスト専用の認証情報を `compose.yaml` に直接書く |
| Dockerfile は `base` → `test` → `runtime` の順に並べ、backend は `target: runtime` を明示する | 何も指定せずに `docker build` しても、本番を想定した `runtime` ができる（最後のステージが既定になる）。`runtime` の中身は 6A と同じ（psycopg だけ追加） | `runtime` → `test` の順（既定のビルドがテスト用になってしまう） |
| `test` ステージの pytest は `-p no:cacheprovider` で実行する | `/app` は所有者が root で、`app` ユーザーからは書き込めない（キャッシュを作らない） | — |
| SQLite のデータは移行しない | デモデータなので、migration と seed で作り直す。`backend/data/app.db` は、ホストでの開発用としてそのまま残す | 移行用のスクリプト |

## 5. 検証結果

確認日：2026-10-07。**`backend/data/app.db` は使っていません。** 検証用に、ルートの `.env` を `openssl rand -hex 24` のパスワードで作りました（Git の管理対象外、ファイルの権限は `600`）。パスワードはどこにも表示していません。

### テスト

| 確認内容 | 結果 |
|---|---|
| ホストでの pytest（SQLite） | **111 passed**。非推奨警告をエラー扱いにしても 111 passed。ヘッダーは `test database: SQLite（テストごとの一時ファイル）` |
| `test` イメージでの pytest（SQLite） | 111 passed |
| **PostgreSQL での pytest**（`docker compose --profile test run --rm backend-test`） | **111 passed**。非推奨警告をエラー扱いにしても 111 passed。ヘッダーは `test database: postgresql+psycopg://ai_support_desk:***@db-test:5432/ai_support_desk_test`。`test_models_match_migrations`（`compare_metadata`）、commit 失敗時の rollback（PostgreSQL のトリガー）、CHECK 制約と NOT NULL 違反、日時（`AT TIME ZONE 'UTC'`）、`ILIKE` による検索もすべて通った |
| 安全装置 | `TEST_DATABASE_URL=…/app_dev` で実行すると、`ERROR: TEST_DATABASE_URL の DB 名に 'test' が含まれていません…` と表示して pytest が開始されない |
| `db-test` の後片付け | tmpfs なので、削除したあとに volume は残らない |
| ホストでの `alembic check`（SQLite） | `No new upgrade operations detected.` |

### Docker Compose

| 確認内容 | 結果 |
|---|---|
| まっさらな状態からの `up -d --build`（アプリのイメージも `pgdata` もない状態） | 終了コード 0。backend と frontend を 1 回ずつビルドし、volume `pgdata` を作成 |
| 起動の順番（時刻） | db 02:19:49.579 に開始 → **54.716 に healthy** → migrate 55.190 に開始、55.858 に終了（0）→ backend 56.302 に開始 → healthy → frontend 02:20:01.903 に開始 → healthy |
| migrate のログ | `Will assume transactional DDL.`（PostgreSQL では DDL がトランザクションの中で実行される）、`Running upgrade -> d39d3345e879` |
| PostgreSQL に対する `alembic current` / `alembic check` | `d39d3345e879 (head)` / `No new upgrade operations detected.` |
| `\d inquiries` | id は `integer`（`nextval('inquiries_id_seq')`）、`varchar(100)`、`text`、`varchar(20)` が 2 つ（`status` の既定値は `'OPEN'`）、`timestamp with time zone` が 2 つ。PK は `pk_inquiries`、インデックスは `ix_inquiries_created_at` と `ix_inquiries_status`、CHECK 制約は `ck_inquiries_category` と `ck_inquiries_status`（各 1 つ）。Step 2 の設計どおり |
| サーバー | `server_version` は 18.6、`TimeZone` は UTC。サーバープロセスはすべて `postgres` ユーザー |
| 実行ユーザー | migrate と backend は `app`、frontend は `node` |
| ポート | ホスト → `localhost:3000` は 200。**`localhost:8000` と `localhost:5432` は接続できない**。ホストで待ち受けているのは 3000 番だけ。ポートの割り当ては db `{}`、backend `{}`、frontend `3000/tcp → 3000` |
| seed（手動） | seed 前は 0 件 → 1 回目は「8 件の問い合わせを投入しました。」→ 2 回目は「既にデータがあるため seed をスキップしました。」 |
| frontend 経由の動作 | 一覧は 7, 6, 5, 8, 3, 2, 1, 4 の順。`q=vpn` → [5]。`q=アカウント` → [8, 4]。`q=できない&status=OPEN` → [7, 1]。`/inquiries/1` は 200、`/999` と `/01` は 404。登録は 303 で `/inquiries/9` へ移動。ステータス変更は「更新しました」（対応中） |
| API（frontend のコンテナから呼び出し） | 同じ status への PATCH は 200 で、`updatedAt` は変わらない。日時は `Z` 付きの UTC（例：`2026-09-28T00:15:00Z`） |
| `docker compose restart` | 9 件と、id 9 の「対応中」が残っている |
| `down` → `up -d` | volume `pgdata` は残り、データも残っている。2 回目の migrate で適用した migration は 0 |
| `down -v` → `up -d` | `pgdata` が削除され、0 件になる。seed を手で実行すると 8 件に戻る |
| DB を止めたとき（`docker compose stop db`） | `/health/ready` は `503 {"status":"unavailable"}`。`/inquiries` は HTTP 500 で、JavaScript を実行した後の DOM に `error.tsx` が表示される。HTML に `psycopg`、`postgres`、`5432`、`password` は出ない。backend のログにだけ `psycopg.OperationalError: failed to resolve host 'db'` |
| DB を再開したとき（`docker compose start db`） | backend は healthy のまま使え、一覧もデータも元どおりに表示される（`pool_pre_ping` が切れた接続を捨てて再接続する） |

DB を止めてから 12 秒後の時点では、backend の health はまだ `healthy` でした（healthcheck は 10 秒間隔で、3 回続けて失敗すると `unhealthy` になる）。そのため readiness の 503 は、エンドポイントを直接呼んで確かめました。

### セキュリティ

| 確認内容 | 結果 |
|---|---|
| `.env` | `git check-ignore` で管理対象外。追跡されている `.env` はない。`.env.example` は管理対象 |
| `.env` がない場合 | `docker compose` は `required variable POSTGRES_USER is missing a value: .env に POSTGRES_USER を設定してください` で止まる |
| イメージ（backend・frontend） | 設定の環境変数に `DATABASE_URL`、`POSTGRES_*`、`API_BASE_URL` はない。`docker history` に秘密情報はない。ファイルシステムに `.env` ファイルはなく、`.env` のパスワードの値と一致するファイルもない |
| 実行中のコンテナ | `DATABASE_URL` を受け取るのは backend と migrate だけ（実行時の環境変数）。frontend が受け取るのは `API_BASE_URL=http://backend:8000` だけ |
| `runtime` のイメージ | テスト、pytest、httpx2 は含まない（6A と同じ）。psycopg だけ追加 |
| `docker compose config` の出力 | パスワードを含むので、報告や docs には貼らない（`--quiet` で構文だけを確かめた） |

### ほかに影響していないこと

| 確認内容 | 結果 |
|---|---|
| frontend | 差分は 0 件。`tsc`、`lint`、`build` はどれも終了コード 0 |
| `backend/data/app.db` | SHA-256 `9641ac22…4440`、`Oct 6 23:24:13`、8 件、`max(updated_at)` は `2026-10-03 06:10:00`。Step 6B の前と同じ |
| `git diff --check` | 問題なし。新規ファイルにも末尾の空白はない |

### 実装・検証中に見つかった問題と対応

**テストや起動が失敗する不具合はありませんでした。** 設計の段階で心配していた点と、実装中に気づいた点を記録しておきます。

1. **`compare_metadata` が PostgreSQL の型で差分を出すかもしれない（設計時の P6）：** PostgreSQL に対する `test_models_match_migrations` と `alembic check` は、どちらも差分なしでした。追加の対応は要りませんでした。
2. **PostgreSQL 18 のイメージで、データの置き場所が変わった：** 実際のイメージで `PGDATA=/var/lib/postgresql/18/docker`、`VOLUME /var/lib/postgresql` を確かめてから、`pgdata:/var/lib/postgresql` にマウントしました。`down` → `up` の後もデータが残ることを確認済みです。
3. **PostgreSQL の失敗トリガーで出る例外の種類：** 既定の `RAISE EXCEPTION` は `InternalError` になり、SQLite（`IntegrityError`）とテストの期待値が食い違います。設計では、テスト側を `DBAPIError` で受けるように変える案でした。実装では `ERRCODE = 'integrity_constraint_violation'` を指定して `IntegrityError` に揃え、テストを変えずに済ませました（§7 を参照）。
4. **backend の README の冒頭が古かった：** Step 4 の時点の記述（「frontend との接続はまだ」）のままだったので、今回あわせて更新しました。
5. **6A のコンテナが動いていた：** 作業を始めた時点で、6A の Compose のコンテナ（受入確認用）が 3000 番で動いていました。`compose.yaml` を変える前に `docker compose down` で止めました。6A の SQLite の volume `ai-support-desk_backend-data` は、削除するかどうかを人間が判断する事項なので、残してあります（今の `compose.yaml` からは使いません）。

## 6. Azure への移行を見据えて保った設計

| Step 6B で作ったもの | Azure（Step 7）での扱い |
|---|---|
| `DATABASE_URL=postgresql+psycopg://…` | Flexible Server の URL に `?sslmode=require` を付ける。アプリのコードは変えない（`backend/.env.example` に例を記載） |
| PostgreSQL 18.6 | Flexible Server の 18（新しく作るサーバーは 18.6）と同じバージョン |
| psycopg 3 | そのまま使える。Entra ID の認証（トークンをパスワードとして使う）にもドライバを変えずに対応できる |
| `pool_pre_ping=True` | DB を再開したあとの再接続で効果を確認した。使われていない接続が切断される環境への対策になる |
| `migrate` サービス | Container Apps Job で、同じイメージの `alembic upgrade head` を実行する |
| `/health` と `/health/ready` | liveness と readiness のプローブ（readiness は PostgreSQL への接続を確かめる） |
| backend と DB を公開しない構成 | backend は内部向けの ingress だけにする。Flexible Server はプライベートアクセスかファイアウォールで制限する。CORS は引き続き不要 |
| `TEST_DATABASE_URL` によるテスト | CI（GitHub Actions の `services: postgres:18`）でも、同じ変数で 111 件を流せる |
| `.env` で秘密情報を分けていること | Azure では Container Apps の secrets や Key Vault に置き換える |

## 7. 設計から変更した点

| 設計案 | 実装 | 理由 |
|---|---|---|
| PostgreSQL の `fail_writes` はテスト側を `DBAPIError` で受ける | トリガーで `ERRCODE = 'integrity_constraint_violation'` を指定し、`IntegrityError` に揃える | SQLite と同じ種類の例外になり、テスト（`test_inquiry_write_repository.py`）を変えずに済む |
| Dockerfile は `runtime` と `test` の 2 つのステージ | `base` → `test` → `runtime` の 3 つ | `docker build` は何も指定しないと最後のステージを作るので、`runtime` を最後に置き、本番を想定したイメージが既定になるようにした |
| `db-test` の認証情報（未定） | `.env` の `POSTGRES_USER` と `POSTGRES_PASSWORD` を使い、DB 名は `ai_support_desk_test` に固定 | 秘密情報の置き場所を `.env` だけにする |

## 8. Step 7 への引き継ぎ

- **CI：** backend は SQLite と PostgreSQL（`services: postgres:18` で `TEST_DATABASE_URL` を指定）のマトリクスで pytest を流し、`alembic check` も行う。frontend は `tsc`、`lint`、`build`。両方のイメージのビルド。
- **Azure：** ACR、Container Apps（frontend は外部向け、backend は内部向けの ingress）、Container Apps Job（migrate）、Flexible Server 18（`sslmode=require`、プライベートアクセス）、Key Vault や secrets。**本番では `API_BASE_URL` を必須にする。** migration 用とアプリ用で DB のユーザーを分けることも検討する。
- **イメージのバージョン：** `postgres:18-alpine`、`python:3.11-slim`、`node:22-alpine` をマイナーバージョンや digest まで固定するかを判断する。
- **使っていない volume：** `ai-support-desk_backend-data`（6A の SQLite）は今の構成では使わない。不要なら `docker volume rm ai-support-desk_backend-data` で削除する。
