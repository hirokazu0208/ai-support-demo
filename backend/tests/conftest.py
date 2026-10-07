import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, make_url, text
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import app
from app.models import Inquiry, InquiryCategory, InquiryStatus


# 指定するとテストをその DB で実行する（例: Docker Compose の test プロファイルで PostgreSQL）。
# 未指定ならテストごとの一時 SQLite ファイルを使う。テストはスキーマを作り直すため、
# 開発用・本番用の DB を指定しないこと（DB 名に "test" を含まない URL は拒否する）。
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip() or None


def pytest_configure(config: pytest.Config) -> None:
    if TEST_DATABASE_URL is None:
        return
    database = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database.lower():
        raise pytest.UsageError(
            "TEST_DATABASE_URL の DB 名に 'test' が含まれていません。"
            "テストはスキーマを作り直すため、テスト専用の DB を指定してください。"
        )


def pytest_report_header(config: pytest.Config) -> str:
    if TEST_DATABASE_URL is None:
        return "test database: SQLite（テストごとの一時ファイル）"
    shown = make_url(TEST_DATABASE_URL).render_as_string(hide_password=True)
    return f"test database: {shown}（TEST_DATABASE_URL）"


def make_alembic_config(db_url: str) -> Config:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """TEST_DATABASE_URL、なければテストごとの一時 SQLite ファイル。backend/data/app.db には触れない。"""
    return TEST_DATABASE_URL or f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def alembic_config(db_url: str) -> Config:
    return make_alembic_config(db_url)


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    """migration を適用していない Engine。

    PostgreSQL ではテストの開始前に public スキーマを作り直し、テーブル・シーケンス・
    alembic_version を空にする（SERIAL の id も 1 から始まる）。終了時ではなく開始時に行うため、
    失敗したテストの残りがあっても次のテストに影響しない。
    """
    engine = create_db_engine(db_url)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
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

    モックではなく本物の DB エラー（IntegrityError: forced failure）で commit の失敗を
    再現するため。テストごとの DB（一時 SQLite / 作り直した PostgreSQL スキーマ）にのみ作成する。
    """

    def _install(operation: str) -> None:
        assert operation in {"INSERT", "UPDATE"}
        name = f"fail_{operation.lower()}"
        with migrated_engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                # SQLite の RAISE(ABORT) と同じく IntegrityError になるよう、整合性違反の SQLSTATE を指定する
                connection.execute(
                    text(
                        f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                        "BEGIN RAISE EXCEPTION 'forced failure' "
                        "USING ERRCODE = 'integrity_constraint_violation'; END $$"
                    )
                )
                connection.execute(
                    text(
                        f"CREATE TRIGGER {name} BEFORE {operation} ON inquiries "
                        f"FOR EACH ROW EXECUTE FUNCTION {name}()"
                    )
                )
            else:
                connection.execute(
                    text(
                        f"CREATE TRIGGER {name} BEFORE {operation} "
                        "ON inquiries BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
                    )
                )

    return _install
