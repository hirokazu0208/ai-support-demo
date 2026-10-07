"""POST /agent/chat と Agent の依存関係（Demo 3 Step 5-D）のテスト。"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentReply, ToolCall
from app.agents.fallback import FallbackAgent
from app.agents.llm.agent import LLMAgent
from app.agents.llm.client import LLMProviderError
from app.agents.rule_based import DRAFT_GUIDE, RuleBasedAgent
from app.db.seed import seed_faqs, seed_inquiries
from app.main import app
from app.routers import agent as agent_router
from app.routers.agent import get_agent
from tests.agents.fakes import FakeLLMClient, function_call, text_turn, tool_turn

RESPONSE_KEYS = {"message", "action", "matchedFaqs", "toolCalls", "inquiryDraft"}


@pytest.fixture
def seeded_client(client: TestClient, db_session: Session) -> TestClient:
    seed_faqs(db_session)
    return client


@pytest.fixture
def override_agent() -> Iterator[None]:
    yield
    app.dependency_overrides.pop(get_agent, None)


def chat(client: TestClient, message: str):  # type: ignore[no-untyped-def]
    return client.post("/agent/chat", json={"message": message})


# --- A. 既定（rule）の互換性 --------------------------------------------------------------------


def test_default_agent_is_cached_rule_based_agent() -> None:
    get_agent.cache_clear()
    try:
        first = get_agent()
        assert type(first) is RuleBasedAgent
        assert get_agent() is first
    finally:
        get_agent.cache_clear()


def test_default_provider_response_is_compatible(seeded_client: TestClient, db_session: Session) -> None:
    body = chat(seeded_client, "VPNがすぐ切れます").json()

    expected = RuleBasedAgent().respond(db_session, "VPNがすぐ切れます")
    assert set(body) == RESPONSE_KEYS
    assert body["action"] == expected.action.value == "FAQ_ANSWER"
    assert body["message"] == expected.message
    assert [faq["id"] for faq in body["matchedFaqs"]] == [m.faq.id for m in expected.matched_faqs]
    assert body["toolCalls"] == [{"name": "search_faqs", "arguments": {"query": "VPNがすぐ切れます", "limit": 3}}]
    assert body["inquiryDraft"] is None


# --- B・C. Agent の差し替えと AgentReply → API 応答の変換 -----------------------------------------


def test_llm_agent_can_be_injected_and_reply_is_converted(
    seeded_client: TestClient, override_agent: None
) -> None:
    message = "プリンタで両面印刷できません。\n問い合わせとして登録して"
    llm = LLMAgent(
        FakeLLMClient(
            [
                tool_turn(function_call("search_faqs", {"query": "プリンタで両面印刷できません"}, "c1")),
                tool_turn(function_call("draft_inquiry", {"message": message}, "c2")),
                text_turn("起票案を作成しました。"),
            ]
        )
    )
    app.dependency_overrides[get_agent] = lambda: llm

    body = chat(seeded_client, message).json()

    assert set(body) == RESPONSE_KEYS
    assert body["action"] == "INQUIRY_DRAFTED"
    assert body["message"] == f"起票案を作成しました。\n\n{DRAFT_GUIDE}"
    assert body["matchedFaqs"][0]["id"] == 9
    assert [call["name"] for call in body["toolCalls"]] == ["search_faqs", "draft_inquiry"]
    assert body["toolCalls"][0]["arguments"] == {"query": "プリンタで両面印刷できません", "limit": 3}
    assert body["inquiryDraft"] == {
        "title": "プリンタで両面印刷できません",
        "description": "プリンタで両面印刷できません。",
        "category": "OTHER",
    }


def test_fake_agent_reply_is_converted(seeded_client: TestClient, override_agent: None) -> None:
    class FixedAgent:
        def respond(self, session: Session, message: str) -> AgentReply:
            return AgentReply(
                message="固定の応答",
                action=AgentAction.INQUIRY_SUGGESTED,
                tool_calls=[ToolCall(name="search_faqs", arguments={"query": message, "limit": 3})],
            )

    app.dependency_overrides[get_agent] = FixedAgent

    body = chat(seeded_client, "テスト").json()

    assert body == {
        "message": "固定の応答",
        "action": "INQUIRY_SUGGESTED",
        "matchedFaqs": [],
        "toolCalls": [{"name": "search_faqs", "arguments": {"query": "テスト", "limit": 3}}],
        "inquiryDraft": None,
    }


def test_fallback_agent_via_api_returns_rule_based_reply(
    seeded_client: TestClient, db_session: Session, override_agent: None
) -> None:
    failing_llm = LLMAgent(FakeLLMClient([LLMProviderError("server", status_code=500)]))
    app.dependency_overrides[get_agent] = lambda: FallbackAgent(failing_llm, RuleBasedAgent())

    response = chat(seeded_client, "VPNがすぐ切れます")

    assert response.status_code == 200
    expected = RuleBasedAgent().respond(db_session, "VPNがすぐ切れます")
    assert response.json()["message"] == expected.message
    assert response.json()["action"] == "FAQ_ANSWER"


# --- D. Agent の例外 → 既存のエラーポリシー（500・内部情報なし）---------------------------------------


@pytest.mark.parametrize(
    "error",
    [LLMProviderError("authentication", status_code=401, request_id="req_x"), RuntimeError("secret detail sk-test")],
)
def test_agent_errors_keep_existing_error_policy(
    client: TestClient, override_agent: None, error: Exception
) -> None:
    class BrokenAgent:
        def respond(self, session: Session, message: str) -> AgentReply:
            raise error

    app.dependency_overrides[get_agent] = BrokenAgent
    server_error_client = TestClient(client.app, raise_server_exceptions=False)

    response = server_error_client.post("/agent/chat", json={"message": "VPN"})

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    for marker in ("LLMProviderError", "authentication", "req_x", "secret detail", "sk-test"):
        assert marker not in response.text


def test_validation_policy_unchanged(client: TestClient) -> None:
    assert client.post("/agent/chat", json={"message": "   "}).status_code == 422
    assert client.post("/agent/chat", json={"message": "x", "history": []}).status_code == 422


# --- E. Agent を毎リクエスト作らない -----------------------------------------------------------------


def test_agent_is_built_once_across_requests(
    seeded_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[object] = []
    original = agent_router.build_agent

    def counting_build(settings):  # type: ignore[no-untyped-def]
        agent = original(settings)
        built.append(agent)
        return agent

    monkeypatch.setattr(agent_router, "build_agent", counting_build)
    get_agent.cache_clear()
    try:
        for _ in range(3):
            assert chat(seeded_client, "VPNがすぐ切れます").status_code == 200
    finally:
        get_agent.cache_clear()

    assert len(built) == 1


# --- Human-in-the-loop（API 経由の LLM でも DB に書かない）----------------------------------------------


def test_llm_agent_via_api_never_writes(
    seeded_client: TestClient, db_session: Session, migrated_engine: Engine, override_agent: None
) -> None:
    seed_inquiries(db_session)
    before = len(seeded_client.get("/inquiries").json())
    llm = LLMAgent(
        FakeLLMClient(
            [
                tool_turn(function_call("create_inquiry", {"title": "x"}, "x1")),
                tool_turn(function_call("draft_inquiry", {"message": "PCが起動しません"}, "d1")),
                text_turn("起票案を作成しました。"),
            ]
        )
    )
    app.dependency_overrides[get_agent] = lambda: llm
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):  # type: ignore[no-untyped-def]
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(migrated_engine, "before_cursor_execute", record)
    try:
        body = chat(seeded_client, "PCが起動しません。問い合わせとして登録して").json()
    finally:
        event.remove(migrated_engine, "before_cursor_execute", record)

    assert body["action"] == "INQUIRY_DRAFTED"
    assert not {"INSERT", "UPDATE", "DELETE"} & set(statements)
    assert len(seeded_client.get("/inquiries").json()) == before
