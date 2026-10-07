from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.faqs import search_faqs
from app.schemas.faq import FaqResponse, FaqSearchParams

router = APIRouter(prefix="/faqs", tags=["faqs"])


@router.get("", response_model=list[FaqResponse])
def read_faqs(
    params: Annotated[FaqSearchParams, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> list[FaqResponse]:
    """FAQ を検索する（スコアの高い順。q 未指定の場合は id 順）。"""
    return [
        FaqResponse(
            id=match.faq.id,
            question=match.faq.question,
            answer=match.faq.answer,
            category=match.faq.category,
            score=match.score,
        )
        for match in search_faqs(db, params.q, limit=params.limit)
    ]
