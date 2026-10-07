"""OpenAIResponsesClient（Demo 3 Step 5-C）のテスト。

実際の OpenAI API には通信しない。httpx2.MockTransport を SDK に渡し、送信されたリクエスト JSON を記録して、
用意した Responses API の JSON を返す。API キーはテスト用の偽の値だけを使う。
"""

import ast
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from sqlalchemy.orm import Session

from app.agents.base import AgentAction
from app.agents.llm.agent import LLMAgent
from app.agents.llm.client import (
    LLMError,
    LLMFunctionCall,
    LLMProviderError,
    LLMRequest,
    LLMResponseError,
)
from app.agents.llm.openai_client import OpenAIResponsesClient
from app.agents.rule_based import DRAFT_GUIDE
from app.config import BACKEND_DIR, Settings
from app.db.seed import seed_faqs
from app.tools.registry import function_tool_definitions

FAKE_KEY = "sk-test-mock-only-0123456789"
MODEL = "test-model-from-settings"
USER_MESSAGE = "VPNがすぐ切れます"


# --- Mock の補助 -----------------------------------------------------------------------------


def response_json(output: list[dict[str, Any]], *, status: str = "completed", rid: str = "resp_1") -> dict[str, Any]:
    return {
        "id": rid,
        "object": "response",
        "created_at": 1760000000,
        "model": MODEL,
        "status": status,
        "output": output,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "metadata": {},
    }


def function_call_item(name: str, arguments: dict[str, Any] | str, call_id: str, item_id: str = "fc_1") -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": item_id,
        "call_id": call_id,
        "name": name,
        "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False),
        "status": "completed",
    }


