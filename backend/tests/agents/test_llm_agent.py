"""LLMAgent（Demo 3 Step 5-B）のテスト。OpenAI API は呼ばず FakeLLMClient だけを使う。"""

import ast
from pathlib import Path

import pytest
from sqlalchemy import Engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.agents.base import AgentAction
from app.agents.llm.agent import (
    INVALID_ARGUMENTS_ERROR,
    TOOL_LIMIT_ERROR,
    UNKNOWN_TOOL_ERROR,
    LLMAgent,
    LLMAgentLimits,
)
from app.agents.llm.client import LLMError, LLMResponseError, LLMTimeoutError
from app.agents.llm.prompts import SYSTEM_INSTRUCTIONS
from app.agents.rule_based import DRAFT_GUIDE
from app.config import BACKEND_DIR, Settings
from app.db.seed import seed_faqs, seed_inquiries
from app.models import Inquiry, InquiryCategory
from app.tools.registry import function_tool_definitions
from tests.agents.fakes import FakeClock, FakeLLMClient, function_call, text_turn, tool_turn

PRINTER_MESSAGE = "プリンタで両面印刷できません。\n問い合わせとして登録して"


@pytest.fixture
def seeded(db_session: Session) -> Session:
    seed_faqs(db_session)
    return db_session


def search(query: str, call_id: str = "call_search") -> object:
    return function_call("search_faqs", {"query": query}, call_id)


def draft(message: str, call_id: str = "call_draft") -> object:
    return function_call("draft_inquiry", {"message": message}, call_id)


# --- A. FAQ 正常系 ------------------------------------------------------------------------


def test_faq_answer_flow(seeded: Session) -> None:
    client = FakeLLMClient(
        [tool_turn(search("VPNがすぐ切れます")), text_turn("VPN クライアントを最新版に更新してください。")]
    )

    reply = LLMAgent(client).respond(seeded, "VPNがすぐ切れます")

    assert reply.action is AgentAction.FAQ_ANSWER
    assert reply.message == "VPN クライアントを最新版に更新してください。"
    assert [m.faq.question for m in reply.matched_faqs] == ["VPN が頻繁に切断されます"]
    assert [(c.name, c.arguments) for c in reply.tool_calls] == [
        ("search_faqs", {"query": "VPNがすぐ切れます", "limit": 3})
    ]
    assert reply.inquiry_draft is None
    assert client.call_count == 2


def test_requests_carry_instructions_tools_and_user_message(seeded: Session) -> None:
    client = FakeLLMClient([tool_turn(search("VPN")), text_turn("回答")])

    LLMAgent(client, LLMAgentLimits(max_output_tokens=321)).respond(seeded, "VPNがすぐ切れます")

    first = client.requests[0]
    assert first.instructions == SYSTEM_INSTRUCTIONS
    assert first.tools == function_tool_definitions()
    assert first.input_items == [{"role": "user", "content": "VPNがすぐ切れます"}]
    assert first.max_output_tokens == 321
    assert first.parallel_tool_calls is False
    assert first.max_tool_calls == 1


def test_tool_result_is_returned_with_matching_call_id(seeded: Session) -> None:
    client = FakeLLMClient([tool_turn(search("VPN", call_id="call_abc")), text_turn("回答")])

    LLMAgent(client).respond(seeded, "VPN")

    second = client.requests[1]
    # 前ターンの function_call item と、その結果（同じ call_id）が積まれている
    assert second.input_items[1] == {
        "type": "function_call",
        "call_id": "call_abc",
        "name": "search_faqs",
        "arguments": '{"query": "VPN"}',
    }
    outputs = client.function_outputs(1)
    assert list(outputs) == ["call_abc"]
    assert outputs["call_abc"]["faqs"][0]["question"] == "VPN が頻繁に切断されます"


# --- B. 問い合わせドラフト正常系 --------------------------------------------------------------


