"""SQLite 固有の設定。SQLite 以外の DB ではこのモジュールは使われない。"""

from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event


def create_sqlite_engine(url: str) -> Engine:
    # FastAPI は def のエンドポイントをスレッドプールで実行するため、
    # 接続を作成したスレッド以外からの利用を許可する
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def _enable_foreign_keys(dbapi_connection: SQLiteConnection, _record: Any) -> None:
    """SQLite は既定で外部キー制約を検証しないため、接続ごとに有効にする。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
