"""FallbackAgent（Demo 3 Step 5-D）のテスト。"""

import ast
import logging
from pathlib import Path

import pytest
from sqlalchemy import Engine, event
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentReply
from app.agents.fallback import FallbackAgent
from app.agents.llm.agent import LLMAgent
from app.agents.llm.client import (
    LLMError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.agents.rule_based import RuleBasedAgent
from app.config import BACKEND_DIR
from app.db.seed import seed_faqs, seed_inquiries
from tests.agents.fakes import FakeLLMClient, function_call, text_turn, tool_turn

FAKE_KEY = "sk-test-fallback-0123456789"
USER_MESSAGE = "VPNがすぐ切れます（社員番号 12345 の端末）"
LOGGER = "app.agents.fallback"


class RaisingAgent:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def respond(self, session: Session, message: str) -> AgentReply:
        self.calls += 1
        raise self.error


class RecordingAgent:
    def __init__(self, reply: AgentReply | None = None) -> None:
        self.reply = reply or AgentReply(message="fallback reply", action=AgentAction.INQUIRY_SUGGESTED)
        self.calls: list[str] = []

    def respond(self, session: Session, message: str) -> AgentReply:
        self.calls.append(message)
        return self.reply


@pytest.fixture
def seeded(db_session: Session) -> Session:
    seed_faqs(db_session)
    return db_session


# --- A. primary 正常 --------------------------------------------------------------------------


def test_primary_success_does_not_call_fallback(db_session: Session, caplog: pytest.LogCaptureFixture) -> None:
    primary = RecordingAgent(AgentReply(message="primary reply", action=AgentAction.FAQ_ANSWER))
    fallback = RecordingAgent()

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        reply = FallbackAgent(primary, fallback).respond(db_session, USER_MESSAGE)

    assert reply.message == "primary reply"
    assert fallback.calls == []
    assert caplog.records == []


# --- B〜E. LLM 層の障害 → fallback ---------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        LLMProviderError("rate_limit", status_code=429, request_id="req_abc"),
        LLMProviderError("timeout"),
        LLMResponseError("LLM returned an empty final response"),
        LLMTimeoutError("LLM agent timed out"),
        LLMError("other llm failure"),
        type("CustomLLMError", (LLMError,), {})("custom"),
    ],
)
def test_llm_errors_fall_back(
    db_session: Session, caplog: pytest.LogCaptureFixture, error: LLMError
) -> None:
    primary = RaisingAgent(error)
    fallback = RecordingAgent()

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        reply = FallbackAgent(primary, fallback).respond(db_session, USER_MESSAGE)

    assert reply.message == "fallback reply"
    assert primary.calls == 1
    assert fallback.calls == [USER_MESSAGE]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert type(error).__name__ in caplog.records[0].getMessage()


def test_fallback_to_real_rule_based_agent(seeded: Session) -> None:
    llm = LLMAgent(FakeLLMClient([LLMProviderError("server", status_code=503, request_id="req_1")]))

    reply = FallbackAgent(primary=llm, fallback=RuleBasedAgent()).respond(seeded, "VPNがすぐ切れます")

    expected = RuleBasedAgent().respond(seeded, "VPNがすぐ切れます")
    assert reply == expected
    assert reply.action is AgentAction.FAQ_ANSWER


def test_partial_llm_run_does_not_mix_into_fallback_reply(seeded: Session, migrated_engine: Engine) -> None:
    """LLM が Tool を実行した後に失敗しても、応答は fallback の結果だけで、DB 書き込みもない。"""
    seed_inquiries(seeded)
    llm = LLMAgent(
        FakeLLMClient(
            [
                tool_turn(function_call("draft_inquiry", {"message": "PCが起動しません"}, "d1")),
                LLMResponseError("broken"),
            ]
        )
    )
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):  # type: ignore[no-untyped-def]
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(migrated_engine, "before_cursor_execute", record)
    try:
        reply = FallbackAgent(llm, RuleBasedAgent()).respond(seeded, "VPNがすぐ切れます")
    finally:
        event.remove(migrated_engine, "before_cursor_execute", record)

    assert reply == RuleBasedAgent().respond(seeded, "VPNがすぐ切れます")
    assert reply.inquiry_draft is None  # LLM 側で作った起票案は混ざらない
    assert not {"INSERT", "UPDATE", "DELETE"} & set(statements)


# --- F・G. LLM と無関係な例外 → fallback しない ---------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("SELECT 1", {}, Exception("db down")),
        ProgrammingError("SELECT x", {}, Exception("bad sql")),
        SQLAlchemyError("generic db error"),
        RuntimeError("bug"),
        ValueError("bad value"),
        KeyError("missing"),
    ],
)
def test_non_llm_errors_are_not_handled(
    db_session: Session, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    fallback = RecordingAgent()

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(type(error)):
            FallbackAgent(RaisingAgent(error), fallback).respond(db_session, USER_MESSAGE)

    assert fallback.calls == []
    assert caplog.records == []


def test_fallback_module_catches_only_llm_errors() -> None:
    tree = ast.parse(Path(BACKEND_DIR / "app" / "agents" / "fallback.py").read_text(encoding="utf-8"))
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]

    assert handlers, "except 節がない"
    for handler in handlers:
        assert isinstance(handler.type, ast.Name) and handler.type.id == "LLMError"


# --- H. fallback 自体の失敗 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "fallback_error",
    [OperationalError("SELECT 1", {}, Exception("db down")), RuntimeError("rule agent bug"), LLMError("nested")],
)
def test_fallback_failure_is_not_swallowed(
    db_session: Session, caplog: pytest.LogCaptureFixture, fallback_error: Exception
) -> None:
    primary = RaisingAgent(LLMProviderError("timeout"))

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(type(fallback_error)):
            FallbackAgent(primary, RaisingAgent(fallback_error)).respond(db_session, USER_MESSAGE)

    assert len(caplog.records) == 1  # primary の失敗は記録されている


# --- I・J. ログ ---------------------------------------------------------------------------------


def test_warning_log_contains_only_safe_fields(db_session: Session, caplog: pytest.LogCaptureFixture) -> None:
    error = LLMProviderError("rate_limit", status_code=429, request_id="req_safe_1")

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        FallbackAgent(RaisingAgent(error), RecordingAgent()).respond(db_session, USER_MESSAGE)

    [record] = caplog.records
    text = record.getMessage()
    assert "falling back to RecordingAgent" in text
    assert "error=LLMProviderError" in text
    assert "kind=rate_limit" in text
    assert "status_code=429" in text
    assert "request_id=req_safe_1" in text
    for secret in (FAKE_KEY, USER_MESSAGE, "VPN", "12345", "SYSTEM", "search_faqs"):
        assert secret not in text
    assert record.exc_info is None  # スタックトレース（例外の内容）を出さない


def test_log_does_not_include_error_message(db_session: Session, caplog: pytest.LogCaptureFixture) -> None:
    """例外メッセージに機微な文字列が入っていてもログには出さない（型・kind 等のみ）。"""
    error = LLMResponseError(f"bad response for {USER_MESSAGE} key={FAKE_KEY}")

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        FallbackAgent(RaisingAgent(error), RecordingAgent()).respond(db_session, USER_MESSAGE)

    text = caplog.records[0].getMessage()
    assert FAKE_KEY not in text
    assert USER_MESSAGE not in text
    assert "error=LLMResponseError" in text
