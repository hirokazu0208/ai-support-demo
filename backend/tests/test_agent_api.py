from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentReply
from app.db.seed import seed_faqs, seed_inquiries
from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import app
from app.routers.agent import get_agent

RESPONSE_KEYS = {"message", "action", "matchedFaqs", "toolCalls"}
FAQ_KEYS = {"id", "question", "answer", "category", "score"}


@pytest.fixture
def seeded_client(client: TestClient, db_session: Session) -> TestClient:
    seed_faqs(db_session)
    return client


def chat(client: TestClient, body: object):  # type: ignore[no-untyped-def]
    return client.post("/agent/chat", json=body)


def test_faq_answer_for_vpn(seeded_client: TestClient) -> None:
    response = chat(seeded_client, {"message": "VPNがすぐ切れます"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["action"] == "FAQ_ANSWER"
    assert set(body["matchedFaqs"][0]) == FAQ_KEYS
    assert body["matchedFaqs"][0]["id"] == 6
    assert body["matchedFaqs"][0]["category"] == "NETWORK"
    # キーワード「VPN」のみ一致（「切れます」は「切れる」を含まない）
    assert body["matchedFaqs"][0]["score"] == 3
    assert "VPN クライアントを最新版に更新" in body["message"]
    assert body["toolCalls"] == [
        {"name": "search_faqs", "arguments": {"query": "VPNがすぐ切れます", "limit": 3}}
    ]


def test_faq_answer_for_password(seeded_client: TestClient) -> None:
    body = chat(seeded_client, {"message": "パスワードを忘れました"}).json()

    assert body["action"] == "FAQ_ANSWER"
    assert body["matchedFaqs"][0]["question"] == "パスワードを忘れてログインできません"


def test_multiple_faqs(seeded_client: TestClient) -> None:
    body = chat(seeded_client, {"message": "パスワードを忘れたうえに VPN もつながりません"}).json()

    assert body["action"] == "FAQ_ANSWER"
    assert {faq["id"] for faq in body["matchedFaqs"][:2]} == {1, 6}
    assert len(body["matchedFaqs"]) <= 3


def test_no_faq_suggests_inquiry(seeded_client: TestClient) -> None:
    body = chat(seeded_client, {"message": "宇宙旅行に行きたいです"}).json()

    assert body["action"] == "INQUIRY_SUGGESTED"
    assert body["matchedFaqs"] == []
    assert body["message"].startswith("FAQ では解決できませんでした")


def test_message_is_trimmed(seeded_client: TestClient) -> None:
    body = chat(seeded_client, {"message": "  VPNがすぐ切れます\n"}).json()

    assert body["toolCalls"][0]["arguments"]["query"] == "VPNがすぐ切れます"


def test_max_length_message_is_accepted(seeded_client: TestClient) -> None:
    assert chat(seeded_client, {"message": "あ" * 1000}).status_code == 200


@pytest.mark.parametrize(
    ("body", "error_type"),
    [
        ({}, "missing"),
        ({"message": ""}, "string_too_short"),
        ({"message": "   　\n"}, "string_too_short"),
        ({"message": "あ" * 1001}, "string_too_long"),
        ({"message": 123}, "string_type"),
        ({"message": "VPN", "history": []}, "extra_forbidden"),
    ],
)
def test_invalid_request_returns_422(
    seeded_client: TestClient, body: dict, error_type: str
) -> None:
    response = chat(seeded_client, body)

    assert response.status_code == 422
    assert error_type in {error["type"] for error in response.json()["detail"]}


def test_non_json_body_returns_422(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        "/agent/chat", content="VPN", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


def test_agent_can_be_replaced_via_dependency(seeded_client: TestClient) -> None:
    """get_agent() を差し替えると別の Agent 実装が使われる（LLM Agent への交換点）。"""

    class FixedAgent:
        def respond(self, session: Session, message: str) -> AgentReply:
            return AgentReply(message=f"echo: {message}", action=AgentAction.INQUIRY_SUGGESTED)

    app.dependency_overrides[get_agent] = FixedAgent
    try:
        body = chat(seeded_client, {"message": "VPN"}).json()
    finally:
        del app.dependency_overrides[get_agent]

    assert body == {
        "message": "echo: VPN",
        "action": "INQUIRY_SUGGESTED",
        "matchedFaqs": [],
        "toolCalls": [],
    }


@pytest.fixture
def broken_db_client(tmp_path: Path) -> Iterator[TestClient]:
    unreachable = create_db_engine(f"sqlite:///{tmp_path / 'missing' / 'app.db'}")
    session_factory = create_session_factory(unreachable)

    def _get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    unreachable.dispose()


def test_database_error_does_not_leak_details(
    broken_db_client: TestClient, tmp_path: Path
) -> None:
    response = chat(broken_db_client, {"message": "VPNがすぐ切れます"})

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert str(tmp_path) not in response.text


def test_existing_apis_still_work(seeded_client: TestClient, db_session: Session) -> None:
    seed_inquiries(db_session)

    assert chat(seeded_client, {"message": "VPNがすぐ切れます"}).status_code == 200
    assert seeded_client.get("/faqs", params={"q": "VPN"}).json()[0]["id"] == 6
    inquiries = seeded_client.get("/inquiries").json()
    assert [item["id"] for item in inquiries] == [7, 6, 5, 8, 3, 2, 1, 4]


def test_openapi_describes_agent_chat(seeded_client: TestClient) -> None:
    schema = seeded_client.get("/openapi.json").json()

    operation = schema["paths"]["/agent/chat"]["post"]
    assert {"200", "422"} <= set(operation["responses"])
    components = schema["components"]["schemas"]
    request = components["AgentChatRequest"]
    assert set(request["properties"]) == {"message"}
    assert request["additionalProperties"] is False
    assert request["properties"]["message"]["maxLength"] == 1000
    assert set(components["AgentChatResponse"]["properties"]) == RESPONSE_KEYS
    assert components["AgentAction"]["enum"] == ["FAQ_ANSWER", "INQUIRY_SUGGESTED"]
