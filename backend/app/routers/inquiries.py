from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Inquiry
from app.repositories.inquiries import (
    create_inquiry,
    get_inquiry,
    list_inquiries,
    update_inquiry_status,
)
from app.schemas.inquiry import (
    InquiryCreate,
    InquiryListParams,
    InquiryResponse,
    InquiryStatusUpdate,
)

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
        raise _not_found()
    return inquiry


@router.post(
    "",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {
            "headers": {
                "Location": {
                    "description": "作成した問い合わせの相対パス（/inquiries/{id}）",
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
def create_inquiry_endpoint(
    payload: InquiryCreate, response: Response, db: DbSession
) -> Inquiry:
    """問い合わせを登録する。status は OPEN 固定。"""
    inquiry = create_inquiry(
        db,
        title=payload.title,
        description=payload.description,
        category=payload.category,
    )
    # 絶対 URL はリバースプロキシ配下でスキーム・ホストを誤りやすいため相対パスにする（RFC 9110 で許容）
    response.headers["Location"] = f"{router.prefix}/{inquiry.id}"
    return inquiry


@router.patch(
    "/{inquiry_id}/status",
    response_model=InquiryResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Inquiry not found"}},
)
def update_inquiry_status_endpoint(
    inquiry_id: InquiryId, payload: InquiryStatusUpdate, db: DbSession
) -> Inquiry:
    """status を変更する。同じ status の場合は何も更新せず、現在の内容を返す。"""
    inquiry = update_inquiry_status(db, inquiry_id, payload.status)
    if inquiry is None:
        raise _not_found()
    return inquiry


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")
