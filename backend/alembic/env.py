from logging.config import fileConfig

from sqlalchemy import create_engine, make_url, pool

from alembic import context
from app.config import settings
from app.db.base import Base
import app.models  # noqa: F401  全モデルを Base.metadata に登録する

config = context.config

if config.config_file_name is not None:
    # アプリやテストで作成済みのロガーを無効化しない
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    """テストなどで sqlalchemy.url が指定されていればそれを、なければアプリの設定を使う。"""
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def run_migrations_offline() -> None:
    """接続せずに SQL を出力する（alembic upgrade --sql）。"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=is_sqlite(url),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite は ALTER TABLE の機能が限られるため、テーブル再作成方式（batch）で変更する
            render_as_batch=is_sqlite(url),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