def test_draft_flow(seeded: Session, migrated_engine: Engine) -> None:
    client = FakeLLMClient(
        [
            tool_turn(search("プリンタで両面印刷できません")),
            tool_turn(draft(PRINTER_MESSAGE)),
            text_turn("起票案を作成しました。内容をご確認ください。"),
        ]
    )
    statements = record_sql(migrated_engine)

    reply = LLMAgent(client).respond(seeded, PRINTER_MESSAGE)

    stop_recording(migrated_engine, statements)
    assert reply.action is AgentAction.INQUIRY_DRAFTED
    assert reply.inquiry_draft is not None
    assert reply.inquiry_draft.title == "プリンタで両面印刷できません"
    assert reply.inquiry_draft.category is InquiryCategory.OTHER
    assert [m.faq.question for m in reply.matched_faqs] == ["複合機で両面印刷ができません"]
    assert [c.name for c in reply.tool_calls] == ["search_faqs", "draft_inquiry"]
    assert reply.message.endswith(DRAFT_GUIDE)
    assert "まだ登録されていません" in reply.message
    assert client.tool_choices == ["required", "auto", "auto"]
    assert not {"INSERT", "UPDATE", "DELETE"} & set(statements.values)


# --- C. FAQ 一致なし ----------------------------------------------------------------------


def test_no_faq_match_suggests_inquiry(seeded: Session) -> None:
    client = FakeLLMClient(
        [tool_turn(search("宇宙旅行に行きたいです")), text_turn("該当する FAQ はありませんでした。")]
    )

    reply = LLMAgent(client).respond(seeded, "宇宙旅行に行きたいです")

    assert reply.action is AgentAction.INQUIRY_SUGGESTED
    assert reply.matched_faqs == []
    assert reply.inquiry_draft is None
    assert [c.name for c in reply.tool_calls] == ["search_faqs"]


# --- D. 未知の Tool ------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["create_inquiry", "update_inquiry_status", "search_faq_tool", "__import__"])
def test_unknown_tool_is_not_executed(
    seeded: Session, migrated_engine: Engine, name: str
) -> None:
    seed_inquiries(seeded)
    before = seeded.scalar(select(func.count()).select_from(Inquiry))
    client = FakeLLMClient(
        [
            tool_turn(function_call(name, {"title": "x", "description": "y", "category": "OTHER"}, "call_x")),
            text_turn("登録できませんでした。"),
        ]
    )
    statements = record_sql(migrated_engine)

    reply = LLMAgent(client).respond(seeded, "問い合わせを直接登録して")

    stop_recording(migrated_engine, statements)
    assert client.function_outputs(1) == {"call_x": UNKNOWN_TOOL_ERROR}
    assert reply.tool_calls == []
    assert reply.action is AgentAction.INQUIRY_SUGGESTED
    assert not {"INSERT", "UPDATE", "DELETE"} & set(statements.values)
    assert seeded.scalar(select(func.count()).select_from(Inquiry)) == before


# --- E. 不正な引数 ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_faqs", "not json"),
        ("search_faqs", {"query": ""}),
        ("search_faqs", {"query": "VPN", "limit": 10}),
        ("search_faqs", {"q": "VPN"}),
        ("draft_inquiry", {"message": "あ" * 1001}),
        ("draft_inquiry", {"message": "x", "category": "OTHER"}),
    ],
)
def test_invalid_arguments_are_not_executed(
    seeded: Session, monkeypatch: pytest.MonkeyPatch, name: str, arguments: object
) -> None:
    executed: list[str] = []
    from app.tools import draft_inquiry as draft_module
    from app.tools import faq_search as faq_module

    monkeypatch.setattr(faq_module, "search_faq_tool", lambda *a, **k: executed.append("search") or [])
    monkeypatch.setattr(draft_module, "draft_inquiry_tool", lambda *a, **k: executed.append("draft"))
    client = FakeLLMClient([tool_turn(function_call(name, arguments, "call_bad")), text_turn("回答")])

    reply = LLMAgent(client).respond(seeded, "VPN")

    assert executed == []
    assert client.function_outputs(1) == {"call_bad": INVALID_ARGUMENTS_ERROR}
    assert reply.tool_calls == []


