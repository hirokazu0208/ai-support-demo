"""LLM に公開する Function Tool の許可リスト（Demo 3 Step 5）のテスト。"""

import ast
import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.seed import seed_faqs, seed_inquiries
from app.models import InquiryCategory
from app.schemas.inquiry import InquiryDraft
from app.tools import draft_inquiry, faq_search
from app.tools.registry import (
    FUNCTION_TOOLS,
    LLM_FAQ_SEARCH_LIMIT,
    ToolArgumentsError,
    UnknownToolError,
    execute_function_tool,
    function_tool_definitions,
    get_function_tool,
)

REGISTRY_PATH = BACKEND_DIR / "app" / "tools" / "registry.py"


# --- 許可リスト・スキーマ -------------------------------------------------------------


def test_allowlist_is_exactly_two_tools() -> None:
    assert set(FUNCTION_TOOLS) == {"search_faqs", "draft_inquiry"}
    assert [d["name"] for d in function_tool_definitions()] == ["search_faqs", "draft_inquiry"]


def test_allowlist_is_read_only() -> None:
    with pytest.raises(TypeError):
        FUNCTION_TOOLS["create_inquiry"] = FUNCTION_TOOLS["search_faqs"]  # type: ignore[index]


def test_tool_definitions_match_expected_schema() -> None:
    assert function_tool_definitions() == [
        {
            "type": "function",
            "name": "search_faqs",
            "description": faq_search.DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "利用者の質問文"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "draft_inquiry",
            "description": draft_inquiry.DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string", "description": "利用者のメッセージ"}},
                "required": ["message"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ]


def test_definitions_reuse_existing_tool_names_and_args_models() -> None:
    assert FUNCTION_TOOLS["search_faqs"].name == faq_search.NAME
    assert FUNCTION_TOOLS["search_faqs"].args_model is faq_search.FaqSearchArgs
    assert FUNCTION_TOOLS["draft_inquiry"].name == draft_inquiry.NAME
    assert FUNCTION_TOOLS["draft_inquiry"].args_model is draft_inquiry.DraftInquiryArgs


def test_strict_schemas_require_all_properties_and_forbid_extra() -> None:
    for definition in function_tool_definitions():
        parameters = definition["parameters"]
        assert definition["strict"] is True
        assert parameters["additionalProperties"] is False
        assert sorted(parameters["required"]) == sorted(parameters["properties"])
        json.dumps(definition)  # JSON にシリアライズできること


def test_search_faqs_does_not_expose_limit() -> None:
    properties = FUNCTION_TOOLS["search_faqs"].definition()["parameters"]["properties"]

    assert set(properties) == {"query"}
    assert "limit" not in json.dumps(function_tool_definitions())


def test_definitions_are_copies() -> None:
    definition = function_tool_definitions()[0]
    definition["parameters"]["properties"]["limit"] = {"type": "integer"}

    assert "limit" not in FUNCTION_TOOLS["search_faqs"].definition()["parameters"]["properties"]


# --- 実行（既存 Tool への委譲）-----------------------------------------------------------


def test_search_faqs_delegates_to_existing_tool(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_faqs(db_session)
    calls: list[tuple[str, int]] = []
    original = faq_search.search_faq_tool

    def spy(session, query, limit=faq_search.DEFAULT_LIMIT):  # type: ignore[no-untyped-def]
        calls.append((query, limit))
        return original(session, query, limit=limit)

    monkeypatch.setattr(faq_search, "search_faq_tool", spy)

    outcome = execute_function_tool(db_session, "search_faqs", '{"query": "VPNがすぐ切れます"}')

    assert calls == [("VPNがすぐ切れます", LLM_FAQ_SEARCH_LIMIT)] == [("VPNがすぐ切れます", 3)]
    assert outcome.arguments == {"query": "VPNがすぐ切れます", "limit": 3}
    assert outcome.matched_faqs[0].faq.question == "VPN が頻繁に切断されます"
    assert outcome.output["faqs"][0] == {
        "id": 6,
        "question": "VPN が頻繁に切断されます",
        "answer": outcome.matched_faqs[0].faq.answer,
        "category": "NETWORK",
        "score": 3,
    }
    assert outcome.inquiry_draft is None


def test_search_faqs_without_match(db_session: Session) -> None:
    seed_faqs(db_session)

    outcome = execute_function_tool(db_session, "search_faqs", '{"query": "宇宙旅行"}')

    assert outcome.output == {"faqs": []}
    assert outcome.matched_faqs == []


def test_draft_inquiry_delegates_to_existing_tool(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    original = draft_inquiry.draft_inquiry_tool

    def spy(message):  # type: ignore[no-untyped-def]
        calls.append(message)
        return original(message)

    monkeypatch.setattr(draft_inquiry, "draft_inquiry_tool", spy)
    message = "プリンタで両面印刷できません。\n問い合わせとして登録して"

    outcome = execute_function_tool(
        db_session, "draft_inquiry", json.dumps({"message": message}, ensure_ascii=False)
    )

    assert calls == [message]
    assert outcome.arguments == {"message": message}
    assert isinstance(outcome.inquiry_draft, InquiryDraft)
    assert outcome.inquiry_draft.category is InquiryCategory.OTHER
    assert outcome.output == {
        "draft": {
            "title": "プリンタで両面印刷できません",
            "description": "プリンタで両面印刷できません。",
            "category": "OTHER",
        }
    }
    assert outcome.matched_faqs == []


def test_draft_inquiry_without_content(db_session: Session) -> None:
    outcome = execute_function_tool(db_session, "draft_inquiry", '{"message": "問い合わせを登録したい"}')

    assert outcome.inquiry_draft is None
    assert outcome.output["draft"] is None
    assert "reason" in outcome.output


def test_max_calls_per_reply() -> None:
    assert FUNCTION_TOOLS["search_faqs"].max_calls_per_reply == 2
    assert FUNCTION_TOOLS["draft_inquiry"].max_calls_per_reply == 1


# --- 実行できないもの -------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "create_inquiry",
        "update_inquiry_status",
        "search_faq_tool",  # モジュール内の関数名でも呼べない
        "draft_inquiry_tool",
        "__import__",
        "SEARCH_FAQS",
        "",
    ],
)
def test_unknown_tool_cannot_be_executed(db_session: Session, name: str) -> None:
    with pytest.raises(UnknownToolError):
        get_function_tool(name)
    with pytest.raises(UnknownToolError):
        execute_function_tool(db_session, name, '{"query": "VPN"}')


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_faqs", "not json"),
        ("search_faqs", '["VPN"]'),
        ("search_faqs", "{}"),
        ("search_faqs", '{"query": ""}'),
        ("search_faqs", '{"query": 123}'),
        ("search_faqs", '{"query": "VPN", "limit": 10}'),  # limit は公開していない
        ("search_faqs", json.dumps({"query": "あ" * 201})),
        ("draft_inquiry", '{"message": ""}'),
        ("draft_inquiry", json.dumps({"message": "あ" * 1001})),
        ("draft_inquiry", '{"message": "x", "title": "y"}'),
    ],
)
def test_invalid_arguments_are_rejected(
    db_session: Session, name: str, arguments: str
) -> None:
    with pytest.raises(ToolArgumentsError):
        execute_function_tool(db_session, name, arguments)


