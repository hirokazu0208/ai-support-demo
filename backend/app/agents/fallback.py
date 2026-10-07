"""LLM 層の障害時に別の Agent（RuleBasedAgent）で応答する FallbackAgent。

フォールバックするのは LLMError 系（プロバイダの障害・応答の不正・時間切れ）だけ。
DB 障害（SQLAlchemyError）やその他の例外はフォールバックせずにそのまま送出する
（RuleBasedAgent も同じ DB を使うため、切り替えても解決しない。原因を隠さない）。
"""

import logging

from sqlalchemy.orm import Session

from app.agents.base import Agent, AgentReply
from app.agents.llm.client import LLMError, LLMProviderError

logger = logging.getLogger(__name__)


class FallbackAgent:
    """primary（LLMAgent）で応答し、LLM 層の障害時は fallback（RuleBasedAgent）で応答する。

    primary の Tool は読み取り（search_faqs）と DB を使わない起票案（draft_inquiry）だけのため、
    途中で失敗してから fallback で応答し直しても、二重登録などの副作用は起きない。
    """

    def __init__(self, primary: Agent, fallback: Agent) -> None:
        self.primary = primary
        self.fallback = fallback

    def respond(self, session: Session, message: str) -> AgentReply:
        try:
            return self.primary.respond(session, message)
        except LLMError as error:
            # 利用者のメッセージ・プロンプト・API キー・応答本文はログに出さない
            kind = error.kind if isinstance(error, LLMProviderError) else None
            status_code = error.status_code if isinstance(error, LLMProviderError) else None
            request_id = error.request_id if isinstance(error, LLMProviderError) else None
            logger.warning(
                "LLM agent failed; falling back to %s (error=%s kind=%s status_code=%s request_id=%s)",
                type(self.fallback).__name__,
                type(error).__name__,
                kind,
                status_code,
                request_id,
            )
        return self.fallback.respond(session, message)
