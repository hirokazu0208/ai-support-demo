from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import create_session_factory
from app.models import Inquiry, InquiryCategory, InquiryStatus
from app.repositories.inquiries import create_inquiry, update_inquiry_status
from tests.conftest import FailWrites, MakeInquiry


def reload(engine: Engine, inquiry_id: int) -> Inquiry | None:
    """別の Session で読み直し、DB に永続化された値を確認する。"""
    with create_session_factory(engine)() as session:
        return session.get(Inquiry, inquiry_id)


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Inquiry)) or 0


@contextmanager
def capture_sql(engine: Engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def _record(_conn, _cursor, statement, *_args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


# --- create_inquiry ---------------------------------------------------------------


def test_create_inquiry_persists_with_open_status_and_same_timestamps(
    db_session: Session, migrated_engine: Engine
) -> None:
    before = datetime.now(UTC)

    created = create_inquiry(
        db_session, title="件名", description="本文", category=InquiryCategory.NETWORK
    )

    after = datetime.now(UTC)
    assert created.id == 1
    assert created.status is InquiryStatus.OPEN
    assert created.created_at == created.updated_at
    assert created.created_at.tzinfo is UTC
    assert before <= created.created_at <= after

    saved = reload(migrated_engine, created.id)
    assert saved is not None
    assert (saved.title, saved.description, saved.category, saved.status) == (
        "件名",
        "本文",
        InquiryCategory.NETWORK,
        InquiryStatus.OPEN,
    )
    assert saved.created_at == saved.updated_at == created.created_at


def test_create_inquiry_rolls_back_when_commit_fails(
    db_session: Session, fail_writes: FailWrites
) -> None:
    fail_writes("INSERT")

    with pytest.raises(IntegrityError, match="forced failure"):
        create_inquiry(
            db_session, title="件名", description="本文", category=InquiryCategory.OTHER
        )

    # rollback 済みのため、同じ Session をそのまま使える（PendingRollbackError にならない）
    assert db_session.is_active
    assert count(db_session) == 0
    assert list(db_session.new) == []


# --- update_inquiry_status --------------------------------------------------------


def test_update_status_changes_status_and_updated_at_only(
    db_session: Session, migrated_engine: Engine, make_inquiry: MakeInquiry
) -> None:
    inquiry = make_inquiry(status=InquiryStatus.OPEN)
    created_at, updated_at = inquiry.created_at, inquiry.updated_at

    updated = update_inquiry_status(db_session, inquiry.id, InquiryStatus.IN_PROGRESS)

    assert updated is not None
    assert updated.status is InquiryStatus.IN_PROGRESS
    assert updated.created_at == created_at
    assert updated.updated_at > updated_at

    saved = reload(migrated_engine, inquiry.id)
    assert saved is not None
    assert saved.status is InquiryStatus.IN_PROGRESS
    assert saved.created_at == created_at
    assert saved.updated_at == updated.updated_at


def test_update_status_with_same_value_does_not_write(
    db_session: Session, migrated_engine: Engine, make_inquiry: MakeInquiry
) -> None:
    inquiry = make_inquiry(status=InquiryStatus.CLOSED)
    updated_at = inquiry.updated_at

    with capture_sql(migrated_engine) as statements:
        result = update_inquiry_status(db_session, inquiry.id, InquiryStatus.CLOSED)

    assert result is not None
    assert result.status is InquiryStatus.CLOSED
    assert result.updated_at == updated_at
    assert not any(s.lstrip().upper().startswith("UPDATE") for s in statements)

    saved = reload(migrated_engine, inquiry.id)
    assert saved is not None
    assert saved.updated_at == updated_at


def test_update_status_returns_none_when_missing(db_session: Session) -> None:
    assert update_inquiry_status(db_session, 999, InquiryStatus.CLOSED) is None


def test_update_status_rolls_back_when_commit_fails(
    db_session: Session,
    migrated_engine: Engine,
    make_inquiry: MakeInquiry,
    fail_writes: FailWrites,
) -> None:
    inquiry = make_inquiry(status=InquiryStatus.OPEN)
    updated_at = inquiry.updated_at
    fail_writes("UPDATE")

    with pytest.raises(IntegrityError, match="forced failure"):
        update_inquiry_status(db_session, inquiry.id, InquiryStatus.CLOSED)

    # rollback により変更途中の属性は失効し、次のアクセスで DB の値に戻る
    assert db_session.is_active
    assert inquiry.status is InquiryStatus.OPEN
    assert inquiry.updated_at == updated_at

    saved = reload(migrated_engine, inquiry.id)
    assert saved is not None
    assert saved.status is InquiryStatus.OPEN
    assert saved.updated_at == updated_at

    # 失敗後も同じ Session で読み取りを続けられる
    assert count(db_session) == 1
