"""ルールベースの Agent。外部 LLM を使わず、決まった手順で Tool を呼び出す。

判断ロジック（Step 2 時点）:
  1. 利用者のメッセージで FAQ 検索 Tool を呼ぶ
  2. 一致した FAQ があれば、最上位の FAQ の回答を返す（FAQ_ANSWER）
  3. なければ問い合わせの登録を提案する（INQUIRY_SUGGESTED。Step 4 で起票案につなぐ）
"""

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentReply, ToolCall
from app.tools import faq_search

NO_FAQ_MESSAGE = (
    "FAQ では解決できませんでした。問い合わせとして登録すると、ヘルプデスクの担当者が対応します。"
)


class RuleBasedAgent:
    def __init__(self, faq_limit: int = faq_search.DEFAULT_LIMIT) -> None:
        self.faq_limit = faq_limit

    def respond(self, session: Session, message: str) -> AgentReply:
        tool_call = ToolCall(
            name=faq_search.NAME, arguments={"query": message, "limit": self.faq_limit}
        )
        matches = faq_search.search_faq_tool(session, message, limit=self.faq_limit)

        if not matches:
            return AgentReply(
                message=NO_FAQ_MESSAGE,
                action=AgentAction.INQUIRY_SUGGESTED,
                tool_calls=[tool_call],
            )

        top = matches[0].faq
        lines = [f"「{top.question}」の FAQ が見つかりました。", "", top.answer]
        if len(matches) > 1:
            lines += ["", "関連する FAQ:"]
            lines += [f"・{match.faq.question}" for match in matches[1:]]
        lines += ["", "解決しない場合は、問い合わせとして登録できます。"]
        return AgentReply(
            message="\n".join(lines),
            action=AgentAction.FAQ_ANSWER,
            matched_faqs=matches,
            tool_calls=[tool_call],
        )
