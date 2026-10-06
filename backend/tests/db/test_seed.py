import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.db.seed import MissingTableError, seed_inquiries
from app.db.seed_data import SEED_INQUIRIES
from app.db.session import create_session_factory
from app.models import Inquiry, InquiryStatus


def count_inquiries(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Inquiry)) or 0


def test_seed_inserts_demo1_inquiries(db_session: Session) -> None:
    assert seed_inquiries(db_session) == 8

    inquiries = db_session.scalars(select(Inquiry).order_by(Inquiry.id)).all()
    assert [inquiry.id for inquiry in inquiries] == list(range(1, 9))
    for inquiry, data in zip(inquiries, SEED_INQUIRIES, strict=True):
        assert inquiry.title == data["title"]
        assert inquiry.description == data["description"]
        assert inquiry.category is data["category"]
        assert inquiry.status is data["status"]
        assert inquiry.created_at == data["created_at"]
        assert inquiry.updated_at == data["created_at"]


def test_seed_is_idempotent(db_session: Session) -> None:
    assert seed_inquiries(db_session) == 8
    assert seed_inquiries(db_session) == 0

    assert count_inquiries(db_session) == 8


def test_seed_does_not_overwrite_existing_data(db_session: Session) -> None:
    seed_inquiries(db_session)
    first = db_session.get(Inquiry, 1)
    assert first is not None
    first.status = InquiryStatus.CLOSED
    db_session.commit()

    assert seed_inquiries(db_session) == 0

    db_session.expire_all()
    first = db_session.get(Inquiry, 1)
    assert first is not None
    assert first.status is InquiryStatus.CLOSED
    assert count_inquiries(db_session) == 8


def test_seed_requires_migration(engine: Engine) -> None:
    with create_session_factory(engine)() as session:
        with pytest.raises(MissingTableError, match="alembic upgrade head"):
            seed_inquiries(session)
