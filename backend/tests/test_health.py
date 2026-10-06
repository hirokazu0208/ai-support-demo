from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import app

client = TestClient(app)


@pytest.fixture
def override_db() -> Iterator[None]:
    """テスト後に get_db の差し替えを元に戻す。"""
    yield
    app.dependency_overrides.clear()


def use_engine(engine: Engine) -> None:
    session_factory = create_session_factory(engine)

    def _get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_ready_returns_ok_when_database_is_available(
    override_db: None, migrated_engine: Engine
) -> None:
    use_engine(migrated_engine)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_503_when_database_is_unavailable(
    override_db: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # 存在しないディレクトリ配下の SQLite ファイルは開けない
    unreachable = create_db_engine(f"sqlite:///{tmp_path / 'missing' / 'app.db'}")
    use_engine(unreachable)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "Database readiness check failed" in caplog.text
    unreachable.dispose()
