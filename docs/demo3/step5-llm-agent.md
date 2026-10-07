# Demo 3 Step 5 — LLM Agent（Provider の差し替え・OpenAI Responses API Adapter・フォールバック）

| 項目 | 内容 |
|---|---|
| 状態 | 実装・自動検証まで完了（5-A〜5-E はコミット済み、5-F は最終検証と文書化） |
| 実施日 | 2026-10-07 |
| 前提 | [Demo 3 Step 4](step4-inquiry-draft.md)（起票案 Tool と Human-in-the-loop）、[Step 6](demo-script.md)（面談デモの整備）完了 |
| 実 API | **OpenAI の実 API には接続していません。** Adapter は Mock / Fake によるテストまで実装済みで、実 API への接続は任意です |
| デモの既定 | `AGENT_PROVIDER=rule`（RuleBasedAgent）。外部 LLM API・API キーなしで動き、追加費用はかかりません |

## 1. 目的

Step 1〜4 で、RuleBasedAgent を使って Tool の契約（名前・説明・引数の JSON Schema）と業務フロー（FAQ 回答 → 起票案 → 人が登録）を固めました。Step 5 では、**Tool を選ぶ判断を LLM に任せられる構造**を追加します。ただし、次の 3 つは変えません。

- API（`POST /agent/chat` の入出力）と画面
- Human-in-the-loop（Agent は DB に書き込まず、登録は人が既存の `POST /inquiries` で行う）
- RuleBasedAgent でデモが動くこと（既定）

## 2. Before / After

| | Before（Step 4 まで） | After（Step 5） |
|---|---|---|
| Agent | RuleBasedAgent だけ | `AGENT_PROVIDER` で RuleBasedAgent / LLM Agent を切り替える |
| Tool の選択 | 決まった手順（ルール） | rule：決まった手順 ／ openai：LLM の tool calling（許可リストの 2 つの Tool だけ） |
| LLM との接続 | なし | `LLMClient` Protocol ＋ `OpenAIResponsesClient`（OpenAI Responses API の Adapter） |
| 障害時 | — | LLM 層の障害は RuleBasedAgent にフォールバック（既定で有効） |
| 設定 | `DATABASE_URL` | `AGENT_*`・`OPENAI_*` を追加（backend だけに渡す） |
| frontend | 全 API のタイムアウト 10 秒 | `POST /agent/chat` だけ 30 秒、その他は 10 秒のまま |
| テスト | 209 件 | 378 件（SQLite / PostgreSQL の両方） |

## 3. Architecture

```
Browser（/chat）
  ↓ Server Action（ブラウザの通信先は Next.js のみ）
Next.js（frontend）── POST /agent/chat（HTTP の待機 30 秒）
  ↓
FastAPI（backend）  routers/agent.py
  ↓ Depends(get_agent)  … @lru_cache で 1 回だけ組み立てる
agents/factory.py  build_agent(settings)
  ↓ AGENT_PROVIDER
  ├─ rule（既定）→ RuleBasedAgent
  └─ openai     → FallbackAgent                      （AGENT_FALLBACK_TO_RULE=false なら LLMAgent だけ）
                   ├─ primary : LLMAgent
                   │             ↓ LLMClient Protocol（provider 中立）
                   │           OpenAIResponsesClient（openai SDK を import するのはここだけ）
                   │             ↓
                   │           OpenAI Responses API
                   └─ fallback: RuleBasedAgent
  ↓ Tool は許可リスト（tools/registry.py）から実行
  ├─ search_faqs    … FAQ 検索（読み取りのみ）
  └─ draft_inquiry  … 起票案の作成（DB を使わない）
  ↓
PostgreSQL（faqs / inquiries）

起票案 → 人が /inquiries/new で確認・修正 → 既存の POST /inquiries で登録（ここで初めて INSERT）
```

| ファイル | 役割 |
|---|---|
| `app/config.py` | `AGENT_*`・`OPENAI_*` の設定と検証（openai のときだけキーとモデルを必須にする） |
| `app/agents/factory.py` | Settings から Agent を組み立てる |
| `app/agents/fallback.py` | FallbackAgent（LLM 層の障害だけを捕まえて RuleBasedAgent で応答） |
| `app/agents/llm/client.py` | `LLMClient` Protocol、`LLMRequest`・`LLMTurn`・`LLMFunctionCall`、`LLMError` 系の例外 |
| `app/agents/llm/agent.py` | LLMAgent（tool calling のループ、上限、AgentReply の組み立て） |
| `app/agents/llm/openai_client.py` | OpenAIResponsesClient（Responses API との変換） |
| `app/agents/llm/prompts.py` | システム指示 |
| `app/tools/registry.py` | LLM に公開する Tool の許可リスト（strict の JSON Schema・引数の検証・実行） |
| `app/agents/rule_based.py` | RuleBasedAgent（**変更なし**） |

