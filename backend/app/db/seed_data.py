"""Demo 1（frontend/src/lib/inquiries/mock-data.ts）の問い合わせ 8 件。

id は持たない（DB の自動採番に任せる）。空のテーブルにこの順で投入すると id は 1〜8 になる。
"""

from datetime import UTC, datetime
from typing import TypedDict

from app.models import InquiryCategory, InquiryStatus


class SeedInquiry(TypedDict):
    title: str
    description: str
    category: InquiryCategory
    status: InquiryStatus
    created_at: datetime


SEED_INQUIRIES: list[SeedInquiry] = [
    {
        "title": "パスワードを忘れてログインできない",
        "description": "社内ポータルのパスワードを失念しました。リセット手順を教えてください。",
        "category": InquiryCategory.ACCOUNT,
        "status": InquiryStatus.OPEN,
        "created_at": datetime(2026, 9, 28, 0, 15, tzinfo=UTC),
    },
    {
        "title": "会議室のWi-Fiに接続できない",
        "description": "3階第2会議室で社内Wi-Fiに接続できません。他のフロアでは問題なく接続できます。",
        "category": InquiryCategory.NETWORK,
        "status": InquiryStatus.IN_PROGRESS,
        "created_at": datetime(2026, 9, 29, 1, 40, tzinfo=UTC),
    },
    {
        "title": "Excelが起動直後に強制終了する",
        "description": "昨日のWindows Update以降、Excelを起動すると数秒で終了してしまいます。",
        "category": InquiryCategory.SOFTWARE,
        "status": InquiryStatus.OPEN,
        "created_at": datetime(2026, 9, 30, 2, 5, tzinfo=UTC),
    },
    {
        "title": "新入社員のアカウント発行依頼",
        "description": "10月入社予定の2名について、メールアカウントと社内システムのアカウント発行をお願いします。",
        "category": InquiryCategory.ACCOUNT,
        "status": InquiryStatus.CLOSED,
        "created_at": datetime(2026, 9, 24, 5, 30, tzinfo=UTC),
    },
    {
        "title": "VPN接続が頻繁に切断される",
        "description": "在宅勤務中、VPNが30分ほどで切断されます。再接続すると一時的に復旧します。",
        "category": InquiryCategory.NETWORK,
        "status": InquiryStatus.OPEN,
        "created_at": datetime(2026, 10, 1, 23, 50, tzinfo=UTC),
    },
    {
        "title": "画像編集ソフトのライセンス追加",
        "description": "デザインチームで1名増員のため、画像編集ソフトのライセンスを1つ追加してください。",
        "category": InquiryCategory.SOFTWARE,
        "status": InquiryStatus.IN_PROGRESS,
        "created_at": datetime(2026, 10, 2, 4, 20, tzinfo=UTC),
    },
    {
        "title": "複合機で両面印刷ができない",
        "description": "2階の複合機で両面印刷を指定しても片面で出力されます。ドライバ設定を確認してほしいです。",
        "category": InquiryCategory.OTHER,
        "status": InquiryStatus.OPEN,
        "created_at": datetime(2026, 10, 3, 6, 10, tzinfo=UTC),
    },
    {
        "title": "退職者アカウントの無効化",
        "description": "9月末で退職した社員のアカウントを無効化してください。対象者は別途メールで送付済みです。",
        "category": InquiryCategory.ACCOUNT,
        "status": InquiryStatus.CLOSED,
        "created_at": datetime(2026, 9, 30, 8, 45, tzinfo=UTC),
    },
]
