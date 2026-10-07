from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.models import InquiryCategory

FAQ_SEARCH_LIMIT_MAX = 20


class FaqResponse(BaseModel):
    """FAQ の検索結果。score は検索語との一致度（q 未指定の場合は 0）。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int
    question: str
    answer: str
    category: InquiryCategory
    score: int


class FaqSearchParams(BaseModel):
    """GET /faqs のクエリパラメータ。未定義のパラメータは 422 にする。"""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(
        default=None,
        max_length=200,
        description="質問文。FAQ のキーワード・質問・回答との一致でスコアを付ける。前後の空白は除く",
    )
    limit: int = Field(default=5, ge=1, le=FAQ_SEARCH_LIMIT_MAX, description="最大件数")

    @field_validator("q")
    @classmethod
    def normalize_q(cls, value: str | None) -> str | None:
        """前後の空白を除き、空になれば「指定なし」とする。"""
        if value is None:
            return None
        return value.strip() or None