## 4. Provider switching

| 設定 | 既定値 | 説明 |
|---|---|---|
| `AGENT_PROVIDER` | `rule` | `rule` / `openai`。それ以外は起動時に検証エラー |
| `AGENT_FALLBACK_TO_RULE` | `true` | openai のとき、LLM 層の障害で RuleBasedAgent に切り替える |
| `AGENT_MAX_LLM_ROUNDS` | 3（1〜10） | Tool 呼び出しの往復に使う LLM 呼び出しの回数（最後の締めの 1 回は別） |
| `AGENT_MAX_TOOL_CALLS` | 4（1〜10） | 1 回の応答で実行する Tool の合計回数 |
| `AGENT_TIMEOUT_SECONDS` | 20（0 より大きく 120 以下） | 1 回の応答全体にかける時間の上限（backend 側） |
| `OPENAI_API_KEY` | なし | openai のときだけ必須。`SecretStr` で保持 |
| `OPENAI_MODEL` | なし | openai のときだけ必須。**コードに固定しない** |
| `OPENAI_BASE_URL` | なし（SDK の既定） | OpenAI 互換のエンドポイントへの差し替え用 |
| `OPENAI_TIMEOUT_SECONDS` | 10（0 より大きく 60 以下） | OpenAI API 1 回の呼び出しのタイムアウト |
| `OPENAI_MAX_RETRIES` | 1（0〜5） | SDK の再試行回数 |
| `OPENAI_MAX_OUTPUT_TOKENS` | 800（1〜4000） | LLM 1 回の最大出力トークン数 |

- `get_agent()` は `@lru_cache(maxsize=1)` で、初回に 1 度だけ Agent（と OpenAI クライアント）を組み立てて再利用します。Agent はリクエストごとの状態を持ちません。
- 応答に「どの Agent が答えたか」は含めません（API の形を変えないため）。

## 5. LLMClient Protocol

```python
class LLMClient(Protocol):
    def create_turn(self, request: LLMRequest) -> LLMTurn: ...
```

- LLMAgent はこの Protocol にだけ依存し、OpenAI SDK の型・例外を知りません。プロバイダを追加するときは Adapter を 1 つ書くだけです。
- `LLMRequest`：システム指示、input items、Tool の定義、`tool_choice`（required / auto / none）、最大出力トークン数、1 ターンの Tool 呼び出し数、並列呼び出しの可否。
- `LLMTurn`：Tool の呼び出し要求（`call_id`・名前・未検証の引数 JSON）、テキスト、次のターンに積む output items。
- 失敗は `LLMError` 系の例外にそろえます：`LLMProviderError`（kind：timeout / connection / rate_limit / authentication / permission / bad_request / server / api、status_code、request_id）、`LLMResponseError`（応答が不正）、`LLMTimeoutError`（Agent 全体の時間切れ）。
- テストでは `FakeLLMClient`（決まった応答を順に返す）と `FakeClock` を使い、ネットワークなしで LLMAgent を検証します。

## 6. OpenAIResponsesClient

- 同期の OpenAI SDK（`openai==3.26.0`）を使います。router・Agent・SQLAlchemy の Session がすべて同期のためです。
- `store=False`：会話の状態を OpenAI 側に保存しません。`previous_response_id` は使わず、前のターンの output items と `function_call_output` を毎回 input に積んで送ります。
- `include=["reasoning.encrypted_content"]`：`store=False` でも、推論モデルの reasoning item を次のターンに引き継げるようにします（推論モデル以外での扱いは、実 API での確認事項として残しています）。
- `parallel_tool_calls=False`、1 ターンの Tool 呼び出しは 1 つ（`max_tool_calls=1`）。
- SDK の例外は `LLMProviderError` に変換し、`from None` で元の例外の連鎖を切ります。例外のメッセージ・属性に API キー・プロンプト・応答本文を含めません。
- openai SDK を import するのは backend 全体でこのモジュールだけです（テストで構文解析して確認）。
- テストは `httpx2.MockTransport` を SDK に渡して行い、実際の通信はしません。

