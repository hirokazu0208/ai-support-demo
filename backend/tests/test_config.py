from pathlib import Path

import pytest

from app.config import BACKEND_DIR, Settings


def test_backend_dir_points_to_backend() -> None:
    assert (BACKEND_DIR / "alembic.ini").is_file()
    assert (BACKEND_DIR / "app" / "config.py").is_file()


def test_default_database_url_is_independent_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)

    assert settings.database_url == f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"


def test_env_file_is_resolved_from_backend_dir() -> None:
    assert Settings.model_config["env_file"] == BACKEND_DIR / ".env"


def test_database_url_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/override.db")

    assert Settings(_env_file=None).database_url == "sqlite:////tmp/override.db"
