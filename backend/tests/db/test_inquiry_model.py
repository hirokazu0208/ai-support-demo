from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models import Inquiry, InquiryCategory, InquiryStatus


def make_inquiry(**overrides: object) -> Inquiry:
    values: dict[str, object] = {
        "title": "テスト",
        "description": "本文",
        "category": InquiryCategory.OTHER,
    }
    values.update(overrides)
    return Inquiry(**values)


def insert_raw(session: Session, **overrides: str) -> None:
    """ORM の検証を通さずに INSERT する（DB 側の制約を確認するため）。"""
    values = {
        "title": "テスト",
        "description": "本文",
        "category": "OTHER",
        "status": "OPEN",
        "created_at": "2026-10-06 00:00:00.000000",
        "updated_at": "2026-10-06 00:00:00.000000",
    }
    values.update(overrides)
    columns = ", ".join(values)
    params = ", ".join(f":{name}" for name in values)
    session.execute(text(f"INSERT INTO inquiries ({columns}) VALUES ({params})"), values)
    session.flush()


def test_defaults_are_applied(db_session: Session) -> None:
    before = datetime.now(UTC)
    inquiry = make_inquiry()
    db_session.add(inquiry)
    db_session.commit()

    db_session.expire_all()
    saved = db_session.get(Inquiry, inquiry.id)
    assert saved is not None
    assert saved.id == 1
    assert saved.status is InquiryStatus.OPEN
    assert saved.created_at.tzinfo is UTC
    assert saved.updated_at.tzinfo is UTC
    assert before <= saved.created_at <= saved.updated_at


def test_updated_at_changes_on_update(db_session: Session) -> None:
    inquiry = make_inquiry()
    db_session.add(inquiry)
    db_session.commit()
    created_at, updated_at = inquiry.created_at, inquiry.updated_at

    inquiry.status = InquiryStatus.CLOSED
    db_session.commit()

    db_session.expire_all()
    saved = db_session.get(Inquiry, inquiry.id)
    assert saved is not None
    assert saved.status is InquiryStatus.CLOSED
    assert saved.created_at == created_at
    assert saved.updated_at > updated_at


def test_aware_datetime_is_stored_as_utc(db_session: Session) -> None:
    jst = datetime(2026, 10, 6, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    inquiry = make_inquiry(created_at=jst, updated_at=jst)
    db_session.add(inquiry)
    db_session.commit()

    # DB に保存された値そのものが UTC の時刻であること（SQLite は文字列、PostgreSQL は timestamptz）
    if db_session.get_bind().dialect.name == "postgresql":
        stored_sql = (
            "SELECT to_char(created_at AT TIME ZONE 'UTC', "
            "'YYYY-MM-DD HH24:MI:SS.US') FROM inquiries"
        )
    else:
        stored_sql = "SELECT created_at FROM inquiries"
    assert db_session.scalar(text(stored_sql)) == "2026-10-06 00:00:00.000000"

    db_session.expire_all()
    saved = db_session.get(Inquiry, inquiry.id)
    assert saved is not None
    assert saved.created_at == datetime(2026, 10, 6, 0, 0, tzinfo=UTC)
    assert saved.created_at.tzinfo is UTC
    assert saved.created_at.utcoffset() == timedelta(0)


def test_naive_datetime_is_rejected(db_session: Session) -> None:
    db_session.add(make_inquiry(created_at=datetime(2026, 10, 6, 9, 0)))

    with pytest.raises(StatementError, match="naive"):
        db_session.commit()


def test_invalid_category_is_rejected_by_orm(db_session: Session) -> None:
    db_session.add(make_inquiry(category="HARDWARE"))

    with pytest.raises(StatementError, match="HARDWARE"):
        db_session.commit()


@pytest.mark.parametrize(
    ("column", "value"), [("category", "HARDWARE"), ("status", "PENDING")]
)
def test_invalid_enum_value_is_rejected_by_check_constraint(
    db_session: Session, column: str, value: str
) -> None:
    with pytest.raises(IntegrityError, match=f"ck_inquiries_{column}"):
        insert_raw(db_session, **{column: value})


def test_valid_raw_insert_is_accepted(db_session: Session) -> None:
    insert_raw(db_session)

    assert db_session.scalar(text("SELECT count(*) FROM inquiries")) == 1


@pytest.mark.parametrize("column", ["title", "description", "category"])
def test_required_columns_are_not_null(db_session: Session, column: str) -> None:
    # SQLite: "NOT NULL constraint failed" / PostgreSQL: "violates not-null constraint"
    with pytest.raises(IntegrityError, match="(?i)not[ -]null"):
        insert_raw(db_session, **{column: None})  # type: ignore[arg-type]


def test_status_server_default_is_open(db_session: Session) -> None:
    db_session.execute(
        text(
            "INSERT INTO inquiries (title, description, category, created_at, updated_at) "
            "VALUES ('t', 'd', 'OTHER', '2026-10-06 00:00:00.000000', '2026-10-06 00:00:00.000000')"
        )
    )

    assert db_session.scalar(text("SELECT status FROM inquiries")) == "OPEN"
