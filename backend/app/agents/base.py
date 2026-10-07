from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.repositories.faqs import FaqMatch
from app.schemas.inquiry import InquiryDraft


class AgentAction(StrEnum):
    """Agent の応答の種類。画面（Step 3）はこの値で次の操作を出し分ける。"""

    FAQ_ANSWER = "FAQ_ANSWER"  # FAQ をもとに回答した
    INQUIRY_SUGGESTED = "INQUIRY_SUGGESTED"  # 問い合わせの登録を提案した（起票案は作れなかった）
    INQUIRY_DRAFTED = "INQUIRY_DRAFTED"  # 問い合わせの起票案を作成した（登録は人が行う）


@dataclass(frozen=True)
class ToolCall:
    """Agent が呼び出した Tool の記録（応答に含め、デモ・デバッグで Tool の利用を可視化する）。"""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentReply:
    message: str
    action: AgentAction
    matched_faqs: list[FaqMatch] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    # 問い合わせの起票案。DB には保存しない（人が既存の登録画面で確認してから登録する）
    inquiry_draft: InquiryDraft | None = None


class Agent(Protocol):
    """Agent の共通インターフェース。RuleBasedAgent と将来の LLM Agent が実装する。

    session は Tool（repository）の呼び出しに使う。Agent 自身は DB を直接操作しない。
    """

    def respond(self, session: Session, message: str) -> AgentReply: ...