def test_error_outputs_do_not_leak_internal_details() -> None:
    for error in (UNKNOWN_TOOL_ERROR, INVALID_ARGUMENTS_ERROR, TOOL_LIMIT_ERROR):
        text = str(error)
        for marker in ("Traceback", "Error(", "registry", "pydantic", "sqlalchemy", ".py"):
            assert marker not in text


# --- F. Tool 回数上限（同じ Tool を繰り返し要求）---------------------------------------------


def test_repeated_tool_requests_stop_at_limit(seeded: Session) -> None:
    client = FakeLLMClient(
        [
            tool_turn(search("VPN", "c1")),
            tool_turn(search("VPN 切断", "c2")),
            tool_turn(search("VPN 再接続", "c3")),  # 3 回目（search_faqs の上限 2 を超える）
            text_turn("VPN の FAQ をご確認ください。"),
        ]
    )

    reply = LLMAgent(client).respond(seeded, "VPNがすぐ切れます")

    assert [c.name for c in reply.tool_calls] == ["search_faqs", "search_faqs"]
    outputs = client.function_outputs(3)
    assert set(outputs) == {"c1", "c2", "c3"}
    assert "faqs" in outputs["c1"] and "faqs" in outputs["c2"]  # 2 回までは実行された
    assert outputs["c3"] == TOOL_LIMIT_ERROR  # 3 回目は実行されない
    # 上限に達したら Tool なしで最終回答を求める
    assert client.tool_choices == ["required", "auto", "auto", "none"]
    assert reply.action is AgentAction.FAQ_ANSWER


def test_total_tool_call_limit_from_settings(seeded: Session) -> None:
    settings = Settings(_env_file=None, agent_max_tool_calls=1)  # type: ignore[call-arg]
    client = FakeLLMClient([tool_turn(search("VPN")), text_turn("回答")])

    reply = LLMAgent(client, LLMAgentLimits.from_settings(settings)).respond(seeded, "VPN")

    assert len(reply.tool_calls) == 1
    # 合計上限（1）に達したので、次は tool_choice=none で締める
    assert client.tool_choices == ["required", "none"]


def test_round_limit_forces_final_answer(seeded: Session) -> None:
    client = FakeLLMClient(
        [
            tool_turn(function_call("unknown_a", {}, "u1")),
            tool_turn(function_call("unknown_b", {}, "u2")),
            text_turn("ご案内できる情報がありませんでした。"),
        ]
    )

    reply = LLMAgent(client, LLMAgentLimits(max_llm_rounds=2)).respond(seeded, "VPN")

    assert client.tool_choices == ["required", "auto", "none"]
    assert reply.tool_calls == []
    assert reply.action is AgentAction.INQUIRY_SUGGESTED


def test_tool_request_after_none_is_an_error(seeded: Session) -> None:
    client = FakeLLMClient(
        [tool_turn(search("VPN", "c1")), tool_turn(search("VPN", "c2"))]
    )

    with pytest.raises(LLMResponseError):
        LLMAgent(client, LLMAgentLimits(max_llm_rounds=1)).respond(seeded, "VPN")
    assert client.tool_choices == ["required", "none"]


# --- G. Tool 個別上限 ----------------------------------------------------------------------


def test_draft_inquiry_runs_at_most_once(seeded: Session) -> None:
    client = FakeLLMClient(
        [
            tool_turn(draft("PCが起動しません", "d1")),
            tool_turn(draft("モニターも映りません", "d2")),
            text_turn("起票案を作成しました。"),
        ]
    )

    reply = LLMAgent(client).respond(seeded, "PCが起動しません。問い合わせとして登録して")

    assert [c.name for c in reply.tool_calls] == ["draft_inquiry"]
    assert reply.inquiry_draft is not None
    assert reply.inquiry_draft.title == "PCが起動しません"  # 1 回目の結果だけ
    assert client.function_outputs(2)["d2"] == TOOL_LIMIT_ERROR


