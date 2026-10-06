"""問い合わせのデータアクセス層。SQL の組み立てとトランザクション境界はこのモジュールで扱う。

- 読み取り関数は commit しない（Session のライフサイクルは get_db() が管理する）
- 書き込み関数は 1 関数 = 1 トランザクションとし、関数内で commit する。
  commit に失敗した場合は必ず rollback してから例外を再送出し、Session を再利用可能な状態に戻す
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.types import utc_now
from app.models import Inquiry, InquiryCategory, InquiryStatus


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


def create_inquiry(
    session: Session, *, title: str, description: str, category: InquiryCategory
) -> Inquiry:
    """問い合わせを登録する。status は OPEN 固定、created_at と updated_at は同じ UTC 時刻。"""
    now = utc_now()
    inquiry = Inquiry(
        title=title,
        description=description,
        category=category,
        status=InquiryStatus.OPEN,
        created_at=now,
        updated_at=now,
    )
    session.add(inquiry)
    _commit(session)
    return inquiry


def update_inquiry_status(
    session: Session, inquiry_id: int, status: InquiryStatus
) -> Inquiry | None:
    """status を変更する。該当なしの場合は None（API の 404 に相当）。

    同じ status の場合は何もしない（UPDATE も commit も行わず、updated_at も変えない）。
    status が変わった場合だけ updated_at を明示的に現在時刻にする（created_at は変えない）。
    """
    inquiry = session.get(Inquiry, inquiry_id)
    if inquiry is None:
        return None
    if inquiry.status == status:
        return inquiry

    inquiry.status = status
    inquiry.updated_at = utc_now()
    _commit(session)
    return inquiry


def _commit(session: Session) -> None:
    """commit に失敗したら rollback してから例外を再送出する。

    rollback しないと Session は PendingRollbackError を出す状態のまま残る。
    rollback により、追加途中のオブジェクトは Session から外れ、
    変更途中の属性は失効して次のアクセスで DB の値に戻る。
    """
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
