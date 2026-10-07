from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.base import Agent
from app.agents.rule_based import RuleBasedAgent
from app.db.session import get_db
from app.schemas.agent import AgentChatRequest, AgentChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])


def get_agent() -> Agent:
    """使用する Agent。LLM Agent（Demo 3 Step 5）へはここで差し替える（テストでは依存関係を上書きできる）。"""
    return RuleBasedAgent()


@router.post("/chat", response_model=AgentChatResponse)
def chat(
    payload: AgentChatRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_agent)],
) -> AgentChatResponse:
    """利用者のメッセージに Agent が応答する（FAQ 検索 Tool を利用）。会話の状態は保持しない。"""
    return AgentChatResponse.from_reply(agent.respond(db, payload.message))