def test_search_faqs_runs_at_most_twice_even_within_total_limit(seeded: Session) -> None:
    client = FakeLLMClient(
        [
            tool_turn(search("VPN", "s1")),
            tool_turn(search("Wi-Fi", "s2")),
            tool_turn(search("パスワード", "s3")),
            text_turn("回答"),
        ]
    )

    reply = LLMAgent(client, LLMAgentLimits(max_llm_rounds=5, max_tool_calls=10)).respond(seeded, "x")

    assert [c.arguments["query"] for c in reply.tool_calls] == ["VPN", "Wi-Fi"]
    assert client.function_outputs(3)["s3"] == TOOL_LIMIT_ERROR
    # 2 回の検索結果を重複なしで保持する
    assert {m.faq.question for m in reply.matched_faqs} >= {
        "VPN が頻繁に切断されます",
        "社内 Wi-Fi に接続できません",
    }


# --- H. 空の最終回答 ------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   \n "])
def test_empty_final_response_is_an_error(seeded: Session, text: str) -> None:
    client = FakeLLMClient([tool_turn(search("VPN")), text_turn(text)])

    with pytest.raises(LLMResponseError):
        LLMAgent(client).respond(seeded, "VPN")


def test_long_final_response_is_truncated(seeded: Session) -> None:
    client = FakeLLMClient([tool_turn(search("VPN")), text_turn("あ" * 5000)])

    reply = LLMAgent(client, LLMAgentLimits(max_message_length=2000)).respond(seeded, "VPN")

    assert len(reply.message) == 2000


# --- I. LLM が架空のデータを書く ------------------------------------------------------------


def test_fabricated_faq_and_draft_in_text_are_ignored(seeded: Session) -> None:
    fabricated = (
        "FAQ#999「宇宙旅行の申請方法」によると申請できます。\n"
        "起票案: タイトル=宇宙旅行 カテゴリ=ACCOUNT。問い合わせを登録しました。"
    )
    client = FakeLLMClient([tool_turn(search("宇宙旅行")), text_turn(fabricated)])

    reply = LLMAgent(client).respond(seeded, "宇宙旅行に行きたいです")

    assert reply.matched_faqs == []
    assert reply.inquiry_draft is None
    assert reply.action is AgentAction.INQUIRY_SUGGESTED


def test_action_ignores_llm_text_when_faq_exists(seeded: Session) -> None:
    client = FakeLLMClient(
        [tool_turn(search("VPN")), text_turn("起票案を作成しました（INQUIRY_DRAFTED）。")]
    )

    reply = LLMAgent(client).respond(seeded, "VPN")

    assert reply.action is AgentAction.FAQ_ANSWER
    assert reply.inquiry_draft is None


def test_text_only_first_turn_has_no_structured_data(seeded: Session) -> None:
    """tool_choice=required に反してテキストだけ返しても、架空の構造化データは作らない。"""
    client = FakeLLMClient([text_turn("FAQ によると再起動で直ります。")])

    reply = LLMAgent(client).respond(seeded, "VPN")

    assert reply.tool_calls == []
    assert reply.matched_faqs == []
    assert reply.action is AgentAction.INQUIRY_SUGGESTED


# --- J. DB 副作用 --------------------------------------------------------------------------


def test_llm_agent_never_writes_to_database(seeded: Session, migrated_engine: Engine) -> None:
    seed_inquiries(seeded)
    before = seeded.scalar(select(func.count()).select_from(Inquiry))
    client = FakeLLMClient(
        [
            tool_turn(search("プリンタ")),
            tool_turn(function_call("create_inquiry", {"title": "x"}, "x1")),
            tool_turn(draft(PRINTER_MESSAGE)),
            text_turn("起票案を作成しました。"),
        ]
    )
    statements = record_sql(migrated_engine)

    reply = LLMAgent(client, LLMAgentLimits(max_llm_rounds=5)).respond(seeded, PRINTER_MESSAGE)

    stop_recording(migrated_engine, statements)
    assert statements.values, "SQL が記録されていない"
    assert not {"INSERT", "UPDATE", "DELETE"} & set(statements.values)
    assert seeded.scalar(select(func.count()).select_from(Inquiry)) == before
    assert reply.action is AgentAction.INQUIRY_DRAFTED


