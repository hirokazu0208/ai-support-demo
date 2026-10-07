import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.seed import seed_faqs

RESPONSE_KEYS = {"id", "question", "answer", "category", "score"}


def test_search_returns_ranked_faqs(client: TestClient, db_session: Session) -> None:
    seed_faqs(db_session)

    response = client.get("/faqs", params={"q": "VPNがすぐ切れる"})

    assert response.status_code == 200
    body = response.json()
    assert set(body[0]) == RESPONSE_KEYS
    assert body[0]["question"] == "VPN が頻繁に切断されます"
    assert body[0]["category"] == "NETWORK"
    assert body[0]["score"] > 0
    assert [item["score"] for item in body] == sorted(
        (item["score"] for item in body), reverse=True
    )


def test_default_limit_is_five(client: TestClient, db_session: Session) -> None:
    seed_faqs(db_session)

    response = client.get("/faqs")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [1, 2, 3, 4, 5]
    assert all(item["score"] == 0 for item in response.json())


def test_limit_and_trimmed_query(client: TestClient, db_session: Session) -> None:
    seed_faqs(db_session)

    response = client.get("/faqs", params={"q": "  アカウント  ", "limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_no_match_returns_empty_array(client: TestClient, db_session: Session) -> None:
    seed_faqs(db_session)

    response = client.get("/faqs", params={"q": "宇宙旅行"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 21}, {"limit": "abc"}, {"q": "あ" * 201}, {"foo": "bar"}],
)
def test_invalid_params_return_422(client: TestClient, params: dict) -> None:
    assert client.get("/faqs", params=params).status_code == 422


def test_openapi_describes_faq_search(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/faqs"]["get"]
    assert {p["name"] for p in operation["parameters"]} == {"q", "limit"}
    assert set(schema["components"]["schemas"]["FaqResponse"]["properties"]) == RESPONSE_KEYS
