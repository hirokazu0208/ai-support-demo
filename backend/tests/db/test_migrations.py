from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

from app.config import BACKEND_DIR
from app.db.base import Base
import app.models  # noqa: F401  全モデルを Base.metadata に登録する


def test_upgrade_creates_inquiries_table(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)

    assert set(inspector.get_table_names()) == {"alembic_version", "inquiries"}
    columns = {column["name"]: column for column in inspector.get_columns("inquiries")}
    assert list(columns) == [
        "id",
        "title",
        "description",
        "category",
        "status",
        "created_at",
        "updated_at",
    ]
    assert all(
        not column["nullable"] for column in columns.values()
    ), "全カラム NOT NULL"
    assert inspector.get_pk_constraint("inquiries")["constrained_columns"] == ["id"]
    assert {index["name"] for index in inspector.get_indexes("inquiries")} == {
        "ix_inquiries_created_at",
        "ix_inquiries_status",
    }


def test_check_constraints_are_not_duplicated(migrated_engine: Engine) -> None:
    """Alembic 1.20 + SQLAlchemy 2.1 の autogenerate で発生した CHECK 制約の重複が無いこと。"""
    names = [
        constraint["name"]
        for constraint in inspect(migrated_engine).get_check_constraints("inquiries")
    ]

    assert sorted(names) == ["ck_inquiries_category", "ck_inquiries_status"]


def test_downgrade_removes_inquiries_table(
    alembic_config: Config, migrated_engine: Engine
) -> None:
    command.downgrade(alembic_config, "base")

    assert inspect(migrated_engine).get_table_names() == ["alembic_version"]


def test_upgrade_downgrade_upgrade_roundtrip(
    alembic_config: Config, migrated_engine: Engine
) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    assert "inquiries" in inspect(migrated_engine).get_table_names()


def test_models_match_migrations(migrated_engine: Engine) -> None:
    """モデル定義と migration の結果に差分が無いこと（alembic check と同等）。"""
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)

    assert diff == []


def test_alembic_resolves_app_from_any_directory(alembic_config: Config) -> None:
    """alembic -c backend/alembic.ini をどこから実行しても app を import できること。"""
    assert alembic_config.get_main_option("prepend_sys_path") == str(BACKEND_DIR)
