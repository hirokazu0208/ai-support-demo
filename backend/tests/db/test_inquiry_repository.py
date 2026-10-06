from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import InquiryStatus
from app.repositories.inquiries import get_inquiry, list_inquiries
from tests.conftest import MakeInquiry


def ids(inquiries: list) -> list[int]:
    return [inquiry.id for inquiry in inquiries]


def test_list_orders_by_created_at_desc_then_id_desc(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    same_time = datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
    oldest = make_inquiry(created_at=datetime(2026, 10, 1, 0, 0, tzinfo=UTC))
    tie_first = make_inquiry(created_at=same_time)
    tie_second = make_inquiry(created_at=same_time)
    newest = make_inquiry(created_at=datetime(2026, 10, 3, 0, 0, tzinfo=UTC))

    assert ids(list_inquiries(db_session)) == [
        newest.id,
        tie_second.id,
        tie_first.id,
        oldest.id,
    ]


def test_list_returns_empty_list_when_no_data(db_session: Session) -> None:
    assert list_inquiries(db_session) == []


def test_q_matches_title_or_description(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    in_title = make_inquiry(title="VPNが切れる", description="本文")
    in_description = make_inquiry(title="接続の問題", description="VPN接続が不安定")
    make_inquiry(title="プリンタ", description="印刷できない")

    assert set(ids(list_inquiries(db_session, q="VPN"))) == {
        in_title.id,
        in_description.id,
    }


def test_q_is_case_insensitive_for_ascii(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    excel = make_inquiry(title="Excelが起動しない")

    assert ids(list_inquiries(db_session, q="excel")) == [excel.id]
    assert ids(list_inquiries(db_session, q="EXCEL")) == [excel.id]


def test_q_matches_japanese_substring(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    target = make_inquiry(title="パスワードを忘れてログインできない")
    make_inquiry(title="Wi-Fiに接続できない")

    assert ids(list_inquiries(db_session, q="ログイン")) == [target.id]


def test_q_treats_wildcards_as_literals(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    percent = make_inquiry(title="CPU使用率100%")
    underscore = make_inquiry(title="file_name が不正")
    make_inquiry(title="filename が長い")

    assert ids(list_inquiries(db_session, q="%")) == [percent.id]
    assert ids(list_inquiries(db_session, q="file_name")) == [underscore.id]


def test_status_filters_inquiries(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    closed = make_inquiry(status=InquiryStatus.CLOSED)
    make_inquiry(status=InquiryStatus.OPEN)

    assert ids(list_inquiries(db_session, status=InquiryStatus.CLOSED)) == [closed.id]


def test_q_and_status_are_combined_with_and(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    match = make_inquiry(title="VPN障害", status=InquiryStatus.CLOSED)
    make_inquiry(title="VPN障害", status=InquiryStatus.OPEN)
    make_inquiry(title="プリンタ", status=InquiryStatus.CLOSED)

    assert ids(
        list_inquiries(db_session, q="VPN", status=InquiryStatus.CLOSED)
    ) == [match.id]


def test_q_without_match_returns_empty_list(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    make_inquiry(title="VPN障害")

    assert list_inquiries(db_session, q="存在しない語") == []


def test_get_inquiry_returns_inquiry(
    db_session: Session, make_inquiry: MakeInquiry
) -> None:
    inquiry = make_inquiry(title="詳細")

    found = get_inquiry(db_session, inquiry.id)

    assert found is not None
    assert found.title == "詳細"


def test_get_inquiry_returns_none_when_missing(db_session: Session) -> None:
    assert get_inquiry(db_session, 999) is None
