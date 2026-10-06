from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    """現在時刻を UTC のタイムゾーン付き datetime で返す。"""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """UTC のタイムゾーン付き datetime だけを受け付け、UTC で返す日時型。

    - 保存時: naive な datetime は拒否し、aware な値は UTC に変換する
    - 読み出し時: SQLite は タイムゾーンを保持できず naive な値を返すため UTC とみなし、
      PostgreSQL（timestamptz）の値は接続のタイムゾーン設定によらず UTC に変換する
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive な datetime は保存できません（UTC などのタイムゾーンを付けてください）")
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
