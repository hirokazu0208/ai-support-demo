from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

from app.agents.base import AgentAction, AgentReply
from app.schemas.faq import FaqResponse

AGENT_MESSAGE_MAX_LENGTH = 1000

# 前後の空白を除いてから長さを検証する（空白のみは 422）
AgentMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=AGENT_MESSAGE_MAX_LENGTH),
]


class AgentChatRequest(BaseModel):
    """POST /agent/chat のリクエスト。未定義の項目は 422（入力も camelCase のみ）。"""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel)

    message: AgentMessage


class ToolCallResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    arguments: dict[str, Any]


class AgentChatResponse(BaseModel):
    """POST /agent/chat の応答（JSON は camelCase: matchedFaqs / toolCalls）。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    message: str
    action: AgentAction
    matched_faqs: list[FaqResponse]
    tool_calls: list[ToolCallResponse]

    @classmethod
    def from_reply(cls, reply: AgentReply) -> "AgentChatResponse":
        return cls(
            message=reply.message,
            action=reply.action,
            matched_faqs=[FaqResponse.from_match(match) for match in reply.matched_faqs],
            tool_calls=[
                ToolCallResponse(name=call.name, arguments=call.arguments)
                for call in reply.tool_calls
            ],
        )
