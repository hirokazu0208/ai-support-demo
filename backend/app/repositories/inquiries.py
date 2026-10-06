"""問い合わせのデータアクセス層。SQL の組み立てはこのモジュールで行う。

読み取りのみのため commit は行わない（Session のライフサイクルは get_db() が管理する）。
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Inquiry, InquiryStatus


def list_inquiries(
    session: Session, *, q: str | None = None, status: InquiryStatus | None = None
) -> list[Inquiry]:
    """問い合わせ一覧を作成日時の新しい順（同時刻は id の降順）で返す。

    q はタイトル・問い合わせ内容の部分一致（大文字小文字を区別しない）。
    % と _ はワイルドカードではなく文字として扱う。q と status は AND で組み合わせる。
    """
    stmt = select(Inquiry)
    if status is not None:
        stmt = stmt.where(Inquiry.status == status)
    if q:
        stmt = stmt.where(
            or_(
                Inquiry.title.icontains(q, autoescape=True),
                Inquiry.description.icontains(q, autoescape=True),
            )
        )
    stmt = stmt.order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
    return list(session.scalars(stmt))


def get_inquiry(session: Session, inquiry_id: int) -> Inquiry | None:
    """該当なしの場合は None（API の 404 に相当）。"""
    return session.get(Inquiry, inquiry_id)
