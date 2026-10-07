"""Demo 1 の問い合わせ 8 件と FAQ 10 件を投入する。

    python -m app.db.seed

テーブルごとに、空のときだけ投入する（何度実行しても重複しない）。問い合わせと FAQ は独立しており、
一方にデータがあっても他方の投入には影響しない。1 件でもデータがあるテーブルには何もしないため、
画面で変更した内容を上書きしない。
"""

import sys

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.db.faq_seed_data import SEED_FAQS
from app.db.seed_data import SEED_INQUIRIES
from app.db.session import SessionLocal
from app.db.types import utc_now
from app.models import Faq, Inquiry


class MissingTableError(RuntimeError):
    """migration が未適用で対象のテーブルが存在しない。"""


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


def seed_faqs(session: Session) -> int:
    """faqs テーブルが空なら FAQ を投入して件数を返す。データがあれば何もせず 0 を返す。"""
    if not inspect(session.connection()).has_table(Faq.__tablename__):
        raise MissingTableError(
            "faqs テーブルがありません。先に `alembic upgrade head` を実行してください。"
        )

    existing = session.scalar(select(func.count()).select_from(Faq))
    if existing:
        return 0

    now = utc_now()
    session.add_all(Faq(**data, created_at=now, updated_at=now) for data in SEED_FAQS)
    session.commit()
    return len(SEED_FAQS)


def main() -> int:
    with SessionLocal() as session:
        try:
            inserted = seed_inquiries(session)
            inserted_faqs = seed_faqs(session)
        except MissingTableError as error:
            print(error, file=sys.stderr)
            return 1

    if inserted:
        print(f"{inserted} 件の問い合わせを投入しました。")
    else:
        print("既にデータがあるため seed をスキップしました。")
    if inserted_faqs:
        print(f"{inserted_faqs} 件の FAQ を投入しました。")
    else:
        print("FAQ は既にデータがあるため seed をスキップしました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
