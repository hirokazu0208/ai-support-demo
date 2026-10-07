"""Agent Factory（Demo 3 Step 5-D）のテスト。偽の API キーと MockTransport だけを使い、実通信はしない。"""

import json

import httpx2
import pytest
from sqlalchemy.orm import Session

from app.agents.base import AgentAction
from app.agents.factory import build_agent
from app.agents.fallback import FallbackAgent
from app.agents.llm.agent import LLMAgent, LLMAgentLimits
from app.agents.llm.openai_client import OpenAIResponsesClient
from app.agents.rule_based import RuleBasedAgent
from app.config import Settings
from app.db.seed import seed_faqs

FAKE_KEY = "sk-test-factory-0123456789"
MODEL = "test-model-from-settings"


def openai_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "agent_provider": "openai",
        "openai_api_key": FAKE_KEY,
        "openai_model": MODEL,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_rule_provider_builds_rule_based_agent() -> None:
    agent = build_agent(Settings(_env_file=None))  # type: ignore[call-arg]

    assert type(agent) is RuleBasedAgent


def test_openai_without_fallback_builds_llm_agent() -> None:
    agent = build_agent(openai_settings(agent_fallback_to_rule=False))

    assert type(agent) is LLMAgent
    assert isinstance(agent.client, OpenAIResponsesClient)


def test_openai_with_fallback_builds_fallback_agent() -> None:
    agent = build_agent(openai_settings())  # AGENT_FALLBACK_TO_RULE の既定値は true

    assert type(agent) is FallbackAgent
    assert type(agent.primary) is LLMAgent
    assert type(agent.fallback) is RuleBasedAgent
    assert isinstance(agent.primary.client, OpenAIResponsesClient)


def test_openai_settings_are_passed_to_client() -> None:
    settings = openai_settings(
        agent_fallback_to_rule=False,
        openai_base_url="https://llm.example.test/v1",
        openai_timeout_seconds=7.5,
        openai_max_retries=2,
    )

    agent = build_agent(settings)

    assert isinstance(agent, LLMAgent)
    client = agent.client
    assert isinstance(client, OpenAIResponsesClient)
    assert client.model == MODEL
    sdk = client._client  # SDK クライアントの設定値を確認する（通信はしない）
    assert sdk.api_key == FAKE_KEY
    assert str(sdk.base_url) == "https://llm.example.test/v1/"
    assert sdk.timeout == 7.5
    assert sdk.max_retries == 2


def test_limits_are_passed_to_llm_agent() -> None:
    settings = openai_settings(
        agent_fallback_to_rule=False,
        agent_max_llm_rounds=2,
        agent_max_tool_calls=3,
        agent_timeout_seconds=15,
        openai_max_output_tokens=500,
    )

    agent = build_agent(settings)

    assert isinstance(agent, LLMAgent)
    assert agent.limits == LLMAgentLimits(
        max_llm_rounds=2, max_tool_calls=3, timeout_seconds=15.0, max_output_tokens=500
    )


def test_built_agent_uses_settings_over_mock_transport(db_session: Session) -> None:
    """組み立てた Agent が設定のモデル・キー・宛先で Responses API を呼ぶ（MockTransport で受け取る）。"""
    seed_faqs(db_session)
    sent: list[httpx2.Request] = []
    replies = [
        {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "search_faqs", "arguments": '{"query": "VPN"}', "status": "completed"},
        {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "回答", "annotations": []}]},
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        item = replies[len(sent) - 1]
        return httpx2.Response(200, json={"id": f"resp_{len(sent)}", "object": "response", "created_at": 1, "model": MODEL, "status": "completed", "output": [item]})

    agent = build_agent(
        openai_settings(openai_base_url="https://llm.example.test/v1", openai_max_retries=0),
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    reply = agent.respond(db_session, "VPNがすぐ切れます")

    assert reply.action is AgentAction.FAQ_ANSWER
    assert [str(r.url) for r in sent] == ["https://llm.example.test/v1/responses"] * 2
    assert all(r.headers["authorization"] == f"Bearer {FAKE_KEY}" for r in sent)
    assert all(json.loads(r.content)["model"] == MODEL for r in sent)


def test_openai_provider_requires_settings_before_building() -> None:
    """キー・モデルがない設定は Settings の時点で拒否される（Factory まで到達しない）。"""
    with pytest.raises(ValueError):
        Settings(_env_file=None, agent_provider="openai")  # type: ignore[call-arg]