def test_llm_package_has_no_write_paths_or_provider_sdk() -> None:
    """agents/llm は SQL・問い合わせの登録処理・repository の書き込みを参照しない。

    openai SDK を import してよいのはアダプター（openai_client.py、Step 5-C）だけ。
    """
    for path in (BACKEND_DIR / "app" / "agents" / "llm").glob("*.py"):
        sdk_allowed = path.name == "openai_client.py"
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and not sdk_allowed:
                assert not any(a.name.split(".")[0] == "openai" for a in node.names), path.name
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = {alias.name for alias in node.names}
                if not sdk_allowed:
                    assert module.split(".")[0] != "openai", path.name
                assert module != "app.repositories.inquiries", path.name
                assert not (module.startswith("sqlalchemy") and module != "sqlalchemy.orm"), path.name
                assert not names & {"create_inquiry", "update_inquiry_status", "Inquiry", "text"}, path.name
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"getattr", "eval", "exec", "__import__"}, path.name


# --- K. tool_choice ------------------------------------------------------------------------


def test_tool_choice_sequence(seeded: Session) -> None:
    client = FakeLLMClient(
        [tool_turn(search("プリンタ")), tool_turn(draft(PRINTER_MESSAGE)), text_turn("完了")]
    )

    LLMAgent(client).respond(seeded, PRINTER_MESSAGE)

    assert client.tool_choices == ["required", "auto", "auto"]
    assert [r.max_tool_calls for r in client.requests] == [1, 1, 1]


# --- L. 全体の時間上限（実際の sleep は使わない）----------------------------------------------


def test_timeout_after_slow_llm_call(seeded: Session) -> None:
    clock = FakeClock()
    client = FakeLLMClient(
        [tool_turn(search("VPN")), text_turn("回答")],
        on_call=lambda n: clock.advance(25.0),  # 1 回目の LLM 呼び出しで 25 秒経過
    )

    with pytest.raises(LLMTimeoutError):
        LLMAgent(client, LLMAgentLimits(timeout_seconds=20.0), clock=clock).respond(seeded, "VPN")
    assert client.call_count == 1


def test_timeout_before_next_llm_call(seeded: Session) -> None:
    clock = FakeClock()
    client = FakeLLMClient(
        [tool_turn(search("VPN")), text_turn("回答")],
        on_call=lambda n: clock.advance(12.0),
    )

    with pytest.raises(LLMTimeoutError):
        LLMAgent(client, LLMAgentLimits(timeout_seconds=20.0), clock=clock).respond(seeded, "VPN")
    # 1 回目（12 秒）は間に合い、2 回目の後で 24 秒となり時間切れ
    assert client.call_count == 2


def test_within_timeout_succeeds(seeded: Session) -> None:
    clock = FakeClock()
    client = FakeLLMClient(
        [tool_turn(search("VPN")), text_turn("回答")], on_call=lambda n: clock.advance(5.0)
    )

    reply = LLMAgent(client, LLMAgentLimits(timeout_seconds=20.0), clock=clock).respond(seeded, "VPN")

    assert reply.action is AgentAction.FAQ_ANSWER


# --- エラーの伝播 ---------------------------------------------------------------------------


def test_llm_errors_propagate(seeded: Session) -> None:
    client = FakeLLMClient([LLMError("provider failed")])

    with pytest.raises(LLMError):
        LLMAgent(client).respond(seeded, "VPN")


def test_database_errors_are_not_swallowed(seeded: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.tools import faq_search as faq_module

    def broken(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(faq_module, "search_faq_tool", broken)
    client = FakeLLMClient([tool_turn(search("VPN")), text_turn("回答")])

    with pytest.raises(OperationalError):
        LLMAgent(client).respond(seeded, "VPN")
    assert client.call_count == 1  # DB の例外を LLM に渡して続行しない


# --- SQL 記録の補助 --------------------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.values: list[str] = []

    def __call__(self, _conn, _cursor, statement, *_args) -> None:  # type: ignore[no-untyped-def]
        self.values.append(statement.lstrip().split()[0].upper())


def record_sql(engine: Engine) -> _Recorder:
    recorder = _Recorder()
    event.listen(engine, "before_cursor_execute", recorder)
    return recorder


def stop_recording(engine: Engine, recorder: _Recorder) -> None:
    event.remove(engine, "before_cursor_execute", recorder)
