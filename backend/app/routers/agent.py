from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.base import Agent
from app.agents.factory import build_agent
from app.config import settings
from app.db.session import get_db
from app.schemas.agent import AgentChatRequest, AgentChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@lru_cache(maxsize=1)
def get_agent() -> Agent:
    """使用する Agent（AGENT_PROVIDER で切り替え）。

    初回に 1 度だけ組み立て、以降のリクエストでは同じインスタンス（と OpenAI クライアント）を再利用する。
    Agent はリクエストごとの状態を持たないため共有してよい。テストでは依存関係を上書きできる。
    """
    return build_agent(settings)


@router.post("/chat", response_model=AgentChatResponse)
def chat(
    payload: AgentChatRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_agent)],
) -> AgentChatResponse:
    """利用者のメッセージに Agent が応答する（Tool を利用）。会話の状態は保持しない。"""
    return AgentChatResponse.from_reply(agent.respond(db, payload.message))