## 7. Tool Calling

```
利用者のメッセージ
  → LLM（1 回目は tool_choice=required：必ず Tool を根拠にさせる）
  → function_call（例：search_faqs {"query": "..."}）
  → 許可リストで検証・実行 → function_call_output（同じ call_id）
  → LLM（2 回目以降は tool_choice=auto）→ …
  → 最終テキスト
  → AgentReply（action・matchedFaqs・inquiryDraft・toolCalls は Tool の実行結果だけから作る）
```

- LLM の文章に書かれた FAQ や起票案は、構造化データ（`matchedFaqs`・`inquiryDraft`）に使いません（LLM がでっち上げた FAQ が画面のカードにならない）。
- `action` もコードで決めます：起票案がある → `INQUIRY_DRAFTED`、FAQ が見つかった → `FAQ_ANSWER`、それ以外 → `INQUIRY_SUGGESTED`。
- 起票案があるときは、LLM の文章とは別に「まだ登録されていません」という案内（`DRAFT_GUIDE`）を必ず付けます。
- 最終メッセージは 2000 文字までに切り詰めます。空の場合はエラー（フォールバックの対象）です。

## 8. Tool allowlist

| Tool | LLM に見せる引数 | サーバー側で固定・検証 | 1 回の応答での上限 |
|---|---|---|---|
| `search_faqs` | `query`（文字列） | 件数 `limit` は 3 に固定（LLM には公開しない） | 2 回 |
| `draft_inquiry` | `message`（文字列） | 既存の `DraftInquiryArgs` で長さを検証。DB を使わない | 1 回 |

- 許可リストは読み取り専用の `MappingProxyType`。Tool 名から関数を動的に探して呼ぶことはしません。
- JSON Schema は strict（全項目が required、`additionalProperties: false`）。公開していない項目を渡されたら実行しません。
- **登録・更新・削除の Tool（`create_inquiry` など）は存在しません。** repository や SQL も LLM に公開しません。
- 未知の Tool・不正な引数・上限を超えた呼び出しは実行せず、例外の内容を含まない定型のエラー（`unknown_tool` / `invalid_arguments` / `tool_call_limit_reached`）だけを LLM に返します。
- Tool の結果に含まれる文章に指示が書かれていても従わないよう、システム指示で明示しています（安全性は指示だけに頼らず、上の構造で担保します）。

## 9. Bounded loop

無限ループや長時間化を防ぐため、LLMAgent の処理には上限を設けています。

- LLM の往復は `AGENT_MAX_LLM_ROUNDS`（3）回まで。上限に達したら `tool_choice=none` で最終回答を 1 回だけ求めます。その応答でもまだ Tool を要求したらエラーです。
- Tool の実行は合計 `AGENT_MAX_TOOL_CALLS`（4）回まで、Tool ごとの上限（search 2 回・draft 1 回）もあります。上限に達したら、それ以降は Tool を使わずに回答させます。
- 1 ターンで要求できる Tool は 1 つ、並列呼び出しは無効です。

したがって、1 回の応答で OpenAI API を呼ぶのは最大で 4 回（3 往復 ＋ 締めの 1 回）です。SDK の再試行は別に数えます。

## 10. Timeout

時間の上限は 3 つあり、それぞれ別の設定です。混同しないように分けています。

| 設定 | 場所 | 意味 |
|---|---|---|
| `OPENAI_TIMEOUT_SECONDS`（10 秒）× (1 + `OPENAI_MAX_RETRIES`) | backend → OpenAI | OpenAI API 1 回の呼び出しの待ち時間（SDK の再試行を含む） |
| `AGENT_TIMEOUT_SECONDS`（20 秒） | backend | LLMAgent 1 回の応答全体の上限。**各 LLM 呼び出しの前後で判定**し、超えていたら `LLMTimeoutError`（フォールバックの対象） |
| `AGENT_REQUEST_TIMEOUT_MS`（30 秒） | frontend → backend | Next.js が `POST /agent/chat` の応答を待つ HTTP の時間。その他の API は `DEFAULT_REQUEST_TIMEOUT_MS`（10 秒）のまま |