def message_item(text: str, item_id: str = "msg_1") -> dict[str, Any]:
    return {
        "type": "message",
        "id": item_id,
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


class MockOpenAI:
    """MockTransport のハンドラー。リクエストを記録し、用意した応答（または例外）を順に返す。"""

    def __init__(self, responses: list[httpx2.Response | Exception | dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if len(self.requests) > len(self._responses):
            raise AssertionError(f"unexpected HTTP request #{len(self.requests)}")
        item = self._responses[len(self.requests) - 1]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return httpx2.Response(200, json=item)
        return item

    def body(self, index: int) -> dict[str, Any]:
        return json.loads(self.requests[index].content)


def make_client(mock: MockOpenAI, **kwargs: Any) -> OpenAIResponsesClient:
    options: dict[str, Any] = {"api_key": FAKE_KEY, "model": MODEL, "max_retries": 0}
    options.update(kwargs)
    return OpenAIResponsesClient(
        http_client=httpx2.Client(transport=httpx2.MockTransport(mock)), **options
    )


def make_request(**overrides: Any) -> LLMRequest:
    values: dict[str, Any] = {
        "instructions": "SYSTEM",
        "input_items": [{"role": "user", "content": USER_MESSAGE}],
        "tools": function_tool_definitions(),
        "tool_choice": "required",
        "max_output_tokens": 800,
        "max_tool_calls": 1,
        "parallel_tool_calls": False,
    }
    values.update(overrides)
    return LLMRequest(**values)


@pytest.fixture
def seeded(db_session: Session) -> Session:
    seed_faqs(db_session)
    return db_session


# --- LLMRequest → Responses API ---------------------------------------------------------------


def test_request_parameters_are_mapped() -> None:
    mock = MockOpenAI([response_json([message_item("回答")])])

    make_client(mock).create_turn(make_request())

    request = mock.requests[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/responses")
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = mock.body(0)
    assert body == {
        "model": MODEL,
        "instructions": "SYSTEM",
        "input": [{"role": "user", "content": USER_MESSAGE}],
        "tools": function_tool_definitions(),
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "max_tool_calls": 1,
        "max_output_tokens": 800,
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }
    assert "previous_response_id" not in body


@pytest.mark.parametrize("tool_choice", ["required", "auto", "none"])
def test_tool_choice_is_passed_through(tool_choice: str) -> None:
    mock = MockOpenAI([response_json([message_item("回答")])])

    make_client(mock).create_turn(make_request(tool_choice=tool_choice, max_tool_calls=None if tool_choice == "none" else 1))

    body = mock.body(0)
    assert body["tool_choice"] == tool_choice
    assert body["store"] is False
    # tool_choice=none では max_tool_calls を送らない（LLMAgent が None を渡す）
    assert ("max_tool_calls" in body) is (tool_choice != "none")


def test_request_items_are_not_mutated_by_client() -> None:
    mock = MockOpenAI([response_json([message_item("回答")])])
    request = make_request()
    snapshot = json.dumps([request.input_items, request.tools], ensure_ascii=False)

    make_client(mock).create_turn(request)

    assert json.dumps([request.input_items, request.tools], ensure_ascii=False) == snapshot


def test_model_and_key_come_from_settings() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        agent_provider="openai",
        openai_api_key=FAKE_KEY,
        openai_model=MODEL,
        openai_base_url="https://llm.example.test/v1",
        openai_timeout_seconds=7.5,
        openai_max_retries=0,
    )
    mock = MockOpenAI([response_json([message_item("回答")])])

    client = OpenAIResponsesClient.from_settings(
        settings, http_client=httpx2.Client(transport=httpx2.MockTransport(mock))
    )
    client.create_turn(make_request())

    assert client.model == MODEL
    assert mock.body(0)["model"] == MODEL
    assert str(mock.requests[0].url) == "https://llm.example.test/v1/responses"
    assert mock.requests[0].headers["authorization"] == f"Bearer {FAKE_KEY}"


@pytest.mark.parametrize(
    "overrides",
    [{"openai_api_key": None}, {"openai_model": None}],
)
def test_from_settings_requires_key_and_model(overrides: dict[str, Any]) -> None:
    values: dict[str, Any] = {"openai_api_key": FAKE_KEY, "openai_model": MODEL}
    values.update(overrides)
    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]

    with pytest.raises(ValueError) as error:
        OpenAIResponsesClient.from_settings(settings)
    assert FAKE_KEY not in str(error.value)


@pytest.mark.parametrize(("api_key", "model"), [("", MODEL), ("  ", MODEL), (FAKE_KEY, ""), (FAKE_KEY, " ")])
def test_blank_key_or_model_is_rejected(api_key: str, model: str) -> None:
    with pytest.raises(ValueError):
        OpenAIResponsesClient(api_key=api_key, model=model)


def test_api_key_is_not_exposed_in_repr() -> None:
    client = make_client(MockOpenAI([]))

    assert FAKE_KEY not in repr(client)
    assert FAKE_KEY not in str(vars(client).keys())
    assert "_model" in vars(client) and "api_key" not in vars(client)


# --- Responses API → LLMTurn ------------------------------------------------------------------


def test_function_call_is_parsed() -> None:
    mock = MockOpenAI([response_json([function_call_item("search_faqs", {"query": "VPN"}, "call_123")])])

    turn = make_client(mock).create_turn(make_request())

    assert turn.function_calls == [
        LLMFunctionCall(call_id="call_123", name="search_faqs", arguments='{"query": "VPN"}')
    ]
    assert turn.output_text == ""
    assert turn.output_items == [function_call_item("search_faqs", {"query": "VPN"}, "call_123")]


def test_text_response_is_parsed_into_plain_dicts() -> None:
    mock = MockOpenAI([response_json([message_item("VPN クライアントを更新してください。")])])

    turn = make_client(mock).create_turn(make_request(tool_choice="none", max_tool_calls=None))

    assert turn.function_calls == []
    assert turn.output_text == "VPN クライアントを更新してください。"
    assert turn.output_items == [message_item("VPN クライアントを更新してください。")]
    # SDK 固有の型を LLMAgent 側へ渡さない（素の dict / list / str だけ）
    assert all(type(item) is dict for item in turn.output_items)
    json.dumps(turn.output_items, ensure_ascii=False)


def test_reasoning_items_are_kept_for_next_turn() -> None:
    reasoning = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "opaque"}
    mock = MockOpenAI([response_json([reasoning, function_call_item("search_faqs", {"query": "VPN"}, "call_1")])])

    turn = make_client(mock).create_turn(make_request())

    assert turn.output_items[0] == reasoning
    assert [call.call_id for call in turn.function_calls] == ["call_1"]


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_failed_response_is_an_error(status: str) -> None:
    mock = MockOpenAI([response_json([], status=status)])

    with pytest.raises(LLMResponseError):
        make_client(mock).create_turn(make_request())


@pytest.mark.parametrize(
    "item",
    [
        {"type": "function_call", "id": "fc_1", "call_id": "call_1", "arguments": "{}", "status": "completed"},
        {"type": "function_call", "id": "fc_1", "name": "search_faqs", "arguments": "{}", "status": "completed"},
        {"type": "function_call", "id": "fc_1", "call_id": "", "name": "search_faqs", "arguments": "{}", "status": "completed"},
    ],
)
def test_malformed_function_call_is_an_error(item: dict[str, Any]) -> None:
    mock = MockOpenAI([response_json([item])])

    with pytest.raises(LLMResponseError):
        make_client(mock).create_turn(make_request())


# --- function_call → Tool 実行 → function_call_output → 次の呼び出し（LLMAgent と結合）-------------


def test_round_trip_with_llm_agent_keeps_call_ids(seeded: Session) -> None:
    mock = MockOpenAI(
        [
            response_json([function_call_item("search_faqs", {"query": USER_MESSAGE}, "call_search_1")], rid="resp_1"),
            response_json([message_item("VPN クライアントを最新版に更新してください。")], rid="resp_2"),
        ]
    )

    reply = LLMAgent(make_client(mock)).respond(seeded, USER_MESSAGE)

    assert reply.action is AgentAction.FAQ_ANSWER
    assert reply.message == "VPN クライアントを最新版に更新してください。"
    assert [m.faq.question for m in reply.matched_faqs] == ["VPN が頻繁に切断されます"]
    first, second = mock.body(0), mock.body(1)
    assert first["tool_choice"] == "required"
    assert second["tool_choice"] == "auto"
    # 2 回目の input: ユーザー発話 → 前ターンの function_call → 同じ call_id の function_call_output
    assert second["input"][0] == {"role": "user", "content": USER_MESSAGE}
    assert second["input"][1] == function_call_item("search_faqs", {"query": USER_MESSAGE}, "call_search_1")
    output_item = second["input"][2]
    assert output_item["type"] == "function_call_output"
    assert output_item["call_id"] == "call_search_1"
    assert json.loads(output_item["output"])["faqs"][0]["question"] == "VPN が頻繁に切断されます"
    for body in (first, second):
        assert body["store"] is False
        assert "previous_response_id" not in body


def test_round_trip_with_draft_keeps_each_call_id(seeded: Session) -> None:
    message = "プリンタで両面印刷できません。\n問い合わせとして登録して"
    mock = MockOpenAI(
        [
            response_json([function_call_item("search_faqs", {"query": "プリンタで両面印刷できません"}, "call_A", "fc_A")]),
            response_json([function_call_item("draft_inquiry", {"message": message}, "call_B", "fc_B")]),
            response_json([message_item("起票案を作成しました。")]),
        ]
    )

    reply = LLMAgent(make_client(mock)).respond(seeded, message)

    assert reply.action is AgentAction.INQUIRY_DRAFTED
    assert reply.inquiry_draft is not None
    assert reply.message.endswith(DRAFT_GUIDE)
    third = mock.body(2)
    pairs = [
        (item["type"], item["call_id"])
        for item in third["input"]
        if item.get("type") in ("function_call", "function_call_output")
    ]
    assert pairs == [
        ("function_call", "call_A"),
        ("function_call_output", "call_A"),
        ("function_call", "call_B"),
        ("function_call_output", "call_B"),
    ]
    outputs = {item["call_id"]: json.loads(item["output"]) for item in third["input"] if item.get("type") == "function_call_output"}
    assert "faqs" in outputs["call_A"]
    assert outputs["call_B"]["draft"]["title"] == "プリンタで両面印刷できません"
    assert [mock.body(i)["tool_choice"] for i in range(3)] == ["required", "auto", "auto"]
    assert all(mock.body(i)["store"] is False for i in range(3))


# --- OpenAI 例外 → LLMProviderError -------------------------------------------------------------


def status_response(code: int, request_id: str = "req_test_1") -> httpx2.Response:
    return httpx2.Response(
        code,
        json={"error": {"message": f"echo {USER_MESSAGE} {FAKE_KEY}", "type": "error", "code": None}},
        headers={"x-request-id": request_id},
    )


@pytest.mark.parametrize(
    ("response", "kind", "status_code"),
    [
        (status_response(429), "rate_limit", 429),
        (status_response(401), "authentication", 401),
        (status_response(403), "permission", 403),
        (status_response(400), "bad_request", 400),
        (status_response(404), "bad_request", 404),
        (status_response(500), "server", 500),
        (status_response(503), "server", 503),
    ],
)
def test_status_errors_are_converted(response: httpx2.Response, kind: str, status_code: int) -> None:
    mock = MockOpenAI([response])

    with pytest.raises(LLMProviderError) as error:
        make_client(mock).create_turn(make_request())

    assert error.value.kind == kind
    assert error.value.status_code == status_code
    assert error.value.request_id == "req_test_1"
    assert_no_leak(error.value)


@pytest.mark.parametrize(
    ("exception", "kind"),
    [
        (httpx2.ReadTimeout("timed out"), "timeout"),
        (httpx2.ConnectTimeout("timed out"), "timeout"),
        (httpx2.ConnectError("connection refused"), "connection"),
    ],
)
def test_transport_errors_are_converted(exception: Exception, kind: str) -> None:
    mock = MockOpenAI([exception])

    with pytest.raises(LLMProviderError) as error:
        make_client(mock).create_turn(make_request())

    assert error.value.kind == kind
    assert error.value.status_code is None
    assert_no_leak(error.value)


def assert_no_leak(error: LLMProviderError) -> None:
    import openai

    assert isinstance(error, LLMError)
    assert not isinstance(error, openai.APIError)  # SDK 固有の例外を Agent 層へ出さない
    assert error.__cause__ is None and error.__suppress_context__  # 元の例外の連鎖を切っている
    for text in (str(error), repr(error), str(vars(error))):
        assert FAKE_KEY not in text
        assert USER_MESSAGE not in text


def test_retries_use_configured_max_retries() -> None:
    mock = MockOpenAI([status_response(500), response_json([message_item("回答")])])

    turn = make_client(mock, max_retries=1).create_turn(make_request())

    assert turn.output_text == "回答"
    assert len(mock.requests) == 2  # 1 回だけ再試行した


def test_provider_error_propagates_through_llm_agent(seeded: Session) -> None:
    """LLMAgent は LLMProviderError をそのまま上位へ伝える（フォールバックは Step 5-D 以降）。"""
    mock = MockOpenAI([status_response(429)])

    with pytest.raises(LLMProviderError):
        LLMAgent(make_client(mock)).respond(seeded, USER_MESSAGE)


# --- 依存関係の境界 -----------------------------------------------------------------------------


def test_openai_sdk_is_imported_only_by_the_adapter() -> None:
    importers = []
    for path in (BACKEND_DIR / "app").rglob("*.py"):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "openai" for a in node.names):
                importers.append(path.relative_to(BACKEND_DIR).as_posix())
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "openai":
                importers.append(path.relative_to(BACKEND_DIR).as_posix())

    assert sorted(set(importers)) == ["app/agents/llm/openai_client.py"]


def test_default_base_url_without_settings_override() -> None:
    """base_url を指定しない場合は OpenAI の既定の宛先を使う（送信は MockTransport が受け取り、実通信はしない）。"""
    sent: list[str] = []

    def guard(request: httpx2.Request) -> httpx2.Response:
        sent.append(str(request.url))
        return httpx2.Response(200, json=response_json([message_item("ok")]))

    client = OpenAIResponsesClient(
        api_key=FAKE_KEY, model=MODEL, http_client=httpx2.Client(transport=httpx2.MockTransport(guard))
    )
    client.create_turn(make_request())

    assert sent == ["https://api.openai.com/v1/responses"]
