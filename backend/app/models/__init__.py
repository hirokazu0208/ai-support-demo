"""全モデルを import し、Base.metadata に登録する（Alembic の autogenerate が参照する）。"""

from app.models.inquiry import Inquiry, InquiryCategory, InquiryStatus

__all__ = ["Inquiry", "InquiryCategory", "InquiryStatus"]
