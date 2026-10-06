from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.seed import seed_inquiries
from tests.conftest import FailWrites, MakeInquiry

RESPONSE_KEYS = {
    "id",
    "title",
    "description",
    "category",
    "status",
    "createdAt",
    "updatedAt",
}
VALID_BODY = {"title": "プリンタが動かない", "description": "3階の複合機", "category": "OTHER"}
LEAK_MARKERS = ("forced failure", "IntegrityError", "sqlite", "INSERT", "UPDATE", "Traceback")


def parse_utc(value: str) -> datetime:
    assert value.endswith("Z")
    return datetime.fromisoformat(value)


def inquiry_count(client: TestClient) -> int:
    return len(client.get("/inquiries").json())


def assert_validation_error(response, field: str, error_type: str) -> None:  # type: ignore[no-untyped-def]
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert {"loc": ["body", field], "type": error_type} in [
        {"loc": error["loc"], "type": error["type"]} for error in errors
    ], errors


# --- POST /inquiries ---------------------------------------------------------------


def test_create_returns_201_with_location_and_open_status(client: TestClient) -> None:
    response = client.post("/inquiries", json=VALID_BODY)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert response.headers["location"] == f"/inquiries/{body['id']}"
    assert body["status"] == "OPEN"
    assert body["title"] == VALID_BODY["title"]
    assert body["category"] == "OTHER"
    assert body["createdAt"] == body["updatedAt"]
    parse_utc(body["createdAt"])


def test_create_is_persisted_and_id_follows_seed(
    client: TestClient, db_session: Session
) -> None:
    seed_inquiries(db_session)

    created = client.post("/inquiries", json=VALID_BODY).json()

    assert created["id"] == 9
    fetched = client.get(f"/inquiries/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created
    assert client.get("/inquiries").json()[0]["id"] == 9  # 最新の作成日時で先頭に来る


def test_create_trims_title_and_description(client: TestClient) -> None:
    response = client.post(
        "/inquiries",
        json={**VALID_BODY, "title": "  件名　", "description": "\n 1行目\n2行目 \n"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "件名"
    assert body["description"] == "1行目\n2行目"  # 途中の改行は保持する
    assert client.get(f"/inquiries/{body['id']}").json()["title"] == "件名"


@pytest.mark.parametrize(
    ("field", "max_length"), [("title", 100), ("description", 2000)]
)
def test_create_length_boundaries(
    client: TestClient, field: str, max_length: int
) -> None:
    at_limit = client.post("/inquiries", json={**VALID_BODY, field: "あ" * max_length})
    padded = client.post(
        "/inquiries", json={**VALID_BODY, field: f"  {'あ' * max_length}  "}
    )
    over_limit = client.post(
        "/inquiries", json={**VALID_BODY, field: "あ" * (max_length + 1)}
    )

    assert at_limit.status_code == 201
    assert at_limit.json()[field] == "あ" * max_length
    assert padded.status_code == 201
    assert_validation_error(over_limit, field, "string_too_long")
    assert inquiry_count(client) == 2


@pytest.mark.parametrize("field", ["title", "description"])
@pytest.mark.parametrize("blank", ["", "   ", "　", "\n\t"])
def test_create_rejects_blank_text(client: TestClient, field: str, blank: str) -> None:
    response = client.post("/inquiries", json={**VALID_BODY, field: blank})

    assert_validation_error(response, field, "string_too_short")
    assert inquiry_count(client) == 0


@pytest.mark.parametrize("field", ["title", "description", "category"])
def test_create_requires_fields(client: TestClient, field: str) -> None:
    body = {key: value for key, value in VALID_BODY.items() if key != field}

    assert_validation_error(client.post("/inquiries", json=body), field, "missing")


def test_create_rejects_invalid_category(client: TestClient) -> None:
    response = client.post("/inquiries", json={**VALID_BODY, "category": "HARDWARE"})

    assert_validation_error(response, "category", "enum")


def test_create_rejects_non_string_title(client: TestClient) -> None:
    response = client.post("/inquiries", json={**VALID_BODY, "title": 123})

    assert_validation_error(response, "title", "string_type")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "CLOSED"),
        ("id", 100),
        ("createdAt", "2026-01-01T00:00:00Z"),
        ("updatedAt", "2026-01-01T00:00:00Z"),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("foo", "bar"),
    ],
)
def test_create_rejects_server_managed_and_unknown_fields(
    client: TestClient, field: str, value: object
) -> None:
    response = client.post("/inquiries", json={**VALID_BODY, field: value})

    assert_validation_error(response, field, "extra_forbidden")
    assert inquiry_count(client) == 0


