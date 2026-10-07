"""FAQ 検索 Tool。Step 1 の search_faqs()（repository）をそのまま呼ぶ。"""

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.repositories.faqs import FaqMatch, search_faqs

NAME = "search_faqs"
DESCRIPTION = "社内ヘルプデスクの FAQ を、利用者の質問文でキーワード検索する。一致度の高い順に返す。"
DEFAULT_LIMIT = 3


class FaqSearchArgs(BaseModel):
    """Tool の引数。LLM Agent では JSON Schema（FaqSearchArgs.model_json_schema()）として渡す。"""

    query: str = Field(min_length=1, max_length=200, description="利用者の質問文")
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=10, description="最大件数")


def search_faq_tool(
    session: Session, query: str, limit: int = DEFAULT_LIMIT
) -> list[FaqMatch]:
    """FAQ を検索する。検索アルゴリズムは repository（app.repositories.faqs）にのみ存在する。"""
    return search_faqs(session, query, limit=limit)
