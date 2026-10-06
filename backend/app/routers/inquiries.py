from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Inquiry
from app.repositories.inquiries import get_inquiry, list_inquiries
from app.schemas.inquiry import InquiryListParams, InquiryResponse

router = APIRouter(prefix="/inquiries", tags=["inquiries"])

DbSession = Annotated[Session, Depends(get_db)]

# PostgreSQL の SERIAL（int4）の最大値。範囲外の id は DB に問い合わせず 422 にする
# （SQLite では 2**63 以上の整数で OverflowError になり、500 になるのを防ぐ）
INQUIRY_ID_MAX = 2_147_483_647

InquiryId = Annotated[
    int, Path(ge=1, le=INQUIRY_ID_MAX, description="問い合わせ ID（正の整数）")
]


@router.get("", response_model=list[InquiryResponse])
def read_inquiries(
    params: Annotated[InquiryListParams, Query()], db: DbSession
) -> list[Inquiry]:
    """問い合わせ一覧を作成日時の新しい順（同時刻は id の降順）で返す。"""
    return list_inquiries(db, q=params.q, status=params.status)


@router.get(
    "/{inquiry_id}",
    response_model=InquiryResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Inquiry not found"}},
)
def read_inquiry(inquiry_id: InquiryId, db: DbSession) -> Inquiry:
    inquiry = get_inquiry(db, inquiry_id)
    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found"
        )
    return inquiry
