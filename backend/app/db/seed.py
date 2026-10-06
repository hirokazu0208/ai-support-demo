"""Demo 1 の問い合わせ 8 件を投入する。

    python -m app.db.seed

inquiries テーブルが空のときだけ投入する（何度実行しても重複しない）。
1 件でもデータがあれば何もしないため、画面で変更した内容を上書きしない。
"""

import sys

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.db.seed_data import SEED_INQUIRIES
from app.db.session import SessionLocal
from app.models import Inquiry


class MissingTableError(RuntimeError):
    """migration が未適用で inquiries テーブルが存在しない。"""


def seed_inquiries(session: Session) -> int:
    """テーブルが空なら seed データを投入して件数を返す。データがあれば何もせず 0 を返す。"""
    if not inspect(session.connection()).has_table(Inquiry.__tablename__):
        raise MissingTableError(
            "inquiries テーブルがありません。先に `alembic upgrade head` を実行してください。"
        )

    existing = session.scalar(select(func.count()).select_from(Inquiry))
    if existing:
        return 0

    # id は指定しない（DB の自動採番）。updated_at は created_at と同じ値にする
    session.add_all(
        Inquiry(**data, updated_at=data["created_at"]) for data in SEED_INQUIRIES
    )
    session.commit()
    return len(SEED_INQUIRIES)


def main() -> int:
    with SessionLocal() as session:
        try:
            inserted = seed_inquiries(session)
        except MissingTableError as error:
            print(error, file=sys.stderr)
            return 1

    if inserted:
        print(f"{inserted} 件の問い合わせを投入しました。")
    else:
        print("既にデータがあるため seed をスキップしました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
