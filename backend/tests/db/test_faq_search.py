from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.seed import seed_faqs
from app.models import Faq, InquiryCategory
from app.repositories.faqs import normalize, search_faqs


def add_faq(session: Session, question: str, keywords: str, answer: str = "回答") -> Faq:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    faq = Faq(
        question=question,
        answer=answer,
        category=InquiryCategory.OTHER,
        keywords=keywords,
        created_at=now,
        updated_at=now,
    )
    session.add(faq)
    session.commit()
    return faq


def questions(matches: list) -> list[str]:
    return [match.faq.question for match in matches]


def test_normalize_absorbs_width_and_case() -> None:
    assert normalize("  ＶＰＮ Wi-Fi  ") == "vpn wi-fi"


def test_keyword_contained_in_query_matches(db_session: Session) -> None:
    seed_faqs(db_session)

    matches = search_faqs(db_session, "VPNがすぐ切れてしまいます")

    assert matches[0].faq.question == "VPN が頻繁に切断されます"
    # キーワード「VPN」「切れる」ではなく「VPN」のみ一致（「切れて」は「切れる」を含まない）
    assert matches[0].score == 3


@pytest.mark.parametrize("query", ["vpn", "ＶＰＮ", "Vpn"])
def test_search_ignores_case_and_width(db_session: Session, query: str) -> None:
    seed_faqs(db_session)

    assert questions(search_faqs(db_session, query))[0] == "VPN が頻繁に切断されます"


def test_more_keyword_hits_rank_higher(db_session: Session) -> None:
    single = add_faq(db_session, "印刷について", "印刷")
    double = add_faq(db_session, "両面印刷について", "印刷 両面")

    matches = search_faqs(db_session, "両面印刷ができない")

    assert [match.faq.id for match in matches] == [double.id, single.id]
    assert [match.score for match in matches] == [6, 3]


def test_query_contained_in_question_scores(db_session: Session) -> None:
    faq = add_faq(db_session, "社内ポータルの使い方", "ポータル")

    [match] = search_faqs(db_session, "社内ポータル")

    assert match.faq.id == faq.id
    assert match.score == 3 + 2  # キーワード「ポータル」+ 質問文の部分一致


def test_query_contained_in_answer_scores(db_session: Session) -> None:
    faq = add_faq(db_session, "質問", "なし", answer="設定画面から変更してください")

    [match] = search_faqs(db_session, "設定画面")

    assert match.faq.id == faq.id
    assert match.score == 1


def test_space_separated_terms_score(db_session: Session) -> None:
    faq = add_faq(db_session, "メールの転送設定", "メール 転送")

    [match] = search_faqs(db_session, "outlook 転送")

    assert match.faq.id == faq.id
    assert match.score == 3 + 1  # キーワード「転送」+ 語「転送」


def test_ties_are_ordered_by_id(db_session: Session) -> None:
    first = add_faq(db_session, "A", "共通")
    second = add_faq(db_session, "B", "共通")

    assert [m.faq.id for m in search_faqs(db_session, "共通の質問")] == [first.id, second.id]


def test_no_match_returns_empty_list(db_session: Session) -> None:
    seed_faqs(db_session)

    assert search_faqs(db_session, "宇宙旅行の申請方法") == []


def test_wildcards_are_literal(db_session: Session) -> None:
    seed_faqs(db_session)

    assert search_faqs(db_session, "%") == []
    assert search_faqs(db_session, "_") == []


@pytest.mark.parametrize("query", [None, "", "   "])
def test_blank_query_returns_faqs_in_id_order(db_session: Session, query: str | None) -> None:
    seed_faqs(db_session)

    matches = search_faqs(db_session, query, limit=3)

    assert [match.faq.id for match in matches] == [1, 2, 3]
    assert all(match.score == 0 for match in matches)


def test_limit_is_applied(db_session: Session) -> None:
    seed_faqs(db_session)

    assert len(search_faqs(db_session, "アカウント", limit=1)) == 1
    assert len(search_faqs(db_session, None, limit=20)) == 10


def test_seed_faqs_examples(db_session: Session) -> None:
    """seed の FAQ が代表的な質問で上位に来ること（両 DB で同じ結果）。"""
    seed_faqs(db_session)

    cases = {
        "パスワードを忘れました": "パスワードを忘れてログインできません",
        "会議室でWiFiにつながらない": "社内 Wi-Fi に接続できません",
        "Excelが起動しない": "Excel や Word が起動直後に終了します",
        "プリンターで両面印刷したい": "複合機で両面印刷ができません",
        "スマホを機種変更したので MFA を再登録したい": "多要素認証（MFA）の認証アプリを再設定したい",
    }
    for query, expected in cases.items():
        assert questions(search_faqs(db_session, query))[0] == expected, query


def test_invalid_category_is_rejected_by_check_constraint(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_faqs_category"):
        db_session.execute(
            text(
                "INSERT INTO faqs (question, answer, category, keywords, created_at, updated_at) "
                "VALUES ('q', 'a', 'HARDWARE', 'k', :now, :now)"
            ),
            {"now": datetime(2026, 10, 7, tzinfo=UTC)},
        )
        db_session.flush()
