from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.sqlite import create_sqlite_engine


def create_db_engine(url: str) -> Engine:
    """DATABASE_URL から Engine を作る。SQLite 固有の設定は app.db.sqlite に閉じ込める。"""
    if make_url(url).get_backend_name() == "sqlite":
        return create_sqlite_engine(url)
    # 使われていない接続が切断される環境（Azure など）に備え、利用前に接続を確認する
    return create_engine(url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # commit 後も属性を読めるようにし（API 応答の生成時に再 SELECT しない）、
    # flush のタイミングは明示的に制御する
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


engine = create_db_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def get_db() -> Iterator[Session]:
    """1 リクエストにつき 1 つの Session を提供する FastAPI 依存関数。

    commit は行わない。書き込み処理側でトランザクション境界を明示する。
    """
    with SessionLocal() as session:
        yield session