- frontend の 30 秒は backend の 20 秒より長くして、backend の応答（フォールバックした RuleBasedAgent の応答を含む）を待てるようにしています。
- **注意：** `AGENT_TIMEOUT_SECONDS` は呼び出しの境目で判定するため、実行中の OpenAI 呼び出しは途中で止めません。上限の直前に始まった呼び出しが長引くと（最大で 1 回の呼び出しの時間だけ）20 秒を超えることがあります。実 API で応答時間を測ってから、必要なら値を調整します。
- frontend がタイムアウトした場合は、既存のエラー処理で「AIサポートに接続できませんでした。時間をおいて再度お試しください。」を表示し、入力内容は残します。

## 11. Fallback

- `FallbackAgent` は `LLMError` 系（プロバイダの障害・応答の不正・時間切れ）だけを捕まえ、RuleBasedAgent で応答し直します。利用者には通常の応答が返ります。
- DB の障害（`SQLAlchemyError`）やその他の例外は捕まえません。RuleBasedAgent も同じ DB を使うので切り替えても解決せず、原因を隠さないためです（既存の API のエラー方針のまま）。
- LLM の Tool は読み取りと DB を使わない起票案だけなので、途中まで実行してからフォールバックしても副作用はありません。途中の Tool の結果がフォールバック後の応答に混ざらないこともテストで確認しています。
- フォールバック時の WARNING ログには、安全な項目（例外の型・kind・status_code・request_id・フォールバック先の Agent 名）だけを出します。利用者のメッセージ・プロンプト・API キー・応答本文・例外のメッセージは出しません。

## 12. Human-in-the-loop

Step 4 の方針をそのまま維持しています。

- LLMAgent・RuleBasedAgent・Tool はどれも DB に書き込みません。
- 起票案は画面の起票案カードから既存の `/inquiries/new` に引き継ぐだけで、人が確認・修正して「登録する」を押したときだけ、既存の `POST /inquiries` で登録されます。
- テストでの保証：
  - Agent の応答中に実行された SQL を記録し、`INSERT` / `UPDATE` / `DELETE` がないこと（RuleBasedAgent・LLMAgent・API 経由の 3 か所）
  - `agents/`・`tools/`・`agents/llm/` が書き込みの関数やモデルを import していないこと（構文解析）
- E2E（5-F）：Agent の処理前 11 件 → 処理後 11 件 → 人が登録した後 12 件。

## 13. Security

| 観点 | 対策 |
|---|---|
| API キーの置き場所 | backend の環境変数だけ（Compose の `backend.environment`、または `backend/.env`）。frontend・migrate には渡さない。compose.yaml・Dockerfile・ソース・`.env.example` に値を書かない |
| ブラウザ | ブラウザは Next.js とだけ通信。FastAPI・DB はホストに公開せず（公開ポートは 3000 だけ）、CORS もなし |
| 権限の最小化 | LLM が使えるのは許可リストの 2 つの Tool だけ。登録の手段はない |
| プロンプトインジェクション | Tool の結果の文章に従わないよう指示し、さらに構造（許可リスト・strict schema・上限・構造化データは Tool の結果からのみ）で被害を限定 |
| ログ | フォールバックのログは安全な項目だけ。利用者のメッセージ・プロンプト・応答本文は出さない |
| 外部への保存 | `store=False`（OpenAI 側に会話の状態を保存しない） |

## 14. Secret handling

- `OPENAI_API_KEY` は `SecretStr` で保持し、`repr`・`str`・`model_dump()` に値が出ません。OpenAIResponsesClient も属性・`repr` にキーを持ちません。
- Settings は `hide_input_in_errors=True`（pydantic-settings 2.15.0 の `SettingsConfigDict` が正式にサポートする設定）にしています。設定エラーの `str` / `repr` には「どの項目が不正か」だけを出し、入力値（API キー・DB のパスワードなど）を出しません。
  - 修正前は、openai を指定してモデルを入れ忘れた場合などに、入力全体（キーを含む）がエラーのメッセージに出ることを再現しました。表示の省略に頼らず、構造的に防いでいます。
  - `ValidationError.errors()` の戻り値には入力値が残るため、これをログに出す処理は書きません（5-F 時点で使用箇所なし）。
- `docker compose config` の出力にはパスワード・API キーが含まれるため共有しません（compose.yaml の冒頭にも記載）。
- ルートの `.gitignore` で `.env`・`.env.*` を除外し、`.env.example` だけを管理しています。

## 15. Testing strategy