def test_registry_tools_do_not_write_to_database(
    db_session: Session, migrated_engine: Engine
) -> None:
    seed_faqs(db_session)
    seed_inquiries(db_session)
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):  # type: ignore[no-untyped-def]
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(migrated_engine, "before_cursor_execute", record)
    try:
        execute_function_tool(db_session, "search_faqs", '{"query": "VPNがすぐ切れます"}')
        execute_function_tool(
            db_session, "draft_inquiry", '{"message": "PCが起動しません。問い合わせとして登録して"}'
        )
    finally:
        event.remove(migrated_engine, "before_cursor_execute", record)

    assert statements, "SQL が記録されていない"
    assert not {"INSERT", "UPDATE", "DELETE"} & set(statements)


def test_registry_does_not_reference_write_operations_or_sql() -> None:
    """registry は問い合わせの登録処理・repository の書き込み・SQL を参照しない。"""
    tree = ast.parse(Path(REGISTRY_PATH).read_text(encoding="utf-8"))
    imported_modules = set()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module)
            imported_names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            imported_modules |= {alias.name for alias in node.names}

    assert "app.repositories.inquiries" not in imported_modules
    assert not imported_names & {"create_inquiry", "update_inquiry_status", "Inquiry", "text", "select"}
    assert not any(module and module.startswith("sqlalchemy") and module != "sqlalchemy.orm" for module in imported_modules)
    # 動的な関数探索（getattr / globals / importlib / eval）を使わない
    called = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called & {"getattr", "globals", "eval", "exec", "__import__"}
    assert "importlib" not in imported_modules
