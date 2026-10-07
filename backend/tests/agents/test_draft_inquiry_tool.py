import pytest

from app.models import InquiryCategory
from app.schemas.inquiry import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH, InquiryCreate, InquiryDraft
from app.tools.draft_inquiry import (
    DraftInquiryArgs,
    classify_category,
    draft_inquiry_tool,
    has_registration_request,
    strip_registration_request,
)


def test_printer_request_from_demo_scenario() -> None:
    draft = draft_inquiry_tool("プリンタで両面印刷できません。\n問い合わせとして登録して")

    assert draft is not None
    assert draft.title == "プリンタで両面印刷できません"
    assert draft.description == "プリンタで両面印刷できません。"
    # InquiryCategory に HARDWARE はなく、既存データ（複合機の問い合わせ・FAQ）と同じ OTHER
    assert draft.category is InquiryCategory.OTHER


def test_title_is_first_sentence_without_trailing_punctuation() -> None:
    draft = draft_inquiry_tool("Excelが起動しません。昨日のアップデート以降です。")

    assert draft is not None
    assert draft.title == "Excelが起動しません"
    assert draft.description == "Excelが起動しません。昨日のアップデート以降です。"


def test_description_keeps_problem_and_drops_request() -> None:
    draft = draft_inquiry_tool("VPNが30分で切れます。\n在宅勤務中です。\n担当者に問い合わせたいです")

    assert draft is not None
    assert draft.description == "VPNが30分で切れます。\n在宅勤務中です。"


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("パスワードを忘れてログインできません", InquiryCategory.ACCOUNT),
        ("VPNがすぐ切れます", InquiryCategory.NETWORK),
        ("会議室のＷｉ－Ｆｉにつながらない", InquiryCategory.NETWORK),
        ("Excelが起動直後に終了します", InquiryCategory.SOFTWARE),
        ("ソフトのライセンスを追加したい", InquiryCategory.SOFTWARE),
        ("プリンタで両面印刷できません", InquiryCategory.OTHER),
        ("PCのモニターが映らない", InquiryCategory.OTHER),
        ("宇宙旅行に行きたいです", InquiryCategory.OTHER),
        # 同数の場合は ACCOUNT → NETWORK → SOFTWARE の順
        ("パスワードもVPNもだめです", InquiryCategory.ACCOUNT),
        # 一致数が多いカテゴリを優先
        ("VPNとWi-FiのせいでExcelが開けない", InquiryCategory.NETWORK),
    ],
)
def test_classify_category(message: str, category: InquiryCategory) -> None:
    assert classify_category(message) is category


@pytest.mark.parametrize(
    "message",
    [
        "問い合わせとして登録して",
        "この内容で問い合わせを登録したい",
        "問い合わせを作成してください",
        "担当者に問い合わせたい",
        "ヘルプデスクに相談したいです",
        "起票して",
        "チケットを作成してください",
        "問い合わせたいです",
    ],
)
def test_detects_explicit_registration_request(message: str) -> None:
    assert has_registration_request(message)
    assert strip_registration_request(message) == ""


@pytest.mark.parametrize(
    "message", ["VPNがすぐ切れます", "問い合わせ一覧の見方を教えて", "登録方法がわからない"]
)
def test_ordinary_questions_are_not_registration_requests(message: str) -> None:
    assert not has_registration_request(message)


def test_request_at_the_beginning_is_removed() -> None:
    assert strip_registration_request("問い合わせとして登録して：パスワードを忘れました") == "パスワードを忘れました"


def test_only_request_returns_none() -> None:
    assert draft_inquiry_tool("問い合わせとして登録して") is None
    assert draft_inquiry_tool("   ") is None


def test_lengths_are_limited_to_inquiry_create_constraints() -> None:
    draft = draft_inquiry_tool("あ" * 3000)

    assert draft is not None
    assert len(draft.title) == TITLE_MAX_LENGTH == 100
    assert len(draft.description) == DESCRIPTION_MAX_LENGTH == 2000


@pytest.mark.parametrize(
    "message",
    [
        "プリンタで両面印刷できません。\n問い合わせとして登録して",
        "宇宙旅行に行きたいです",
        "😀" * 150 + "。問い合わせを登録して",
        "  先頭と末尾に空白がある質問です  ",
    ],
)
def test_draft_is_valid_inquiry_create(message: str) -> None:
    """起票案はそのまま POST /inquiries（InquiryCreate）で受け付けられる内容である。"""
    draft = draft_inquiry_tool(message)

    assert isinstance(draft, InquiryDraft)
    created = InquiryCreate.model_validate(draft.model_dump(mode="json", by_alias=True))
    assert created.model_dump() == draft.model_dump()


def test_tool_args_schema_is_available_for_llm() -> None:
    schema = DraftInquiryArgs.model_json_schema()

    assert schema["required"] == ["message"]
    assert schema["properties"]["message"]["maxLength"] == 1000
