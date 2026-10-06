from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.session import create_db_engine, create_session_factory


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