def test_create_rejects_non_json_body(client: TestClient) -> None:
    response = client.post(
        "/inquiries", content="not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"


# --- PATCH /inquiries/{id}/status ---------------------------------------------------


def patch_status(client: TestClient, inquiry_id: int | str, status: str):  # type: ignore[no-untyped-def]
    return client.patch(f"/inquiries/{inquiry_id}/status", json={"status": status})


def test_patch_open_to_in_progress_to_closed(client: TestClient) -> None:
    created = client.post("/inquiries", json=VALID_BODY).json()

    in_progress = patch_status(client, created["id"], "IN_PROGRESS")
    assert in_progress.status_code == 200
    assert set(in_progress.json()) == RESPONSE_KEYS
    assert in_progress.json()["status"] == "IN_PROGRESS"

    closed = patch_status(client, created["id"], "CLOSED")
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"

    # GET で永続化を確認。createdAt は不変、updatedAt は変更のたびに進む
    fetched = client.get(f"/inquiries/{created['id']}").json()
    assert fetched == closed.json()
    assert fetched["createdAt"] == created["createdAt"]
    assert (
        parse_utc(created["updatedAt"])
        < parse_utc(in_progress.json()["updatedAt"])
        < parse_utc(closed.json()["updatedAt"])
    )


def test_patch_same_status_returns_200_without_touching_updated_at(
    client: TestClient,
) -> None:
    created = client.post("/inquiries", json=VALID_BODY).json()

    response = patch_status(client, created["id"], "OPEN")

    assert response.status_code == 200
    assert response.json() == created
    assert client.get(f"/inquiries/{created['id']}").json()["updatedAt"] == created["updatedAt"]


def test_patch_missing_inquiry_returns_404(client: TestClient) -> None:
    response = patch_status(client, 999, "CLOSED")

    assert response.status_code == 404
    assert response.json() == {"detail": "Inquiry not found"}


@pytest.mark.parametrize("inquiry_id", ["abc", "0", "-1", "9223372036854775808"])
def test_patch_invalid_id_returns_422(client: TestClient, inquiry_id: str) -> None:
    response = patch_status(client, inquiry_id, "CLOSED")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "inquiry_id"]


def test_patch_invalid_status_returns_422(
    client: TestClient, make_inquiry: MakeInquiry
) -> None:
    inquiry = make_inquiry()

    assert_validation_error(patch_status(client, inquiry.id, "PENDING"), "status", "enum")
    assert_validation_error(
        client.patch(f"/inquiries/{inquiry.id}/status", json={}), "status", "missing"
    )
    assert client.get(f"/inquiries/{inquiry.id}").json()["status"] == "OPEN"


def test_patch_rejects_unknown_fields(
    client: TestClient, make_inquiry: MakeInquiry
) -> None:
    inquiry = make_inquiry()

    response = client.patch(
        f"/inquiries/{inquiry.id}/status", json={"status": "CLOSED", "title": "x"}
    )

    assert_validation_error(response, "title", "extra_forbidden")
    assert client.get(f"/inquiries/{inquiry.id}").json()["status"] == "OPEN"


# --- commit 失敗時 -------------------------------------------------------------------


@pytest.fixture
def server_error_client(client: TestClient) -> TestClient:
    """未処理例外を 500 レスポンスとして受け取る（本番の挙動と同じ）。"""
    return TestClient(client.app, raise_server_exceptions=False)


def assert_internal_error_without_details(response, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    for marker in (*LEAK_MARKERS, str(tmp_path)):
        assert marker not in response.text


def test_create_commit_failure_rolls_back_without_leaking(
    server_error_client: TestClient, fail_writes: FailWrites, tmp_path: Path
) -> None:
    fail_writes("INSERT")

    response = server_error_client.post("/inquiries", json=VALID_BODY)

    assert_internal_error_without_details(response, tmp_path)
    after = server_error_client.get("/inquiries")
    assert after.status_code == 200
    assert after.json() == []


def test_patch_commit_failure_rolls_back_without_leaking(
    server_error_client: TestClient,
    make_inquiry: MakeInquiry,
    fail_writes: FailWrites,
    tmp_path: Path,
) -> None:
    inquiry = make_inquiry()
    before = server_error_client.get(f"/inquiries/{inquiry.id}").json()
    fail_writes("UPDATE")

    response = patch_status(server_error_client, inquiry.id, "CLOSED")

    assert_internal_error_without_details(response, tmp_path)
    assert server_error_client.get(f"/inquiries/{inquiry.id}").json() == before


# --- OpenAPI -------------------------------------------------------------------------


def test_openapi_describes_write_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    create = schema["paths"]["/inquiries"]["post"]
    assert {"201", "422"} <= set(create["responses"])
    assert "Location" in create["responses"]["201"]["headers"]
    assert create["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InquiryCreate"
    }

    patch = schema["paths"]["/inquiries/{inquiry_id}/status"]["patch"]
    assert {"200", "404", "422"} <= set(patch["responses"])
    assert patch["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InquiryStatusUpdate"
    }

    components = schema["components"]["schemas"]
    create_schema = components["InquiryCreate"]
    assert set(create_schema["properties"]) == {"title", "description", "category"}
    assert create_schema["additionalProperties"] is False
    assert create_schema["properties"]["title"]["maxLength"] == 100
    assert create_schema["properties"]["description"]["maxLength"] == 2000
    assert set(components["InquiryStatusUpdate"]["properties"]) == {"status"}
