from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.models import InquiryCategory, InquiryStatus


class InquiryResponse(BaseModel):
    """問い合わせのレスポンス。Python 側は snake_case、JSON は camelCase（createdAt など）。"""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )

    id: int
    title: str
    description: str
    category: InquiryCategory
    status: InquiryStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


class InquiryListParams(BaseModel):
    """GET /inquiries のクエリパラメータ。未定義のパラメータは 422 にする。"""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(
        default=None,
        max_length=200,
        description="タイトル・問い合わせ内容の部分一致（大文字小文字を区別しない）。前後の空白は除く",
    )
    status: InquiryStatus | None = Field(default=None, description="ステータスで絞り込む")

    @field_validator("q")
    @classmethod
    def normalize_q(cls, value: str | None) -> str | None:
        """前後の空白を除き、空になれば「指定なし」とする（Demo 1 と同じ扱い）。"""
        if value is None:
            return None
        return value.strip() or None
