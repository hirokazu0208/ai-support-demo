from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import app
from app.models import Inquiry, InquiryCategory, InquiryStatus


def make_alembic_config(db_url: str) -> Config:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """テストごとの一時 SQLite ファイル。backend/data/app.db には触れない。"""
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def alembic_config(db_url: str) -> Config:
    return make_alembic_config(db_url)


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    """migration を適用していない Engine。"""
    engine = create_db_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def migrated_engine(alembic_config: Config, engine: Engine) -> Engine:
    """create_all() ではなく、本番と同じ Alembic migration でスキーマを作成する。"""
    command.upgrade(alembic_config, "head")
    return engine


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    with create_session_factory(migrated_engine)() as session:
        yield session


MakeInquiry = Callable[..., Inquiry]


@pytest.fixture
def make_inquiry(db_session: Session) -> MakeInquiry:
    """テスト専用の問い合わせを 1 件作成して commit するファクトリー。"""

    def _make(
        *,
        title: str = "テスト問い合わせ",
        description: str = "テスト本文",
        category: InquiryCategory = InquiryCategory.OTHER,
        status: InquiryStatus = InquiryStatus.OPEN,
        created_at: datetime = datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
    ) -> Inquiry:
        inquiry = Inquiry(
            title=title,
            description=description,
            category=category,
            status=status,
            created_at=created_at,
            updated_at=created_at,
        )
        db_session.add(inquiry)
        db_session.commit()
        return inquiry

    return _make


@pytest.fixture
def client(migrated_engine: Engine) -> Iterator[TestClient]:
    """get_db を migration 済みの一時 DB に差し替えた TestClient。"""
    session_factory = create_session_factory(migrated_engine)

    def _get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


FailWrites = Callable[[str], None]


@pytest.fixture
def fail_writes(migrated_engine: Engine) -> FailWrites:
    """inquiries への INSERT / UPDATE を DB 側で失敗させるトリガーを追加する。

    モックではなく本物の DB エラー（sqlite3.IntegrityError: forced failure）で
    commit の失敗を再現するため。テストごとの一時 DB にのみ作成する。
    """

    def _install(operation: str) -> None:
        assert operation in {"INSERT", "UPDATE"}
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE TRIGGER fail_{operation.lower()} BEFORE {operation} "
                    "ON inquiries BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
                )
            )

    return _install
