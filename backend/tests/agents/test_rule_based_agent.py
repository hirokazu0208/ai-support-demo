import ast
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.agents.base import AgentAction
from app.agents.rule_based import NO_FAQ_MESSAGE, RuleBasedAgent
from app.config import BACKEND_DIR
from app.db.seed import seed_faqs
from app.repositories.faqs import search_faqs
from app.tools import faq_search


@pytest.fixture
def seeded(db_session: Session) -> Session:
    seed_faqs(db_session)
    return db_session


def test_faq_found_returns_faq_answer(seeded: Session) -> None:
    reply = RuleBasedAgent().respond(seeded, "VPNがすぐ切れます")

    assert reply.action is AgentAction.FAQ_ANSWER
    assert reply.matched_faqs[0].faq.question == "VPN が頻繁に切断されます"
    assert reply.matched_faqs[0].faq.answer in reply.message
    assert [call.name for call in reply.tool_calls] == ["search_faqs"]
    assert reply.tool_calls[0].arguments == {"query": "VPNがすぐ切れます", "limit": 3}


def test_multiple_faqs_are_returned_in_score_order(seeded: Session) -> None:
    reply = RuleBasedAgent().respond(seeded, "パスワードを忘れたうえに VPN もつながりません")

    questions = [match.faq.question for match in reply.matched_faqs]
    assert reply.action is AgentAction.FAQ_ANSWER
    assert set(questions[:2]) == {"パスワードを忘れてログインできません", "VPN が頻繁に切断されます"}
    scores = [match.score for match in reply.matched_faqs]
    assert scores == sorted(scores, reverse=True)
    # 2 件目以降は「関連する FAQ」として案内する
    assert f"・{questions[1]}" in reply.message


def test_matched_faqs_equal_tool_result(seeded: Session) -> None:
    """Agent の matched_faqs は FAQ 検索 Tool（= repository）の結果そのもの。"""
    reply = RuleBasedAgent().respond(seeded, "プリンターで両面印刷したい")

    expected = search_faqs(seeded, "プリンターで両面印刷したい", limit=3)
    assert [(m.faq.id, m.score) for m in reply.matched_faqs] == [
        (m.faq.id, m.score) for m in expected
    ]


def test_no_faq_suggests_inquiry(seeded: Session) -> None:
    reply = RuleBasedAgent().respond(seeded, "宇宙旅行に行きたいです")

    assert reply.action is AgentAction.INQUIRY_SUGGESTED
    assert reply.matched_faqs == []
    assert reply.message == NO_FAQ_MESSAGE
    assert [call.name for call in reply.tool_calls] == ["search_faqs"]


def test_no_faq_when_table_is_empty(db_session: Session) -> None:
    reply = RuleBasedAgent().respond(db_session, "VPNがすぐ切れます")

    assert reply.action is AgentAction.INQUIRY_SUGGESTED


def test_agent_calls_faq_search_through_tool_layer(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Agent は Tool 経由で repository の search_faqs() を呼ぶ（HTTP や独自実装を使わない）。"""
    calls: list[tuple[str, int]] = []
    original = faq_search.search_faqs

    def spy(session, q, *, limit):  # type: ignore[no-untyped-def]
        calls.append((q, limit))
        return original(session, q, limit=limit)

    monkeypatch.setattr(faq_search, "search_faqs", spy)

    reply = RuleBasedAgent(faq_limit=2).respond(seeded, "Excelが起動しない")

    assert calls == [("Excelが起動しない", 2)]
    assert len(reply.matched_faqs) <= 2


def test_agents_and_tools_do_not_reimplement_faq_search() -> None:
    """検索アルゴリズム（score_faq / normalize）と DB アクセスは repository にのみ存在する。"""
    forbidden_names = {"score_faq", "normalize", "select", "Faq"}
    for path in [
        *(BACKEND_DIR / "app" / "agents").glob("*.py"),
        *(BACKEND_DIR / "app" / "tools").glob("*.py"),
    ]:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported = {alias.name for alias in node.names}
                assert not imported & forbidden_names, (path.name, imported)
                if path.parent.name == "agents":
                    # Agent は repository の検索関数を直接呼ばず、Tool を使う
                    assert "search_faqs" not in imported, path.name
            assert not (
                isinstance(node, ast.FunctionDef) and node.name in {"score_faq", "search_faqs"}
            ), path.name
