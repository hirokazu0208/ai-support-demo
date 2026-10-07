from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, portable_enum, utc_now
from app.models.inquiry import InquiryCategory


class Faq(Base):
    """よくある質問。AI Agent の FAQ 検索 Tool が参照する。"""

    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(String(200))
    answer: Mapped[str] = mapped_column(Text)
    # 問い合わせと同じ分類を使う（起票案のカテゴリ推定にも利用できる）
    category: Mapped[InquiryCategory] = mapped_column(
        portable_enum(InquiryCategory, "category")
    )
    # 検索用キーワード（空白区切り）。質問文にキーワードが含まれるかで一致を判定する
    keywords: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )
