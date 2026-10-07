"""設定（Settings）から Agent を組み立てる。

AGENT_PROVIDER=rule   → RuleBasedAgent（既定。外部 LLM なし）
AGENT_PROVIDER=openai → OpenAIResponsesClient → LLMAgent
                        AGENT_FALLBACK_TO_RULE=true（既定）なら FallbackAgent(LLMAgent, RuleBasedAgent)
"""

import httpx2

from app.agents.base import Agent
from app.agents.fallback import FallbackAgent
from app.agents.llm.agent import LLMAgent, LLMAgentLimits
from app.agents.llm.openai_client import OpenAIResponsesClient
from app.agents.rule_based import RuleBasedAgent
from app.config import Settings


def build_agent(settings: Settings, *, http_client: httpx2.Client | None = None) -> Agent:
    """Agent を作る。http_client はテストで MockTransport を渡すためのもの（本番では指定しない）。"""
    if settings.agent_provider == "rule":
        return RuleBasedAgent()

    client = OpenAIResponsesClient.from_settings(settings, http_client=http_client)
    llm_agent = LLMAgent(client, LLMAgentLimits.from_settings(settings))
    if settings.agent_fallback_to_rule:
        return FallbackAgent(primary=llm_agent, fallback=RuleBasedAgent())
    return llm_agent
