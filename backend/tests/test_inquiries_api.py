from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.seed import seed_inquiries
from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import app
from app.models import InquiryStatus
from tests.conftest import MakeInquiry

RESPONSE_KEYS = {
    "id",
    "title",
    "description",
    "category",
    "status",
    "createdAt",
    "updatedAt",
}


def ids(response_json: list[dict]) -> list[int]:
    return [item["id"] for item in response_json]


# --- GET /inquiries ---------------------------------------------------------


def test_list_seed_data_in_created_at_desc_order(
    client: TestClient, db_session: Session
) -> None:
    seed_inquiries(db_session)

    response = client.get("/inquiries")

    assert response.status_code == 200
    assert ids(response.json()) == [7, 6, 5, 8, 3, 2, 1, 4]


def test_list_breaks_created_at_ties_by_id_desc(
    client: TestClient, make_inquiry: MakeInquiry
) -> None:
    same_time = datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
    first = make_inquiry(created_at=same_time)
    second = make_inquiry(created_at=same_time)

    assert ids(client.get("/inquiries").json()) == [second.id, first.id]


def test_list_returns_empty_array_when_no_data(client: TestClient) -> None:
    response = client.get("/inquiries")

    assert response.status_code == 200
    assert response.json() == []


def test_list_response_uses_camel_case_and_utc(
    client: TestClient, make_inquiry: MakeInquiry
) -> None:
    make_inquiry(created_at=datetime(2026, 9, 28, 0, 15, tzinfo=UTC))

    [item] = client.get("/inquiries").json()

    assert set(item) == RESPONSE_KEYS
    assert item["createdAt"] == "2026-09-28T00:15:00Z"
    assert item["updatedAt"] == "2026-09-28T00:15:00Z"


def test_q_searches_title_and_description(
    client: TestClient, db_session: Session
) -> None:
    seed_inquiries(db_session)

    assert ids(client.get("/inquiries", params={"q": "vpn"}).json()) == [5]
    # 検索対象はタイトルと本文のみ。id 1 は category が ACCOUNT だが本文に「アカウント」を含まない
    assert ids(client.get("/inquiries", params={"q": "アカウント"}).json()) == [8, 4]


def test_q_is_trimmed(client: TestClient, db_session: Session) -> None:
    seed_inquiries(db_session)

    assert ids(client.get("/inquiries", params={"q": "  VPN  "}).json()) == [5]


@pytest.mark.parametrize("q", ["", "   ", "　"])
def test_blank_q_returns_all(client: TestClient, db_session: Session, q: str) -> None:
    seed_inquiries(db_session)

    assert len(client.get("/inquiries", params={"q": q}).json()) == 8


def test_status_filters_inquiries(client: TestClient, db_session: Session) -> None:
    seed_inquiries(db_session)

    assert ids(client.get("/inquiries", params={"status": "CLOSED"}).json()) == [8, 4]


def test_q_and_status_combined(client: TestClient, db_session: Session) -> None:
    seed_inquiries(db_session)

    # 「できない」は 7（OPEN）・2（IN_PROGRESS）・1（OPEN）に一致する
    assert ids(client.get("/inquiries", params={"q": "できない"}).json()) == [7, 2, 1]

    response = client.get("/inquiries", params={"q": "できない", "status": "OPEN"})

    assert ids(response.json()) == [7, 1]


def test_search_without_match_returns_empty_array(
    client: TestClient, db_session: Session
) -> None:
    seed_inquiries(db_session)

    response = client.get("/inquiries", params={"q": "存在しない語"})

    assert response.status_code == 200
    assert response.json() == []


def test_invalid_status_returns_422(client: TestClient) -> None:
    response = client.get("/inquiries", params={"status": "PENDING"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "status"]


def test_undefined_query_parameter_returns_422(client: TestClient) -> None:
    response = client.get("/inquiries", params={"stauts": "OPEN"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_q_longer_than_200_returns_422(client: TestClient) -> None:
    assert client.get("/inquiries", params={"q": "あ" * 200}).status_code == 200
    assert client.get("/inquiries", params={"q": "あ" * 201}).status_code == 422


# --- GET /inquiries/{id} ----------------------------------------------------


def test_get_inquiry_returns_detail(client: TestClient, db_session: Session) -> None:
    seed_inquiries(db_session)

    response = client.get("/inquiries/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "title": "パスワードを忘れてログインできない",
        "description": "社内ポータルのパスワードを失念しました。リセット手順を教えてください。",
        "category": "ACCOUNT",
        "status": InquiryStatus.OPEN.value,
        "createdAt": "2026-09-28T00:15:00Z",
        "updatedAt": "2026-09-28T00:15:00Z",
    }


def test_get_missing_inquiry_returns_404(client: TestClient) -> None:
    response = client.get("/inquiries/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


@pytest.mark.parametrize(
    "inquiry_id",
    ["abc", "1.5", "0", "-1", "2147483648", "9223372036854775808", "1" * 40],
)
def test_invalid_inquiry_id_returns_422(client: TestClient, inquiry_id: str) -> None:
    response = client.get(f"/inquiries/{inquiry_id}")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "inquiry_id"]


def test_max_inquiry_id_is_accepted_and_returns_404(client: TestClient) -> None:
    assert client.get("/inquiries/2147483647").status_code == 404


# --- DB 障害時 ----------------------------------------------------------------


@pytest.fixture
def broken_db_client(tmp_path: Path) -> Iterator[TestClient]:
    """開けない SQLite に接続させ、未処理例外を 500 レスポンスとして受け取る TestClient。"""
    unreachable = create_db_engine(f"sqlite:///{tmp_path / 'missing' / 'app.db'}")
    session_factory = create_session_factory(unreachable)

    def _get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    unreachable.dispose()


@pytest.mark.parametrize("path", ["/inquiries", "/inquiries/1"])
def test_database_error_does_not_leak_details(
    broken_db_client: TestClient, tmp_path: Path, path: str
) -> None:
    response = broken_db_client.get(path)

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    for secret in ("sqlite", "OperationalError", "unable to open", str(tmp_path)):
        assert secret not in response.text


# --- OpenAPI ------------------------------------------------------------------


def test_openapi_describes_inquiry_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert {"/inquiries", "/inquiries/{inquiry_id}"} <= set(schema["paths"])
    assert set(schema["paths"]["/inquiries"]) == {"get"}
    assert set(schema["paths"]["/inquiries/{inquiry_id}"]) == {"get"}

    list_params = {p["name"] for p in schema["paths"]["/inquiries"]["get"]["parameters"]}
    assert list_params == {"q", "status"}

    detail = schema["paths"]["/inquiries/{inquiry_id}"]["get"]
    assert {"200", "404", "422"} <= set(detail["responses"])
    [id_param] = detail["parameters"]
    assert id_param["schema"]["minimum"] == 1
    assert id_param["schema"]["maximum"] == 2147483647

    components = schema["components"]["schemas"]
    assert set(components["InquiryResponse"]["properties"]) == RESPONSE_KEYS
    assert components["InquiryStatus"]["enum"] == ["OPEN", "IN_PROGRESS", "CLOSED"]
    assert components["InquiryCategory"]["enum"] == [
        "ACCOUNT",
        "NETWORK",
        "SOFTWARE",
        "OTHER",
    ]