**実 API を呼ばずに、LLM 経路のすべてをテストします。**

| テスト | 件数（parametrize を含む） | 内容 |
|---|---|---|
| `tests/test_agent_settings.py` | 27 | 既定値、openai のときの必須項目、範囲外の値、空の値、キーが repr・エラーに出ないこと |
| `tests/agents/test_tool_registry.py` | 31 | 許可リストがちょうど 2 つ、読み取り専用、strict schema、limit を公開しない、未知の Tool・不正な引数の拒否、DB に書き込まないこと |
| `tests/agents/test_llm_agent.py` | 36 | FAQ 回答・起票案の流れ、call_id の対応、未知の Tool・不正な引数・上限、往復の上限、`tool_choice` の順序、時間切れ、でっち上げた FAQ・起票案を無視、DB に書き込まないこと |
| `tests/agents/test_openai_client.py` | 37 | リクエストの変換、function_call・reasoning item の解析、`function_call_output` を含む往復、ステータスエラー（429 rate_limit・401 authentication・403・400・404・500・503）と通信エラー（timeout・connection）の変換、再試行回数、キー・メッセージが漏れないこと、SDK を import するのは Adapter だけ |
| `tests/agents/test_fallback_agent.py` | 21 | LLM 障害でのフォールバック、DB 障害は捕まえないこと、ログの項目 |
| `tests/agents/test_agent_factory.py` | 7 | provider ごとの組み立て、設定の受け渡し |
| `tests/test_agent_router.py` | 10 | 既定が RuleBasedAgent で応答の形が変わらないこと、LLM Agent・FallbackAgent を API 経由で使えること、Agent を 1 回だけ組み立てること |

- Step 5 で追加したのは上の 7 ファイル（計 169 件。Step 4 までの 209 件はそのまま）です。テストの合計は 378 件で、SQLite と PostgreSQL（Compose の test プロファイル）の両方で、警告をエラー扱いにしても全件成功しています。
- frontend：`tsc --noEmit`・`npm run lint`・`npm run build`。build した server bundle で、`/agent/chat` だけ `timeoutMs:3e4`、それ以外は既定の `1e4` であることを確認しています。
- E2E：Docker Compose（PostgreSQL）＋ヘッドレス Chrome で、rule provider の FAQ 回答・起票案・人による登録を確認しています。

## 16. Cost policy

- デモの既定は `AGENT_PROVIDER=rule` です。外部の LLM API（OpenAI・Anthropic・Claude など）を呼ばないため、**追加費用はかかりません。** API キーも不要です。
- Step 5 の開発と検証では、実際の OpenAI API に一度も接続していません（テストは Fake / Mock、Compose での確認は偽のキーで設定の読み取りまで）。
- 実 API に接続する場合は任意で、`.env` に `AGENT_PROVIDER=openai`・`OPENAI_API_KEY`・`OPENAI_MODEL` を設定します。1 回の応答あたりの呼び出しは最大 4 回、出力は 1 回 800 トークンまでに制限しています。

## 17. Azure への将来の拡張

- **現在は Azure に未デプロイです。** Azure のリソースは作成していません。
- Step 5 完了後に、無料枠を中心にした別の工程として設計・デプロイする予定です。
- 想定している構成（未確定）：frontend・backend のコンテナを Azure Container Apps などで動かし、DB は Azure Database for PostgreSQL Flexible Server（`sslmode=require`）、API キーは Key Vault などから backend の環境変数としてだけ渡す。backend は内部向けにして公開しない構成を維持する。
- Azure OpenAI を使う場合も、`LLMClient` Protocol の Adapter を追加する（または `OPENAI_BASE_URL` を使う）形で、LLMAgent・Tool・API・画面は変えない方針です。ただし、Azure OpenAI の利用は費用が発生するため、デプロイ工程でも既定は rule のままにします。

## 18. 残っている事項（実 API に接続する場合）

- 実 API での最小限の動作確認（`include=["reasoning.encrypted_content"]` を推論モデル以外のモデルが受け付けるか、日本語の応答の質、1 回の応答にかかる時間）。
- 応答時間を測ったうえで、`AGENT_TIMEOUT_SECONDS`・`OPENAI_TIMEOUT_SECONDS`・frontend の 30 秒の関係を見直す（第 10 節の注意）。
- openai provider とフォールバックの画面での E2E（実 API または偽の OpenAI 互換サーバーを使う）。
