from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, portable_enum, utc_now


class InquiryCategory(StrEnum):
    ACCOUNT = "ACCOUNT"
    NETWORK = "NETWORK"
    SOFTWARE = "SOFTWARE"
    OTHER = "OTHER"


class InquiryStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class Inquiry(Base):
    __tablename__ = "inquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[InquiryCategory] = mapped_column(
        portable_enum(InquiryCategory, "category")
    )
    status: Mapped[InquiryStatus] = mapped_column(
        portable_enum(InquiryStatus, "status"),
        default=InquiryStatus.OPEN,
        server_default=InquiryStatus.OPEN.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )
