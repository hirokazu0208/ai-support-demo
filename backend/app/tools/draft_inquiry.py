"""問い合わせ起票案 Tool。利用者のメッセージから問い合わせの起票案（タイトル・カテゴリ・内容）を作る。

外部 LLM を使わない決定的なルールで作成する。起票案は DB に保存しない（登録は人が既存の登録画面で行う）。
制約は InquiryCreate（POST /inquiries）と同じものを InquiryDraft で検証する。
"""

import re
import unicodedata

from pydantic import BaseModel, Field, ValidationError

from app.models import InquiryCategory
from app.schemas.inquiry import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH, InquiryDraft

NAME = "draft_inquiry"
DESCRIPTION = (
    "利用者のメッセージから、ヘルプデスクへの問い合わせの起票案（タイトル・カテゴリ・内容）を作成する。"
    "登録はしない。"
)

# 「問い合わせとして登録して」などの登録依頼の言い回し（判定と、起票案からの除去に使う）
_REQUEST_PATTERNS = [
    r"(?:これを|この内容で|この件を)?問い合わせ(?:として|を)?(?:登録|起票|作成)(?:して(?:ください|ほしい|欲しい)?|したい(?:です)?|をお願い(?:します|いたします)?|お願いします|してもらえますか)?",
    r"(?:担当者|ヘルプデスク|サポート)に(?:問い合わせ(?:たい|して)|相談(?:したい|して)|連絡(?:したい|して))(?:です|ください)?",
    r"問い合わせたい(?:です)?",
    r"起票(?:して(?:ください|ほしい)?|したい(?:です)?|をお願い(?:します)?|お願いします)",
    r"チケット(?:を)?(?:作成|起票|登録)(?:して(?:ください)?|したい(?:です)?|をお願い(?:します)?)?",
]
_REQUEST_RE = re.compile("|".join(f"(?:{pattern})" for pattern in _REQUEST_PATTERNS))

# カテゴリ分類のキーワード（一致数が最も多いカテゴリ。同数は ACCOUNT → NETWORK → SOFTWARE の順。
# 該当なしは OTHER。InquiryCategory に HARDWARE はないため、PC・プリンター等の機器は OTHER）
CATEGORY_KEYWORDS: dict[InquiryCategory, tuple[str, ...]] = {
    InquiryCategory.ACCOUNT: (
        "パスワード", "ログイン", "アカウント", "多要素認証", "mfa", "二段階認証", "権限", "入社", "退職",
    ),
    InquiryCategory.NETWORK: (
        "vpn", "wi-fi", "wifi", "無線", "ネットワーク", "インターネット", "lan", "回線",
    ),
    InquiryCategory.SOFTWARE: (
        "excel", "word", "office", "outlook", "teams", "アプリ", "ソフト", "ライセンス", "インストール",
    ),
}


class DraftInquiryArgs(BaseModel):
    """Tool の引数。LLM Agent では JSON Schema として渡す。"""

    message: str = Field(min_length=1, max_length=1000, description="利用者のメッセージ")


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def has_registration_request(message: str) -> bool:
    """利用者が問い合わせの登録（起票）を明示的に依頼しているか。"""
    return _REQUEST_RE.search(unicodedata.normalize("NFKC", message)) is not None


def strip_registration_request(message: str) -> str:
    """登録依頼の言い回しを除いた、問題の内容だけの文章を返す（空になることがある）。"""
    text = _REQUEST_RE.sub("", unicodedata.normalize("NFKC", message))
    # 依頼部分を除いた跡に残る句読点を整える（行頭の句読点・行末の読点のみ。文末の「。」は残す）
    lines = [line.strip(" 　").lstrip("、,。.:").rstrip("、,").strip(" 　") for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text.strip()


def classify_category(text: str) -> InquiryCategory:
    normalized = _normalize(text)
    best, best_hits = InquiryCategory.OTHER, 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in normalized)
        if hits > best_hits:
            best, best_hits = category, hits
    return best


def _make_title(content: str) -> str:
    """最初の文（句点・改行まで）を、末尾の句読点を除いて最大 100 文字にする。"""
    first = re.split(r"[。．.!！?？\n]", content, maxsplit=1)[0].strip(" 　、,")
    chars = list(first or content)
    return "".join(chars[:TITLE_MAX_LENGTH]).strip()


def draft_inquiry_tool(message: str) -> InquiryDraft | None:
    """起票案を作成する。登録依頼を除くと内容が残らない場合は None（起票できない）。"""
    content = strip_registration_request(message)
    if not content:
        return None
    description = "".join(list(content)[:DESCRIPTION_MAX_LENGTH])
    try:
        # InquiryCreate と同じ制約で検証する（POST /inquiries でそのまま登録できる内容であること）
        return InquiryDraft.model_validate(
            {
                "title": _make_title(content),
                "description": description,
                "category": classify_category(content),
            }
        )
    except ValidationError:
        return None
