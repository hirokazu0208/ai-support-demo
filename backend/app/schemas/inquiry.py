from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
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


# 前後の空白を除いてから長さを検証する。長さは Python の len()（コードポイント単位）で数え、
# Demo 1 の validation.ts（countChars）と同じ上限にそろえる
InquiryTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
InquiryDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class InquiryCreate(BaseModel):
    """POST /inquiries のリクエスト。

    id・status・createdAt・updatedAt はサーバー側で決めるため受け付けない（未定義の項目は 422）。
    入力も camelCase のみ受け付ける（populate_by_name は付けない）。
    """

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel)

    title: InquiryTitle
    description: InquiryDescription
    category: InquiryCategory


class InquiryStatusUpdate(BaseModel):
    """PATCH /inquiries/{id}/status のリクエスト。status 以外は受け付けない。"""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel)

    status: InquiryStatus
